# Base de microsserviços para o TCC

Este diretório é a **Parte 2, com logs centralizados**. Execute os comandos abaixo dentro de `centralized/`. A aplicação é idêntica à Parte 1; Fluent Bit, Loki e Grafana estão em `observability/`.

```bash
sudo env FAULT_ENABLED=true docker compose up --build -d --wait
sudo python3 scripts/observability.py
sudo ./experiments/run-experiment.sh E02
```

Grafana: http://localhost:3000, usuário `admin`, senha inicial `tcc-local`. Em **Explore**, selecione **Loki**, ajuste o intervalo e consulte:

```logql
{job="tcc"} | json | traceId="IDENTIFICADOR_DA_EXECUCAO"
```

O Data Source e o dashboard são provisionados automaticamente. Os volumes de Loki, Grafana e offsets do Fluent Bit são preservados pelo reset. O wrapper verifica a infraestrutura antes da injeção e a entrega dos eventos depois da restauração. Consulte [observability/README.md](observability/README.md) para coleta, parsing, labels, armazenamento, consultas, limites e protocolo experimental, e o [README da raiz](../README.md) para alternar os ambientes.

Aplicação experimental simples para estudar diagnóstico de erros por logs. Implementa criação e consulta de usuários, produtos e pedidos, comunicação HTTP síncrona, persistência independente, logs JSON e falhas controladas.

O fluxo principal é `cliente → gateway → order-service → user-service / product-service`. Somente Order acessa `orders_db`; User e Product acessam seus respectivos bancos. O gateway encaminha as respostas sem regras de negócio. Ele usa Spring Web e RestClient, evitando adicionar Spring Cloud para as três rotas fixas desta base.

## Organização

Existe um único **`pom.xml`** na raiz deste cenário e uma única pasta **`src/`**. Os pacotes Java são `common`, `gateway`, `order`, `product` e `user`.

```text
.
├── pom.xml                         # Dependências, testes e quatro executáveis
├── src/
│   ├── main/
│   │   ├── java/
│   │   │   ├── common/
│   │   │   ├── gateway/
│   │   │   ├── user/
│   │   │   ├── product/
│   │   │   └── order/
│   │   └── resources/
│   │       ├── common.properties
│   │       ├── services/
│   │       │   ├── gateway/application.properties
│   │       │   ├── user-service/application.properties
│   │       │   ├── product-service/application.properties
│   │       │   └── order-service/application.properties
│   │       └── db/migration/
│   │           ├── user/V1__create_users.sql
│   │           ├── product/V1__create_products.sql
│   │           └── order/V1__create_orders.sql
│   └── test/java/                  # Mesmos cinco pacotes
├── target/                         # Classes, relatórios e JARs; ignorado pelo Git
├── Dockerfile
├── compose.yaml
├── scripts/
│   ├── smoke.py
│   ├── observability.py            # Disponibilidade e entrega ao Loki
│   └── test_observability.py
├── observability/
│   ├── fluent-bit/
│   ├── loki/
│   └── grafana/                    # Provisioning e dashboard
└── experiments/
    ├── runner.py                   # Executor Python; biblioteca padrão
    ├── centralized_runner.py       # Verificações antes/depois da injeção
    ├── run-experiment.sh
    ├── reset-environment.sh
    ├── test_runner.py
    ├── scenarios/
    └── results/
```

### Organização do build e das configurações

O projeto usa **um único módulo Maven**. A estrutura anterior associava a mesma pasta de fontes a cinco projetos, fazendo o servidor Java do VS Code atribuir arquivos ao projeto errado e perder a resolução de dependências. O POM único permite ao Maven e ao editor usar a estrutura padrão `src/main/java` e `src/test/java`.

Java 21 e Spring Boot 4.1.1 foram preservados. O build gera quatro JARs executáveis, cada um com sua classe principal. Eles compartilham o código e as dependências empacotados, mas cada processo inicializa apenas os componentes do pacote de seu serviço. `common` contém a infraestrutura compartilhada; os serviços mantêm bancos e comunicação HTTP independentes.

