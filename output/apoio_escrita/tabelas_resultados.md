# Tabelas derivadas da rodada de 14 de outubro de 2026

Dados lidos dos metadados e dos eventos com o traceId de cada execução. Os arquivos originais não foram alterados.

## Respostas observadas

| Caso | Sem centralização | Centralizado | Ambos coincidem com o esperado? |
|---|---|---|---|
| E01 | 400 / VALIDATION_ERROR | 400 / VALIDATION_ERROR | Sim |
| E02 | 502 / DOWNSTREAM_ERROR | 502 / DOWNSTREAM_ERROR | Sim |
| E03 | 504 / DOWNSTREAM_TIMEOUT | 504 / DOWNSTREAM_TIMEOUT | Sim |
| E04 | 502 / DOWNSTREAM_ERROR | 502 / DOWNSTREAM_ERROR | Sim |
| E05 | 502 / DOWNSTREAM_UNAVAILABLE | 502 / DOWNSTREAM_UNAVAILABLE | Sim |

A conformidade HTTP é um resultado técnico; não representa acerto de diagnóstico de um investigador.

## Eventos por requisição experimental

| Caso | Eventos sem centralização | Eventos centralizados nos arquivos de origem | Eventos de origem verificados no Loki |
|---|---:|---:|---:|
| E01 | 8 | 8 | 8 |
| E02 | 25 | 25 | 25 |
| E03 | 19 | 19 | 19 |
| E04 | 19 | 19 | 19 |
| E05 | 16 | 16 | 16 |
| Total | 87 | 87 | 87 |

A última coluna descreve a verificação histórica registrada nos metadados; não é uma nova consulta ao Loki.
As contagens não demonstram melhoria de diagnóstico, ausência geral de perdas ou entrega exatamente uma vez.

## Eventos por serviço no ambiente centralizado

| Caso | Gateway | Order | User | Product |
|---|---:|---:|---:|---:|
| E01 | 5 | 3 | 0 | 0 |
| E02 | 5 | 8 | 3 | 9 |
| E03 | 5 | 8 | 3 | 3 |
| E04 | 5 | 8 | 3 | 3 |
| E05 | 5 | 8 | 3 | 0 |

As contagens por serviço coincidiram nos dois ambientes nesta rodada.
Em E01, User e Product não foram chamados. Em E05, Product estava parado. Zeros não significam, por si só, perda na coleta.

## Fontes e interpretação das figuras

Figura 1: Sequência temporal do caso E03 nos dois ambientes (linha_tempo_E03.png e .svg).

Fonte: elaboração própria com dados experimentais de 14/10/2026.

O gateway retorna 504 aproximadamente dois segundos após receber a requisição. O Product conclui com 200 aproximadamente cinco segundos após o início. O mesmo padrão aparece nos dois ambientes.
A origem e os instantes exatos estão em origem_linha_tempo_E03.json. A figura representa uma execução por ambiente; não apresenta médias ou intervalos de confiança.

Figura 2: Distribuição dos eventos por serviço e caso experimental (eventos_por_servico.png e .svg).

Uma barra por caso representa a contagem por execução, coincidente nos dois ambientes; os ambientes não foram somados. As contagens e suas fontes estão em origem_eventos_por_servico.json.
Os valores descrevem eventos de log por serviço, não quantidades de erros ou acertos de diagnóstico.

## Registros de origem

- non_centralized, E01: `coleta/rodada-01/non_centralized/experiments/E01/20261014T120155418180Z-f3c5e00a/metadata.json`; trace `3e297d00-198b-4f6b-a239-a9a407f9eab1`.
- non_centralized, E02: `coleta/rodada-01/non_centralized/experiments/E02/20261014T120202903006Z-96330720/metadata.json`; trace `d5726edb-9b0f-459d-927e-182f1ddbc459`.
- non_centralized, E03: `coleta/rodada-01/non_centralized/experiments/E03/20261014T120218453075Z-8e08bd84/metadata.json`; trace `961ca731-db0c-4899-9d42-cc9b07cd47ca`.
- non_centralized, E04: `coleta/rodada-01/non_centralized/experiments/E04/20261014T120237684032Z-bd05c27f/metadata.json`; trace `571f5e83-f911-43f9-83fb-0626833849af`.
- non_centralized, E05: `coleta/rodada-01/non_centralized/experiments/E05/20261014T120243237364Z-d61a1ff8/metadata.json`; trace `07744452-8b78-4ccc-9941-9029d27d29f8`.
- centralized, E01: `coleta/rodada-01/centralized/experiments/E01/20261014T120740002093Z-e141437f/metadata.json`; trace `5a23ee8d-27b5-47c7-b978-3d23af4c8201`.
- centralized, E02: `coleta/rodada-01/centralized/experiments/E02/20261014T120805623624Z-3f687297/metadata.json`; trace `d5018a79-0a45-49fa-b29b-9c0f6a4b29f4`.
- centralized, E03: `coleta/rodada-01/centralized/experiments/E03/20261014T120819711645Z-212ebe32/metadata.json`; trace `b3952597-5ad1-49c0-9bf0-70e85495e6ad`.
- centralized, E04: `coleta/rodada-01/centralized/experiments/E04/20261014T120831142032Z-3b363ed7/metadata.json`; trace `b8afd45a-a241-4154-b316-4064403ff58e`.
- centralized, E05: `coleta/rodada-01/centralized/experiments/E05/20261014T120837047488Z-a1c1401e/metadata.json`; trace `cb012115-193b-4eba-a9c1-a02a0811b476`.
