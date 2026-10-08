# Comandos de desenvolvimento

Execute estes comandos dentro de `centralized/`. Na raiz do repositório, use `./tcc.sh centralized` para selecionar o Compose. A Parte 1 fica em `non_centralized/`.

Java 21, Spring Boot 4.1.1, um único `pom.xml` e uma única pasta `src/`. Os pacotes `common`, `gateway`, `order`, `product` e `user` ficam diretamente em `src/main/java/` e `src/test/java/`.

Build completo e testes:

```bash
./mvnw clean verify
```

Execução em containers e verificação do fluxo:

```bash
docker compose up --build -d --wait
python3 scripts/observability.py
python3 scripts/smoke.py --check-logs
```

Experimento individual e restauração:

```bash
FAULT_ENABLED=true docker compose up --build -d --wait
./experiments/run-experiment.sh E02
./experiments/run-experiment.sh E03
./experiments/reset-environment.sh
python3 -m unittest discover -s experiments -p 'test_*.py' -v
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Se Docker exigir sudo, use `sudo env FAULT_ENABLED=true docker compose up --build -d --wait` e execute os scripts com `sudo`. Veja [experiments/README.md](experiments/README.md) para os cinco cenários, resultados e limites de restauração.

Grafana: http://localhost:3000, usuário `admin`, senha inicial `tcc-local`. Em **Explore**, selecione **Loki**, ajuste o intervalo e consulte `{job="tcc"} | json | traceId="TRACE_DA_EXECUCAO"`. O trace fica em `metadata.json`. A entrega pode ser conferida novamente com `sudo python3 scripts/observability.py --metadata experiments/results/E02/EXECUCAO/metadata.json`. Consulte [observability/README.md](observability/README.md) para o fluxo, configuração e persistência.

Para executar as aplicações fora dos containers, inicie os bancos e use um terminal por serviço:

```bash
docker compose up -d users-db products-db orders-db
./mvnw package -DskipTests
java -jar target/microservices-1.0.0-SNAPSHOT-user-service.jar
java -jar target/microservices-1.0.0-SNAPSHOT-product-service.jar
java -jar target/microservices-1.0.0-SNAPSHOT-order-service.jar
java -jar target/microservices-1.0.0-SNAPSHOT-gateway.jar
```

Cada classe principal seleciona sua configuração em `src/main/resources/services/<serviço>/application.properties`. As migrações usam locations independentes em `src/main/resources/db/migration/{user,product,order}/`. O gateway não inicializa banco de dados.

Se o VS Code ainda mostrar imports inválidos após uma reorganização, abra a pasta `centralized/`, execute **Java: Clean Java Language Server Workspace** na paleta de comandos (`Ctrl+Shift+P`) e confirme o reinício. O servidor deve importar o projeto Maven `microservices` dessa pasta. A atualização automática do classpath pode ser ativada em `.vscode/settings.json` com `"java.configuration.updateBuildConfiguration": "automatic"`.

Veja o [README](README.md) e o [catálogo de cenários](experiments/scenarios/README.md).
