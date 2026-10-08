# Validação da Parte 2 — 07/10/2026

A aplicação manteve paridade em 55 arquivos entre `non_centralized/` e `centralized/`. `./mvnw clean verify` passou nas duas pastas, com 15 testes Java em cada. Os 14 testes Python do executor passaram em cada cenário; os seis testes do verificador de entrega passaram na Parte 2. Ambos os arquivos Compose passaram em `docker compose config --quiet`.

## Pipeline real com processos locais

Foram executados os binários oficiais Fluent Bit 5.1.3, Loki 3.7.8 e Grafana 13.2.3, os quatro JARs gerados pelo Maven e três instâncias PostgreSQL 17.11. Usaram diretórios temporários e portas distintas das do Compose. As configurações de observabilidade vieram dos arquivos deste projeto, com substituição de caminhos e endereços locais.

Um adaptador temporário substituiu somente o controle de containers no `runner.py`: parada/início de processos e leitura de stdout. As requisições, preparação de dados, injeção, contratos, invariantes e comparação dos eventos no Loki usaram a implementação do projeto. Os logs reais dos JARs foram encapsulados no formato `json-file` do Docker para passar pela mesma entrada tail e pelos mesmos filtros do Fluent Bit.

| Experimento | Resposta observada | Eventos de origem conferidos no Loki | Restauração e invariantes |
|---|---|---:|---|
| E01 | 400 / `VALIDATION_ERROR` | 21 | Aprovadas |
| E02 | 502 / `DOWNSTREAM_ERROR` | 53 | Aprovadas |
| E03 | 504 / `DOWNSTREAM_TIMEOUT` | 49 | Aprovadas |
| E04 | 502 / `DOWNSTREAM_ERROR` | 48 | Aprovadas |
| E05 | 502 / `DOWNSTREAM_UNAVAILABLE` | 38 | Aprovadas |

E02 parou e reiniciou o PostgreSQL de produtos; E05 parou e reiniciou o JAR Product. E03 aguardou a conclusão da consulta atrasada. Nenhum desses pedidos alterou o estoque ou criou pedido persistido. Todos os campos dos eventos registrados nos arquivos de origem foram comparados com os eventos entregues, incluindo mensagens, timestamps, trace, operação e stack traces.

Um teste adicional enviou quatro eventos JSON com acentuação e stack traces de mais de 40 KB divididos em fragmentos Docker. Os eventos foram recompostos e preservados. A entrada também recebeu uma mensagem do lançador Java e um evento com `tcc.stack=non_centralized`; esse último foi excluído do Loki.

O Data Source e o dashboard foram provisionados. A consulta ao trace de E02 passou pelo proxy HTTP do Grafana até o Loki e retornou logs dos quatro serviços. As cinco consultas do dashboard foram executadas pelo mesmo proxy e retornaram resultados. O `traceId` permaneceu no corpo dos eventos; a consulta de validação conferiu que ele não era um label indexado.

O [relatório resumido em JSON](validation/native-2026-10-07.json) registra traces, horários, respostas, restauração, invariantes e entrega. É evidência técnica de desenvolvimento, não uma amostra para avaliação cega. Os processos de validação foram encerrados ao final.

## Correções encontradas na integração

- O output Loki do Fluent Bit remove o campo usado para criar um label. A normalização passou a usar uma cópia temporária para preservar `service` no JSON.
- `| json` no LogQL acrescenta campos extraídos aos labels retornados pela consulta. O verificador passou a usar um filtro de linha para conferir os labels indexados sem confundi-los com campos extraídos.
- As consultas de contagem de erros do dashboard extraem somente `level`, evitando criar séries intermediárias por trace e stack trace.

## Limite da validação e execução em Compose

O daemon Docker exige sudo, e `sudo -n` neste ambiente retorna que uma senha é necessária. A primeira validação foi feita com processos locais. Depois, o usuário iniciou o Compose e executou E02; a execução está registrada como `20261007T120147375271Z-5aa69e55` nos resultados locais. O POST retornou o 502 previsto, mas a restauração foi marcada como falha porque uma única consulta ao produto ainda recebeu 503 após o banco voltar.

A verificação HTTP posterior confirmou o produto com estoque 10, ausência de pedidos para o usuário experimental e os 33 eventos de origem desse trace preservados no Loki, nos quatro serviços. A infraestrutura e o pipeline Docker funcionaram nessa execução. O executor foi corrigido nos dois cenários para aguardar a recuperação funcional com prazo limitado, e dois testes de regressão cobrem recuperação após 503 e esgotamento do prazo. O resultado antigo permanece preservado.

A repetição `20261007T121757258474Z-d9c32521` passou com o executor corrigido em Compose: resposta 502 / `DOWNSTREAM_ERROR`, coleta, invariantes, restauração e entrega aprovadas. O estoque permaneceu 10, os pedidos antes/depois permaneceram vazios e os 33 eventos do trace `0e834040-cb5a-4053-87e6-d55c072ec10a` foram conferidos nos quatro serviços. Os metadados locais registram `success=true`, `cleanup.success=true`, `invariants.success=true` e `observability.success=true`.

Execuções adicionais fornecidas pelo usuário e conferidas pelos metadados locais:

| Ambiente | Caso | Run ID | Observado | Resultado |
|---|---|---|---|---|
| centralized | E01 | 20261007T123118153185Z-4bfbc9fb | 400 / VALIDATION_ERROR | Aprovado, incluindo entrega |
| centralized | E03 | 20261007T123125593698Z-24f8396d | 504 / DOWNSTREAM_TIMEOUT | Aprovado, incluindo entrega |
| centralized | E04 | 20261007T123142885440Z-c3240bb7 | 502 / DOWNSTREAM_ERROR | Aprovado, incluindo entrega |
| centralized | E05 | 20261007T123153253168Z-14fec67a | 504 / DOWNSTREAM_TIMEOUT | Divergiu do contrato 502 / DOWNSTREAM_UNAVAILABLE; coleta, restauração e invariantes aprovadas |
| non_centralized | E02 | 20261007T123934487633Z-621c7675 | 502 / DOWNSTREAM_ERROR | Aprovado |

Em E05, o Order registrou `HttpConnectTimeoutException: HTTP connect timed out` ao tentar chamar o Product parado. A aplicação classificou esse sintoma como timeout. A verificação de entrega pelo wrapper não foi executada porque o contrato HTTP falhou. A divergência permanece aberta para investigação; não se reclassificou a injeção como E03 e a execução foi preservada. Os registros comprovam resultados técnicos, sem preencher diagnósticos humanos nem medir seu tempo.

Para validar essa parte na máquina com sudo autorizado, execute na raiz do repositório, com o cenário sem centralização parado:

```bash
sudo env FAULT_ENABLED=true ./tcc.sh centralized up --build -d --wait
sudo python3 centralized/scripts/observability.py
sudo python3 centralized/scripts/smoke.py --faults --check-logs
sudo ./centralized/experiments/run-experiment.sh E02
# Repita E01, E03, E04 e E05 individualmente.
sudo ./centralized/experiments/reset-environment.sh
sudo ./tcc.sh centralized ps
```

O runner centralizado só declara sucesso depois de restaurar a aplicação e conferir a entrega no Loki. Os resultados ficam em `centralized/experiments/results/`, ignorados pelo Git. Consulte a mesma execução no Grafana Explore usando o trace e o intervalo registrados em `metadata.json`.
