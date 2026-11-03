# 3 METODOLOGIA

O estudo foi desenvolvido por meio da implementação de uma aplicação de referência e da execução de erros controlados em dois ambientes, com posterior comparação dos registros produzidos. A avaliação reuniu validação técnica das execuções e análise qualitativa retrospectiva das evidências, acompanhada de contagens descritivas dos eventos. O propósito foi examinar a correspondência entre as condições provocadas e suas manifestações nos logs, considerando a disponibilização local e centralizada desses registros.

## 3.1 Delineamento e delimitação do estudo

A comparação considerou uma configuração sem infraestrutura centralizada de logs, denominada non_centralized, e outra acrescida de Fluent Bit, Loki e Grafana, denominada centralized. Nos dois ambientes, a aplicação produziu logs estruturados e utilizou o mesmo mecanismo de correlação de requisições. A diferença arquitetural investigada correspondeu à inclusão da infraestrutura de coleta, armazenamento e consulta centralizada.

Foram definidos cinco casos, identificados como E01 a E05, executados uma vez em cada ambiente. O corpus principal da avaliação corresponde às dez execuções preservadas em coleta/rodada-01, realizadas em 14 de outubro de 2026. Registros anteriores de desenvolvimento e correção não foram contabilizados como repetições desses casos. Os relatórios de testes automatizados foram utilizados como evidências complementares de validação da implementação.

Os critérios de interpretação foram aplicados retrospectivamente aos arquivos preservados, com conhecimento das condições provocadas pelo executor. A investigação não correspondeu a uma avaliação cega com participantes. Não foram registrados tempos de investigação humana, esforço de interação ou taxas de acerto de investigadores. Por essa razão, o delineamento permite discutir os casos documentados e a disponibilização das evidências, sem estimar ganhos de desempenho humano ou significância estatística.

A utilização de condições conhecidas encontra apoio na discussão de Cândido, Aniche e van Deursen (2021, p. 15) sobre o emprego de injeção de falhas para avaliar se os logs manifestam problemas introduzidos no sistema. Os cinco casos deste trabalho foram definidos para a aplicação de referência; não correspondem a uma reprodução de uma lista de cenários estabelecida pelo artigo.

## 3.2 Arquitetura da aplicação de referência

A aplicação simula operações de comércio eletrônico envolvendo usuários, produtos e pedidos. Seu domínio foi mantido simples para concentrar a avaliação na geração e na interpretação dos logs. A implementação utiliza Java 21 e Spring Boot 4.1.1, com persistência em PostgreSQL e execução dos componentes em contêineres coordenados por Docker Compose.

A arquitetura possui quatro processos de aplicação. O gateway recebe as requisições externas e as encaminha conforme o recurso solicitado. O user-service mantém os dados de usuários, o product-service mantém os dados de produtos e o order-service realiza as operações de pedidos. Os três serviços de negócio utilizam bancos próprios, denominados users-db, products-db e orders-db. O gateway não possui banco de dados de negócio.

No fluxo utilizado pelos experimentos, uma requisição POST /api/orders é recebida pelo gateway e encaminhada ao order-service. O serviço de pedidos valida a entrada, consulta o user-service para verificar o usuário e solicita ao product-service os dados do produto. Após as verificações de negócio, o fluxo normal permite a persistência do pedido. Nos casos experimentais, a condição provocada interrompe esse processamento antes da criação de um pedido válido.

As duas variantes estão organizadas como projetos Maven independentes dentro do mesmo repositório. Cada variante possui um único arquivo de configuração de build e uma árvore de fontes que reúne os pacotes common, gateway, order, product e user. O empacotamento produz aplicações executáveis separadas para os quatro processos. Essa organização do código permite compartilhar a instrumentação sem exigir que os serviços sejam executados no mesmo processo.

Os ambientes possuem projetos Compose e volumes distintos e utilizam as mesmas portas externas da aplicação e dos bancos. Sua execução ocorre separadamente. A configuração do repositório acrescenta ao ambiente centralized os contêineres de observabilidade, preservando a implementação dos serviços de negócio e dos mecanismos experimentais compartilhados.

Não foram acrescentadas políticas de repetição automática de requisições de negócio, circuit breakers ou respostas alternativas. Foram mantidos o tratamento de exceções e os limites de espera necessários para registrar e apresentar os erros. A restauração executada pelos scripts após os casos foi um procedimento de controle experimental, separado do atendimento da requisição de negócio.

