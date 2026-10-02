# Cenários iniciais para reprodução

Este catálogo técnico é um ponto de partida. A classificação definitiva, as métricas e o protocolo de comparação pertencem à metodologia do TCC.

Habilite a injeção no ambiente local:

```bash
FAULT_ENABLED=true docker compose up -d --wait
python3 scripts/smoke.py --faults --check-logs > experiments/results/smoke.json
```

Os cabeçalhos `X-Fault-Service` e `X-Fault-Type` afetam apenas a requisição atual. Todos propagam os cabeçalhos e somente o serviço indicado aplica a falha. O log da origem contém `faultId`, por exemplo `product-service:database`.

| Tipo | Comportamento na origem | Criando pedido com falha em product-service |
|---|---|---|
| `internal-error` | Exceção antes do processamento, HTTP 500 | HTTP 502, `DOWNSTREAM_ERROR` |
| `database` | Exceção de acesso a dados **simulada**, HTTP 503 | HTTP 502, `DOWNSTREAM_ERROR` |
| `timeout` | Aguarda 5 s e encerra sem executar o domínio | HTTP 504, `DOWNSTREAM_TIMEOUT` |
| `not-found` | Recurso inexistente simulado, HTTP 404 | HTTP 422, `PRODUCT_NOT_FOUND` |
| `invalid-response` | GET retorna HTTP 200 com representação incompleta | HTTP 502, `INVALID_DOWNSTREAM_RESPONSE` |

Exemplo, usando IDs criados anteriormente:

```bash
curl -i http://localhost:8080/api/orders \
  -H 'Content-Type: application/json' \
  -H 'X-Trace-Id: experimento-produto-001' \
  -H 'X-Fault-Service: product-service' \
  -H 'X-Fault-Type: internal-error' \
  -d '{"userId":1,"items":[{"productId":1,"quantity":2}]}'
```

Para falha real de disponibilidade, mantenha os outros serviços em execução:

```bash
docker compose stop product-service
# Execute POST /api/orders sem cabeçalhos de injeção.
# Esperado: 502 DOWNSTREAM_UNAVAILABLE, sem persistir pedido.
docker compose start product-service
```

Para indisponibilidade real do banco:

```bash
docker compose stop products-db
# GET /api/products/1: esperado 503 DATABASE_UNAVAILABLE.
# POST /api/orders: esperado 502 DOWNSTREAM_ERROR.
docker compose start products-db
```

A falha real de banco depende do estado das conexões; registre o momento de parada e a duração observada. A injeção `database` representa uma exceção controlada, não uma desconexão real do PostgreSQL.

Para voltar ao ambiente sem injeção:

```bash
FAULT_ENABLED=false docker compose up -d --wait
```

Se estiver usando `.env`, mantenha `FAULT_ENABLED=false` nele também. O delay é configurável por `FAULT_DELAY_MS` (1–60000 ms). Para gerar timeout entre Order e catálogo, use delay maior que o timeout de leitura de Order (2000 ms). O timeout do gateway (10000 ms) permite que Order devolva seu próprio erro. Não há retry, fallback ou circuit breaker.

Salve os logs separadamente para o cenário sem centralização:

```bash
docker compose logs --no-color --no-log-prefix gateway > experiments/results/gateway.log
docker compose logs --no-color --no-log-prefix order-service > experiments/results/order-service.log
docker compose logs --no-color --no-log-prefix user-service > experiments/results/user-service.log
docker compose logs --no-color --no-log-prefix product-service > experiments/results/product-service.log
```

Os eventos da aplicação são JSON, incluindo stack trace como campo. Mensagens do lançador Java podem aparecer fora de JSON. `scripts/smoke.py --check-logs` ignora essas linhas e verifica os campos de correlação nos quatro serviços. Os resultados locais não são versionados por padrão.