**Properties:** cada classe `*Application` seleciona `classpath:/services/<serviço>/` como localização adicional de configuração antes de iniciar o Spring. As quatro configurações mantêm portas, URLs e bancos próprios e importam `common.properties`. Não é necessário selecionar um perfil. O gateway desabilita as autoconfigurações de banco, JPA e Flyway, pois não utiliza persistência.

**Flyway:** cada serviço de domínio usa `spring.flyway.locations=classpath:db/migration/<pacote>`. Os nomes, versões `V1` e conteúdos dos scripts foram preservados. Cada processo executa apenas as migrações de sua location, em seu próprio banco.

O Dockerfile copia `target/microservices-1.0.0-SNAPSHOT-<serviço>.jar`. O Compose continua usando o contexto de build da raiz e os mesmos volumes PostgreSQL. O smoke test e o catálogo de falhas mantêm os mesmos comandos.

Tecnologias: Java 21, Spring Boot 4.1.1, Spring Data JPA, Flyway e PostgreSQL 17. A infraestrutura de centralização utiliza Fluent Bit 5.1.3, Loki 3.7.8 e Grafana 13.2.3, adicionados somente neste cenário.

## Executar

Requisitos: Docker com Compose. Para compilar ou testar fora dos containers: JDK 21 e acesso ao Maven Central na primeira execução. O smoke test utiliza Python 3, sem pacotes adicionais.

Na raiz:

```bash
docker compose up --build -d --wait
python3 scripts/smoke.py --check-logs
```

A API fica em `http://localhost:8080/api`. O primeiro build baixa dependências e imagens. Os bancos mantêm dados em três volumes independentes. As migrações Flyway criam o schema automaticamente; Hibernate apenas valida o schema. Não há dados pré-carregados.

```bash
docker compose ps
docker compose logs -f order-service
docker compose down
```

`down` preserva os volumes. Para um novo experimento com bancos vazios, `docker compose down -v` **apaga os dados locais**.

Opcionalmente copie `.env.example` para `.env` e ajuste os valores. As credenciais padrão `tcc/tcc` são do ambiente experimental local; os bancos e o gateway são publicados apenas em `127.0.0.1`. Os serviços de domínio ficam na rede interna do Compose.

## Fluxo mínimo

Em ambiente vazio, os primeiros IDs serão 1; em ambiente reutilizado, use os IDs retornados pelas respostas.

```bash
curl -i http://localhost:8080/api/users \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ricardo","email":"ricardo@example.com"}'

curl -i http://localhost:8080/api/products \
  -H 'Content-Type: application/json' \
  -d '{"name":"Livro","description":"Produto de teste","price":19.95,"stock":10}'

curl -i http://localhost:8080/api/orders \
  -H 'Content-Type: application/json' \
  -H 'X-Trace-Id: pedido-experimental-001' \
  -d '{"userId":1,"items":[{"productId":1,"quantity":2}]}'

curl -i http://localhost:8080/api/orders/1
curl -i 'http://localhost:8080/api/orders?userId=1'
```

O pedido retorna HTTP 201, status `CREATED`, total `39.90` e itens com preço unitário e subtotal. O serviço consulta usuário e produtos antes de gravar; uma falha aborta a transação. Preços são calculados com `BigDecimal` e armazenados como snapshot no pedido. Não existem chaves estrangeiras entre bancos.

O estoque é **consultado e validado**, sem reserva ou baixa. Cada produto aparece uma vez no pedido; quantidades devem estar entre 1 e 10000, com até 100 itens. Essa base não implementa pagamento, autenticação, carrinho, entrega ou processamento posterior do pedido. As listagens são simples, sem paginação, para pequenos conjuntos de dados experimentais.

| Método | Endpoint externo |
|---|---|
| POST / GET | `/api/users` |
| GET | `/api/users/{id}` |
| POST / GET | `/api/products` |
| GET | `/api/products/{id}` |
| GET | `/api/products/{id}/availability` |
| POST / GET | `/api/orders` |
| GET | `/api/orders/{id}` |
| GET | `/api/orders?userId={id}` |