## 3.3 Instrumentação e infraestrutura de logs

As aplicações foram configuradas para emitir JSON na saída padrão. Os registros de requisição incluem campos como timestamp, level, service, traceId, operation e message. Conforme a ocorrência, também são registrados status, códigos de erro, detalhes de validação, informações da dependência chamada e exceções. Eventos de inicialização e mensagens externas ao contexto de uma requisição podem não conter todos esses campos.

No fluxo avaliado, o gateway gera um identificador quando não recebe um X-Trace-Id válido. O identificador é armazenado no contexto de logging, incluído na resposta e propagado nas chamadas HTTP subsequentes. Assim, os eventos de uma requisição podem ser associados entre os serviços. Esse mecanismo foi mantido nos dois ambientes; a correlação dos registros de origem não foi introduzida exclusivamente pela centralização.

Em non_centralized, os registros permanecem disponíveis nas saídas dos contêineres e nas cópias por serviço preservadas pelo executor. Em centralized, o Fluent Bit também lê os arquivos de logs dos contêineres, recompõe fragmentos do formato Docker, interpreta o conteúdo JSON e encaminha os eventos ao Loki. Os filtros de coleta selecionam os quatro processos de aplicação do ambiente centralizado. Os logs dos bancos e dos próprios componentes de observabilidade não constituem o corpus de requisições analisado.

O Loki recebe e armazena os eventos, e o Grafana utiliza uma fonte de dados provisionada para consultá-los. A configuração emprega labels para identificar o conjunto de logs e o serviço. O traceId é preservado no conteúdo do evento e utilizado como critério de filtragem, sem ser configurado como label indexado de cada requisição. O armazenamento do Loki utiliza um volume persistente local.

O executor centralizado verifica a disponibilidade de Fluent Bit, Loki e Grafana e a existência da fonte de dados e do dashboard provisionados. Após a execução e a restauração do caso, uma verificação adicional consulta diretamente a API do Loki para localizar os eventos associados ao traceId experimental. A verificação procura, nos resultados, os serviços participantes e os valores dos campos dos eventos de origem.

O resumo dessa conferência é salvo no campo observability do arquivo de metadados. A rotina não registra automaticamente o retorno bruto completo do Loki nem um histórico de investigação humana no Grafana. A distinção entre infraestrutura e interpretação segue o ciclo de vida dos logs discutido por Cândido, Aniche e van Deursen (2021).

## 3.4 Definição dos cenários controlados

Todos os casos utilizaram uma requisição de criação de pedido encaminhada pelo gateway. Para cada execução, o executor preparou um usuário e um produto específicos, registrou o estado inicial e aplicou a condição correspondente ao cenário. A quantidade inicial de estoque foi dez, e o usuário experimental não possuía pedidos antes da requisição avaliada.

No caso E01, a quantidade de um item foi definida como -5. A condição foi aplicada ao corpo da requisição, com resposta esperada HTTP 400 e código VALIDATION_ERROR. Esse caso representa uma entrada inválida rejeitada pela validação, e não uma indisponibilidade de infraestrutura. Sua inclusão permite examinar um processamento encerrado antes das consultas aos serviços de usuários e produtos.

No caso E02, o executor interrompeu o contêiner products-db antes de enviar o pedido. A indisponibilidade da dependência de persistência deveria produzir um erro no product-service, posteriormente propagado pelo order-service e pelo gateway. A resposta externa esperada foi HTTP 502, com código DOWNSTREAM_ERROR.

No caso E03, foi aplicado um atraso controlado de 5.000 ms ao atendimento da consulta de leitura no product-service. O limite de leitura do order-service foi de 2.000 ms, de modo que a espera do chamador terminasse antes da conclusão da operação remota. O resultado externo esperado foi HTTP 504, com código DOWNSTREAM_TIMEOUT. O atraso não determinou o encerramento do processamento no Product, permitindo observar sua eventual conclusão tardia.

No caso E04, o mecanismo controlado provocou uma IllegalStateException no product-service durante o atendimento da consulta. O serviço deveria registrar o erro interno e responder com HTTP 500, enquanto a resposta esperada na borda da aplicação foi HTTP 502, com código DOWNSTREAM_ERROR.

