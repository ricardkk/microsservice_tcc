# Microsserviços — comparação de logs para o TCC

Este repositório contém os dois cenários do estudo de diagnóstico de falhas por logs. A aplicação, os contratos HTTP, as migrações, os timeouts e os mecanismos E01–E05 são iguais. A Parte 2 acrescenta Fluent Bit, Loki e Grafana para disponibilizar os logs centralmente.

```text
microsservice_tcc/
├── non_centralized/       # Parte 1: aplicação e logs separados
│   ├── pom.xml, mvnw, Dockerfile, compose.yaml
│   ├── src/main/java/    # common, gateway, user, product, order
│   ├── scripts/
│   └── experiments/
├── centralized/           # Parte 2: mesma aplicação + centralização
│   ├── pom.xml, mvnw, Dockerfile, compose.yaml
│   ├── src/main/java/
│   ├── scripts/
│   ├── experiments/
│   └── observability/
│       ├── fluent-bit/
│       ├── loki/
│       └── grafana/
├── scripts/check-parity.py
└── tcc.sh                 # Escolhe o projeto para comandos Compose
```

Cada cenário é um projeto Maven independente, com um único POM e sua própria `src/`. O Git permanece na raiz. Abra a pasta do cenário no editor para trabalhar no respectivo projeto Java.

Consulte o [roteiro completo de testes e coleta](ROTEIRO_TESTES_COLETA.md) para builds, testes Python, smoke, E01–E05 nos dois ambientes, consulta dos logs, exportação do CSV e preservação dos resultados.

## Executar os cenários

Requisitos: Java 21 para builds locais, Python 3 e Docker Engine para Linux com Compose. A leitura passiva dos logs requer o driver Docker `json-file`, configurado igualmente nas quatro aplicações de ambos os cenários.

Execute um ambiente por vez: eles usam a mesma API em `127.0.0.1:8080` e as mesmas portas dos bancos. Os nomes dos projetos e volumes são distintos. A Parte 1 conserva o nome `tcc-microservices` para continuar usando seus volumes existentes; a Parte 2 usa `tcc-microservices-centralized`.

Parte 1, na raiz:

```bash
sudo env FAULT_ENABLED=true ./tcc.sh non_centralized up --build -d --wait
sudo ./non_centralized/experiments/run-experiment.sh E02
sudo ./tcc.sh non_centralized down
```

Parte 2:

```bash
sudo env FAULT_ENABLED=true ./tcc.sh centralized up --build -d --wait
sudo python3 centralized/scripts/observability.py
sudo ./centralized/experiments/run-experiment.sh E02
sudo ./tcc.sh centralized down
```

Se Docker funcionar sem sudo, retire o prefixo. Também é possível entrar na pasta do cenário e usar `docker compose` diretamente. O seletor sempre executa os comandos no diretório correto.

`down` preserva os dados. Cada ambiente tem seus próprios resultados em `<ambiente>/experiments/results/<cenário>/<run-id>/`, ignorados pelo Git. Os dados anteriores da Parte 1 permanecem disponíveis com o mesmo nome Compose. Não use `down -v` durante a coleta experimental: ele remove os volumes.

## Investigar os logs

Na Parte 1, use os arquivos individuais da execução ou `docker compose logs` dentro de `non_centralized/`.

Na Parte 2, acesse [Grafana](http://localhost:3000), usuário `admin`, senha inicial `tcc-local`. Entre em **Explore**, selecione **Loki** e ajuste o intervalo à execução. O identificador está no `metadata.json` e no `response.json` da execução.

```logql
{job="tcc", service="product-service"}
{job="tcc"} | json | level="ERROR"
{job="tcc"} | json | traceId="IDENTIFICADOR_DA_EXECUCAO"
```

O dashboard **TCC — Visão geral dos logs** apresenta contagens e logs recentes. Explore é a ferramenta principal do protocolo. Os metadados com a falha conhecida ficam com o operador; forneça ao avaliador apenas a evidência definida na metodologia.

## Verificar e manter a comparação

```bash
python3 scripts/check-parity.py
cd non_centralized
./mvnw clean verify
python3 -m unittest discover -s experiments -p 'test_*.py' -v
cd ../centralized
./mvnw clean verify
python3 -m unittest discover -s experiments -p 'test_*.py' -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

O verificador compara fontes Java, recursos, testes, POM, Dockerfile, wrapper Maven, smoke e implementação dos experimentos. Mudanças funcionais devem ser aplicadas aos dois cenários. Os wrappers centralizados acrescentam apenas verificações de infraestrutura e entrega dos logs; não alteram a injeção.

Na revisão de 12/10/2026, passaram 16 testes Java por cenário, 14 testes Python do executor por cenário e seis de observabilidade. A paridade e os dois Compose foram validados. A classificação de timeout de conexão foi corrigida para E05 retornar 502 / `DOWNSTREAM_UNAVAILABLE`; timeout de resposta mantém 504 / `DOWNSTREAM_TIMEOUT`. Os resultados Docker anteriores permanecem preservados e a repetição com imagens reconstruídas ainda precisa confirmar a correção em runtime. Veja o [relatório e os limites da validação](centralized/observability/VALIDATION.md).

As fontes já produzem JSON e geram/propagam `traceId`. PostgreSQL não recebe esse identificador automaticamente; a correlação exigida abrange os processos Java. As falhas dos bancos são diagnosticadas pelas exceções registradas pelas aplicações.

## Arquivos e decisões da Parte 2

O trabalho anterior foi movido com `git mv` para `non_centralized/`. A cópia em `centralized/` mantém o mesmo POM único, código Java, recursos e experimentos. O repositório contém dois projetos independentes para permitir executar cada cenário a partir da própria pasta.

| Arquivos criados ou ajustados | Papel |
|---|---|
| `README.md`, `tcc.sh`, `scripts/check-parity.py` | Seleção dos cenários, instruções e comparação dos arquivos compartilhados |
| `.gitignore`, `.gitattributes` | Ignorar builds/resultados das duas pastas e preservar finais de linha dos wrappers |
| `*/compose.yaml` | Mesmo driver de logs nas aplicações; projetos/volumes separados; infraestrutura apenas na Parte 2 |
| `centralized/observability/fluent-bit/` | Coleta passiva, recomposição Docker, parsing JSON e envio ao Loki |
| `centralized/observability/loki/loki-config.yml` | Armazenamento local persistente em um processo |
| `centralized/observability/grafana/` | Data Source e dashboard provisionados |
| `*/experiments/runner.py`, `*/experiments/test_runner.py` | Pontos opcionais de verificação e teste da restauração antes da checagem de entrega |
| `centralized/experiments/centralized_runner.py`, wrappers shell | Verificar infraestrutura antes e entrega depois, mantendo os mesmos cenários |
| `centralized/scripts/observability.py`, `test_observability.py` | Conferir disponibilidade, campos/eventos e correlação recebidos no Loki |
| READMEs e HELP de cada cenário | Comandos executados no diretório correto e orientação de investigação |

Detalhes: [Parte 1](non_centralized/README.md), [Parte 2](centralized/README.md), [experimentos da Parte 1](non_centralized/experiments/README.md) e [centralização](centralized/observability/README.md).
