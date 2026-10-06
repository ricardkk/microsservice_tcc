# Experimentos de falha controlada

O executor provoca uma falha por execução, registra a resposta e coleta os logs de cada aplicação separadamente. Não interpreta os logs nem realiza o diagnóstico humano. A implementação usa Python 3 com biblioteca padrão; os scripts shell apenas chamam o mesmo executor.

## Preparação e execução

Na raiz do projeto, reconstrua as imagens com as configurações atuais:

```bash
FAULT_ENABLED=true docker compose up --build -d --wait
./experiments/run-experiment.sh E01
./experiments/run-experiment.sh E02
./experiments/run-experiment.sh E03
./experiments/run-experiment.sh E04
./experiments/run-experiment.sh E05
```

Se o Docker exigir sudo, use:

```bash
sudo env FAULT_ENABLED=true docker compose up --build -d --wait
sudo ./experiments/run-experiment.sh E02
sudo ./experiments/run-experiment.sh E03
```

E03 e E04 exigem `FAULT_ENABLED=true` no Product. Essa opção habilita a capacidade de injeção; a falha só é aplicada à requisição que recebe os cabeçalhos de controle. E01, E02 e E05 funcionam também com a capacidade desabilitada.

Todos os cenários aceitam os mesmos argumentos:

```bash
./experiments/run-experiment.sh E02 --ready-timeout 120
./experiments/scenarios/E02-database-unavailable.sh --ready-timeout 120
./experiments/run-experiment.sh E01 --url http://localhost:8080 --results-dir /tmp/tcc-results
```

`--url` deve apontar para o Gateway do mesmo projeto Compose. O prazo HTTP padrão do executor é 15 segundos, ajustável por `--request-timeout`. O prazo de restauração padrão é 90 segundos, além dos limites dos comandos Docker e consultas HTTP.

## Catálogo e contratos

| Cenário | Injeção | Resultado esperado em `POST /api/orders` |
|---|---|---|
| E01 | Quantidade -5, rejeitada no Order | 400, `VALIDATION_ERROR` |
| E02 | Parada real de `products-db` | 502, `DOWNSTREAM_ERROR`; Product registra falha de banco/503 |
| E03 | Atraso na consulta GET ao Product | 504, `DOWNSTREAM_TIMEOUT` observado no Order |
| E04 | Exceção de processamento no Product | 502, `DOWNSTREAM_ERROR`; Product registra `INTERNAL_ERROR`/500 |
| E05 | Parada real de `product-service` | 502, `DOWNSTREAM_UNAVAILABLE` |

E01 envolve Gateway e Order, pois a validação ocorre antes das consultas ao catálogo. E02–E04 podem produzir eventos nos quatro serviços; em E05, o Product parado não recebe a requisição.

O cabeçalho de E03 é `X-Fault-Type: timeout`; o de E04 é `X-Fault-Type: internal-error`. Ambos usam `X-Fault-Service: product-service`. São enviados apenas no POST experimental e propagados pelo Gateway e Order. O atraso é permitido somente em GET: a consulta termina normalmente após a espera e o prazo HTTP do Order gera o timeout. Uma tentativa de aplicar atraso a uma escrita retorna 400 antes de executar o domínio.

## Estado inicial, isolamento e restauração

Antes da preparação, os sete containers devem existir, estar em execução e saudáveis. Um ambiente inválido é rejeitado. O executor usa um lock comum para impedir dois experimentos/reset simultâneos, mesmo com diretórios de resultados diferentes. Esse lock não controla comandos Docker ou requisições feitos manualmente: mantenha o ambiente dedicado ao experimento.

Cada execução cria um usuário e um produto de teste, usa os IDs retornados e confirma suas consultas e o estoque. Não cria pedido de sucesso como preparação. Os dados de preparação permanecem nos bancos e seus IDs ficam registrados nos metadados.

A restauração é armada antes de parar um recurso e executada em `finally`, inclusive para resposta HTTP inesperada, falha de conexão, falha de coleta e SIGINT/SIGTERM. Em E03, há uma espera limitada que cobre o atraso e a consulta anterior ao User antes da coleta/restauração; isso evita iniciar outro cenário enquanto a consulta atrasada ainda está ativa. Os scripts individuais passam pelo mesmo executor.

Após restaurar, o executor aguarda os health checks e consulta a aplicação para verificar que os pedidos do usuário de teste e o estoque não mudaram. Essa verificação confirma invariantes; não infere a causa pelos logs. Uma violação de dados é registrada separadamente de falha na restauração dos containers.

