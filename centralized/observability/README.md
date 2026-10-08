# Centralização de logs

Fluxo: stdout JSON das aplicações → arquivos `json-file` do Docker → Fluent Bit → Loki → Grafana. A aplicação continua disponível independentemente do coletor; não foram acrescentadas dependências de observabilidade às chamadas de negócio.

## Coleta e parsing

O Fluent Bit 5.1.3 lê o diretório de logs do Docker em modo somente leitura. Configure `DOCKER_LOG_DIR` em `.env` se o daemon não usar `/var/lib/docker/containers`. Para descobrir o diretório:

```bash
sudo docker info --format '{{.DockerRootDir}}'
```

Adicione `/containers` ao caminho retornado. Esta configuração é destinada a Docker Engine para Linux; Docker Desktop e rootless precisam de caminhos/permissões compatíveis. O container do coletor usa UID 0 para ler os arquivos do daemon, sem montar o socket Docker.

As aplicações têm os labels de origem `tcc.stack` e `tcc.service`, incluídos pelo driver na camada JSON do Docker. O coletor aceita apenas os quatro serviços com `tcc.stack=centralized`. Logs de PostgreSQL, do cenário sem centralização e da própria infraestrutura ficam fora dessa entrada, evitando mistura e coleta recursiva.

O parser Docker recompõe fragmentos da mesma linha. O parser Spring interpreta o JSON interno, preserva os campos originais e usa o timestamp da aplicação com fuso e precisão. A normalização Lua remove o envelope de transporte; mensagens não JSON, como as do lançador Java, permanecem como `message`, com origem e timestamp Docker. Não se inventam `traceId` ou nível nesses registros.

O JSON, `stack_trace` e os campos de operação são preservados. O Fluent Bit envia os labels `job=tcc` e `service`; o Loki acrescenta `service_name` a partir de `service`. Nível e trace permanecem no corpo JSON. O Fluent Bit mantém offsets e buffer em um volume; seus reenvios tratam entrega de logs e não acrescentam tolerância às requisições de negócio. Um buffer cheio, rotação antes da coleta ou interrupção abrupta ainda pode perder/duplicar eventos; a verificação da execução compara os eventos de origem com os consultados no Loki.

O campo `service` é duplicado temporariamente como `loki_service` na normalização. O output Loki consome/remove essa cópia ao criar o label, preservando `service` no JSON original. As consultas de contagem de erros do dashboard extraem somente `level`, evitando gerar séries de consulta para cada trace ou stack trace.

## Armazenamento e visualização

Loki 3.7.8 executa em um processo, com TSDB/v13 e filesystem local persistente. Grafana 13.2.3 mantém seus dados em outro volume. As versões estão fixadas no Compose. Não há retenção automática configurada para apagar resultados do estudo; monitore o espaço e faça a limpeza explicitamente após preservar a evidência.

O Data Source Loki (`tcc-loki`) e o dashboard (`tcc-logs`) são provisionados por arquivos. Grafana usa `http://loki:3100` na rede interna. As portas HTTP do host são publicadas apenas em loopback: Grafana 3000, Loki 3100, Fluent Bit 2020. Podem ser alteradas pelas variáveis de `.env.example`; o verificador descobre as portas efetivamente publicadas no Compose.

A senha `tcc-local` é destinada ao ambiente local e definida na primeira inicialização. Alterar a variável depois de criar o volume Grafana não troca a senha já armazenada; mantenha a configuração coerente com a credencial atual.

## Disponibilidade e testes de entrega

As imagens Loki e Fluent Bit são mínimas e não recebem probes fictícios baseados em ferramentas de shell ausentes. `docker compose up --wait` aguarda as aplicações; o verificador HTTP confirma a disponibilidade real da infraestrutura, incluindo Data Source e dashboard:

```bash
sudo python3 scripts/observability.py
sudo python3 scripts/observability.py --metadata experiments/results/E02/EXECUCAO/metadata.json
```

O wrapper centralizado executa o primeiro teste antes da injeção e o segundo depois da restauração. O limite padrão é o prazo de restauração do runner; o comando independente usa 60 segundos, ajustável por `--timeout`. A chegada ao Loki é assíncrona, então a consulta aguarda os eventos com prazo limitado.

O teste exige o trace nos serviços participantes e compara todos os campos dos eventos de origem com os retornados pelo Loki. Isso detecta perda de parsing, mensagens, stack traces e eventos. E01 exige Gateway/Order; E05 exige Gateway/Order/User; E02–E04 exigem os quatro serviços. Não interpreta a causa dos erros. Em caso de falha na entrega, os metadados registram `observability.success=false`; a restauração já foi executada.

Para investigar no Explore, `| json | traceId="..."` é adequado: os campos extraídos na consulta aparecem como labels na resposta, mas não são indexados. O verificador usa um filtro de linha por trace para conferir os labels de armazenamento sem confundi-los com os extraídos. Veja a [documentação oficial do LogQL](https://grafana.com/docs/loki/latest/query/log_queries/).

Os campos `cleanup` e `observability` são separados. O reset restaura a aplicação, inicia a infraestrutura quando necessário e preserva os três volumes de observabilidade e os resultados. Recomeçar o diagnóstico não exige apagar os logs: use intervalo e trace específicos.

Para testar processos locais sem containers existe `--http-only`, com URLs explícitas e credenciais por `GRAFANA_ADMIN_USER`/`GRAFANA_ADMIN_PASSWORD`. Esse modo não comprova os mounts/permissões do Docker e deve ser reportado separadamente da execução completa em Compose.

## Protocolo experimental

Mantenha as mesmas versões, fontes, recursos das aplicações, timeouts e condições equivalentes de dados nos dois cenários. Execute um ambiente por vez. O dashboard é complementar; use Explore como ferramenta principal e defina na metodologia o acesso permitido ao avaliador.

Mensure manualmente o tempo e o acerto do diagnóstico. Para estudar a investigação com os logs disponíveis, inicie a contagem depois de confirmar a disponibilidade da evidência; registre latência de ingestão separadamente. Os metadados com cenário/alvo conhecidos pertencem ao operador. O coletor não ingere esses arquivos.