Internamente, os endpoints usam os mesmos caminhos sem `/api`. O health check fica em `/actuator/health` em cada aplicação.

## Logs e erros

O cabeçalho `X-Trace-Id` é propagado do gateway às chamadas de Order e devolvido na resposta. Quando ausente ou inválido, o serviço gera um UUID. IDs recebidos aceitam 1–64 caracteres de letras, números, `.`, `_` e `-`. O contexto de logging é limpo ao finalizar cada requisição.

Os logs JSON no stdout contêm `timestamp`, `level`, `service`, `message` e, durante requisições, `traceId` e `operation`. Eventos de inicialização não têm contexto de requisição. Campos como `orderId`, `productId`, `downstreamStatus`, `durationMs`, `errorCode`, `details` de validação e `stack_trace` ajudam a diagnosticar falhas. Os logs não registram o corpo das requisições nem emails de usuários. O cenário de injeção fica nos metadados do operador, sem marcadores explícitos de injeção nos logs.

Formato de erro:

```json
{
  "timestamp": "2026-10-02T12:00:00Z",
  "status": 422,
  "code": "PRODUCT_NOT_FOUND",
  "message": "Referenced resource does not exist in product-service",
  "traceId": "pedido-experimental-001",
  "details": []
}
```

Validação retorna 400; recurso local ausente retorna 404; conflito de dados retorna 409; referência de pedido inexistente ou estoque insuficiente retorna 422. Order distingue resposta inválida/erro remoto (502) e timeout (504). Falhas de banco no serviço de origem retornam 503. O gateway preserva status e corpo recebidos e ajusta `Location` para `/api/...`.

Os clientes têm timeout de conexão de 1000 ms e leitura de 2000 ms. A leitura no gateway é de 10000 ms para permitir que Order informe falhas nos serviços consultados. Não são adicionados mecanismos de recuperação automática.

A aquisição de conexão no pool dos bancos tem limite padrão de 1000 ms, configurável com `DB_CONNECTION_TIMEOUT_MS`, para dar margem ao Order receber o erro antes de seu timeout HTTP. Esse limite não cobre toda consulta SQL.

## Experimentos de erros controlados

A injeção por requisição é desabilitada por padrão e ativada com `FAULT_ENABLED=true`. E02 e E05 usam parada real do banco/serviço; E03 e E04 usam cabeçalhos direcionados ao Product. O atraso atua somente em consultas GET, e o timeout é produzido pelo cliente HTTP do Order.

```bash
FAULT_ENABLED=true docker compose up --build -d --wait
./experiments/run-experiment.sh E01
./experiments/run-experiment.sh E02
./experiments/run-experiment.sh E03
./experiments/run-experiment.sh E04
./experiments/run-experiment.sh E05
./experiments/reset-environment.sh
```

Se o Docker exigir sudo, use `sudo env FAULT_ENABLED=true docker compose up --build -d --wait` na preparação e `sudo ./experiments/run-experiment.sh E02` para executar. O reset também aceita sudo.

O executor cria dados válidos, captura o `traceId` gerado pela aplicação, salva cada execução em `experiments/results/<cenário>/<run-id>/` e restaura o recurso afetado mesmo em falhas ou interrupções tratáveis. Verifica ausência de pedidos persistidos e alterações de estoque. Os logs permanecem separados por serviço e o diagnóstico humano é feito posteriormente. O reset preserva volumes e desabilita a injeção nos processos, sem modificar `.env`.

Consulte [experiments/README.md](experiments/README.md) para contratos HTTP e restauração e [observability/README.md](observability/README.md) para disponibilidade e entrega ao Loki.

## Desenvolvimento e testes

```bash
./mvnw clean verify
python3 -m unittest discover -s experiments -p 'test_*.py' -v
```

O build gera os quatro executáveis abaixo, além do JAR base `microservices-1.0.0-SNAPSHOT.jar`, usado no empacotamento:

```text
target/microservices-1.0.0-SNAPSHOT-gateway.jar
target/microservices-1.0.0-SNAPSHOT-user-service.jar
target/microservices-1.0.0-SNAPSHOT-product-service.jar
target/microservices-1.0.0-SNAPSHOT-order-service.jar
```

Os testes exercitam HTTP real das aplicações, validação, persistência e migrações em H2 no modo PostgreSQL. Os testes iniciam a classe principal de cada serviço para validar também sua seleção de configuração. Os testes de Order e gateway usam servidores HTTP locais controlados para testar chamadas, erros, timeout e propagação dos cabeçalhos. H2 é exclusivo dos testes; a execução padrão usa PostgreSQL. Para validar também PostgreSQL, containers e correlação entre as quatro aplicações, execute o smoke test no Compose.

Também é possível iniciar apenas os bancos e executar aplicações em terminais separados:

```bash
docker compose up -d users-db products-db orders-db
./mvnw package -DskipTests
java -jar target/microservices-1.0.0-SNAPSHOT-user-service.jar
java -jar target/microservices-1.0.0-SNAPSHOT-product-service.jar
java -jar target/microservices-1.0.0-SNAPSHOT-order-service.jar
java -jar target/microservices-1.0.0-SNAPSHOT-gateway.jar
```

Fora do Compose, as portas padrão são 8081 (User), 8082 (Product), 8083 (Order) e 8080 (gateway). Os bancos usam 5431, 5432 e 5433. URLs, credenciais, porta e timeouts podem ser ajustados por `DB_URL`, `DB_USER`, `DB_PASSWORD`, `PORT`, `USER_SERVICE_URL`, `PRODUCT_SERVICE_URL`, `ORDER_SERVICE_URL`, `HTTP_CONNECT_TIMEOUT_MS` e `HTTP_READ_TIMEOUT_MS`.

O JSON utiliza o [logging estruturado nativo do Spring Boot](https://docs.spring.io/spring-boot/4.0/reference/features/logging.html), com MDC para correlação. As chamadas HTTP utilizam [RestClient do Spring Framework](https://docs.spring.io/spring-framework/reference/integration/rest-clients.html).


## Importação no VS Code

Abra a raiz que contém `pom.xml`. Após alterar a estrutura do projeto, execute **Java: Clean Java Language Server Workspace** na paleta de comandos (`Ctrl+Shift+P`) e confirme o reinício. Isso remove o índice antigo e importa o projeto Maven atual. A opção `java.configuration.updateBuildConfiguration` com valor `automatic` permite atualizar as dependências quando o POM mudar.

As classes devem aparecer no projeto `microservices`. Os antigos projetos `demo`, `common` e `*-service` não fazem mais parte da estrutura Maven.

## Validação

`./mvnw clean verify` passou com 15 testes Java. Os 14 testes Python do executor e os seis testes do verificador de entrega passaram. A aplicação mantém paridade em 55 arquivos com a Parte 1; os dois arquivos Compose passaram na validação de configuração.

E01–E05 passaram com os quatro JARs, três PostgreSQL reais e os binários oficiais Fluent Bit/Loki/Grafana executados em processos locais. Foram conferidos os contratos HTTP, restauração, invariantes de dados, campos dos eventos entregues ao Loki, consulta do trace E02 pelo Grafana e cinco consultas do dashboard. O teste de transporte recompôs fragmentos Docker e preservou stack traces maiores que 40 KB.

E01–E04 passaram em Compose, incluindo restauração, invariantes e entrega ao Loki. E02 conferiu os 33 eventos nos quatro serviços. E05 parou Product e retornou 504 / `DOWNSTREAM_TIMEOUT`, divergindo do contrato previsto 502 / `DOWNSTREAM_UNAVAILABLE`; o Order registrou timeout de conexão, e a restauração/invariantes passaram. Essa divergência permanece aberta. O acesso direto ao daemon pelo agente continua exigindo senha do sudo. Veja o [relatório de validação](observability/VALIDATION.md) para evidências, método, limites e comandos para conferir o runtime Compose.