Respostas 4xx/5xx previstas são resultados válidos. Código de saída 0 indica contrato, coleta, restauração e invariantes aprovados; 1 indica falha; uma interrupção por sinal usa 128 + número do sinal quando a restauração termina normalmente. Toda execução iniciada registra também falhas e o resultado do cleanup.

Para recuperar o ambiente manualmente:

```bash
./experiments/reset-environment.sh
# Ou: sudo ./experiments/reset-environment.sh
```

O reset inicia os bancos existentes, inicia/recria as aplicações com `FAULT_ENABLED=false` e verifica consultas funcionais. Preserva volumes, dados, logs e resultados. Não modifica `.env`; ajuste esse arquivo se quiser manter a injeção desabilitada nos próximos `docker compose up`. Para voltar a E03/E04, execute novamente o comando de preparação com `FAULT_ENABLED=true`.

SIGKILL, desligamento da máquina e indisponibilidade do Docker podem impedir a restauração automática. Após esses casos, use o reset e confirme o ambiente antes de repetir um cenário. A restauração pelo executor ocorre depois da requisição medida; os serviços continuam sem retry, fallback ou circuit breaker.

## Limites de espera e repetibilidade

| Configuração | Padrão |
|---|---:|
| Aquisição de conexão no pool, `DB_CONNECTION_TIMEOUT_MS` | 1000 ms |
| Leitura HTTP do Order | 2000 ms |
| Atraso do Product, `FAULT_DELAY_MS` | 5000 ms |
| Leitura HTTP do Gateway | 10000 ms |
| Requisição do executor | 15000 ms |

O executor registra os valores das variáveis suportadas nos containers e os identificadores das imagens. Valida banco < Order < Gateway < executor e, para E03, atraso > Order. Use imagens reconstruídas a partir deste código e evite sobrescrever essas propriedades por argumentos Java ou configurações Spring adicionais, que não são inspecionados pelo executor.

A parada real de banco depende do estado das conexões e do agendamento dos processos. O timeout do pool não limita toda consulta SQL. Se E02 devolver 504, a execução é registrada como divergência do contrato, restaurada e retorna falha; não é reclassificada como E03. O protocolo torna a ação reproduzível, sem prometer duração idêntica de cada execução.

## Resultados e avaliação humana

Cada repetição recebe um diretório próprio:

```text
experiments/results/E02/<run-id>/
├── metadata.json
├── response.json
└── logs/
    ├── gateway.log
    ├── order-service.log
    ├── user-service.log
    └── product-service.log
```

Os metadados contêm cenário e alvo conhecidos pelo operador, payload/cabeçalhos, IDs de preparação, timeouts, imagens, horários, resposta observada, `traceId`, coleta, invariantes e restauração. `response.json` preserva status, cabeçalhos relevantes, corpo decodificado e texto original. Se nenhuma resposta chegar, a falha de transporte fica nos metadados e não é criada uma resposta fictícia.

O executor não envia `X-Trace-Id`: captura o identificador gerado pelo Gateway e exige sua correspondência no corpo da resposta. Cada requisição tem seu próprio trace; os serviços participantes compartilham o valor propagado. O `run-id` identifica o diretório de execução e não substitui a correlação da aplicação.

Os logs são capturados desde o início da requisição experimental, antes da restauração. Não são unificados, filtrados por erro nem analisados pelo executor. O prazo inclui a conclusão tardia do atraso em E03. Eventos adicionais do período, como health checks, podem aparecer nos arquivos.

Para uma avaliação em que a causa seja desconhecida, forneça apenas os logs em um diretório com nome neutro e guarde os metadados, a resposta e a saída do executor com o responsável. Os logs mantêm códigos operacionais, causas e stack traces; foram removidos marcadores explícitos como `faultId`, `faultType` e `INJECTED_*`. Hooks controlados ainda podem aparecer no stack trace; registre essa limitação na metodologia.

Os resultados locais são ignorados pelo Git. A etapa de centralização de logs não faz parte desta implementação.

## Verificação de desenvolvimento

```bash
./mvnw clean verify
python3 -m unittest discover -s experiments -p 'test_*.py' -v
python3 scripts/smoke.py --faults --check-logs
```

O smoke verifica várias condições da aplicação em sequência. O executor experimental registra um cenário por vez. Os testes Python usam HTTP real local e um substituto do controle Docker para verificar gravação de respostas e restauração em falhas; a execução E01–E05 com Compose valida também containers e PostgreSQL reais.
