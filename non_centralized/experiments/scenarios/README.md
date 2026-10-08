# Cenários de falha

Os scripts desta pasta chamam o executor comum e preservam os mesmos controles de preparação, lock, registro e restauração. Consulte [experiments/README.md](../README.md) para requisitos, contratos, resultados e recuperação.

| Script | Falha |
|---|---|
| `E01-invalid-request.sh` | Quantidade inválida no pedido |
| `E02-database-unavailable.sh` | Parada real de `products-db` |
| `E03-service-timeout.sh` | Atraso GET no Product, timeout no Order |
| `E04-internal-error.sh` | Exceção interna no Product |
| `E05-service-unavailable.sh` | Parada real de `product-service` |

```bash
./experiments/run-experiment.sh E02
./experiments/scenarios/E02-database-unavailable.sh
```

Se o acesso ao Docker exigir sudo, coloque `sudo` antes do comando escolhido. Execute apenas um cenário por vez.

## Mecanismos adicionais para smoke

Os tipos abaixo continuam disponíveis para verificações de desenvolvimento, fora do catálogo E01–E05:

| `X-Fault-Type` | Comportamento na origem | Pedido com alvo no Product |
|---|---|---|
| `database` | Exceção de acesso a dados simulada, 503 | 502, `DOWNSTREAM_ERROR` |
| `not-found` | Recurso ausente simulado, 404 | 422, `PRODUCT_NOT_FOUND` |
| `invalid-response` | GET retorna representação incompleta, 200 | 502, `INVALID_DOWNSTREAM_RESPONSE` |

`database` não desconecta PostgreSQL e não substitui E02. Todos os tipos exigem `FAULT_ENABLED=true` e `X-Fault-Service` igual ao serviço alvo. Não alteram configurações globais entre requisições.