No caso E05, o contêiner product-service foi interrompido antes do envio da requisição de pedido. A impossibilidade de comunicação deveria ser registrada pelo order-service, com resposta externa HTTP 502 e código DOWNSTREAM_UNAVAILABLE. Como o Product estava parado, não se esperavam eventos de atendimento dessa requisição produzidos por ele.

Os mecanismos de atraso e exceção interna exigem habilitação explícita da injeção e identificação do serviço e do tipo de condição por cabeçalhos HTTP. A interrupção de banco e de serviço foi realizada pelo executor por meio do Docker Compose. Além dos prazos de leitura do Order e do atraso no Product, os metadados registram 1.000 ms para obtenção de conexão ao banco, 10.000 ms para leitura pelo gateway e 15.000 ms como limite da requisição enviada pelo executor.

## 3.5 Procedimento de execução e coleta

Antes da requisição experimental, o executor verificou a disponibilidade dos componentes e preparou os dados de usuário e produto. Foram registrados os identificadores desses recursos, o estoque inicial e a lista de pedidos associados ao usuário. Em seguida, foi aplicada a condição do caso e enviada a requisição POST /api/orders. O executor preservou o resultado HTTP, o corpo da resposta e o identificador de correlação retornado pela aplicação.

Os registros de origem foram coletados por docker compose logs, separadamente para gateway, order-service, user-service e product-service, a partir do início da requisição experimental. Esse procedimento foi utilizado nos dois ambientes. No caso E03, o executor aguardou um intervalo adicional antes da coleta para incluir os eventos de conclusão tardia da consulta ao Product.

Após a resposta e a coleta, o recurso interrompido foi reiniciado quando necessário. A recuperação foi verificada por consultas de disponibilidade e leituras funcionais. Também foram conferidos o estoque e os pedidos associados aos recursos experimentais. O objetivo desses controles foi identificar alterações de dados ou problemas de restauração que comprometessem a execução. As consultas de recuperação não repetiram a requisição experimental de criação do pedido.

Cada execução foi preservada em uma pasta identificada pelo caso e por um identificador próprio de rodada. O arquivo metadata.json contém parâmetros, horários, identificadores de imagens, resposta esperada e observada e resultados das verificações. O arquivo response.json preserva a resposta recebida pelo cliente. A subpasta logs reúne as cópias dos registros de cada aplicação. Os arquivos de terminal documentam as etapas relatadas pelo executor e foram diferenciados dos logs de negócio.

No ambiente centralized, a verificação adicional de entrega ao Loki foi executada após a restauração. Os campos events e sourceEventsVerified registram, respectivamente, a contagem retornada pela consulta e a quantidade de eventos de origem submetidos à comparação. Esses valores descrevem uma conferência delimitada pelo traceId e pelo intervalo temporal da requisição.

## 3.6 Procedimento de análise das evidências

A análise iniciou pela leitura dos metadados para localizar o caso, sua resposta e o traceId correspondente. Nos arquivos por serviço, foram selecionados os eventos que continham esse identificador. As mensagens foram examinadas em conjunto com a operação, o componente, o status, os códigos de erro e as exceções, para reconstruir o percurso observado da requisição.

Os critérios compreenderam a identificação da categoria do erro, a localização do componente ou dependência envolvida e a interpretação de sua propagação até o cliente. A resposta HTTP foi confrontada com as evidências internas, evitando tratá-la isoladamente como explicação suficiente. A sequência temporal auxiliou a interpretação, juntamente com as informações das chamadas, sem ser utilizada como prova autônoma de causalidade.

Em seguida, as interpretações foram confrontadas com a condição conhecida da execução e com o caso correspondente no outro ambiente. A informação de que um contêiner foi deliberadamente interrompido pertence ao registro do procedimento experimental; sua ocorrência não foi presumida apenas porque um log indicava falha de comunicação. Essa separação permitiu distinguir a categoria identificável nos registros do mecanismo exato utilizado pelo operador.

As contagens de eventos e de serviços participantes foram utilizadas para descrever o corpus e conferir os registros examinados. A preservação no Loki foi avaliada a partir dos resumos históricos do verificador, em conjunto com seu procedimento de comparação. Os relatórios de testes da aplicação e da infraestrutura foram tratados como validação técnica complementar, sem serem convertidos em acertos de diagnóstico ou repetições dos cinco casos.
