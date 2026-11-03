# 2 REFERENCIAL TEÓRICO

Esta seção apresenta os conceitos que fundamentam a análise de erros por logs em aplicações baseadas em microsserviços. São abordadas as características dessa arquitetura, os sinais de observabilidade, a estruturação e a correlação dos registros, a centralização de logs e a utilização de injeção de falhas em avaliações experimentais. Ao final, são discutidos trabalhos relacionados ao recorte adotado nesta pesquisa.

## 2.1 Microsserviços e propagação de erros

A arquitetura de microsserviços organiza uma aplicação em serviços com responsabilidades delimitadas, que se comunicam para realizar suas funcionalidades. Silva Neto (2023) apresenta essa organização como uma decomposição da aplicação em componentes que podem ser desenvolvidos e implantados separadamente. A execução de uma funcionalidade, entretanto, pode depender da interação entre vários desses componentes.

Essa dependência introduz situações que precisam ser consideradas no diagnóstico de erros. Uma operação pode ser interrompida por um problema no próprio serviço, pela indisponibilidade de uma dependência ou pela impossibilidade de concluir uma comunicação dentro do prazo esperado. Silva Neto (2023) discute problemas associados à comunicação em rede, ao funcionamento da aplicação e ao esgotamento de recursos, destacando a diversidade de condições capazes de comprometer serviços distribuídos.

O componente que apresenta o erro ao cliente nem sempre corresponde ao componente inicialmente afetado. Um serviço pode receber uma resposta de erro de uma dependência e propagá-la para outro ponto da aplicação. Consequentemente, a compreensão do ocorrido pode exigir a análise das interações entre serviços, além da observação da resposta final.

Sousa (2024) relaciona a complexidade da observabilidade em microsserviços à necessidade de acompanhar o fluxo das requisições entre diferentes componentes. Nesse contexto, identificar onde um erro foi percebido constitui uma parte da investigação. Reconstruir o caminho percorrido e localizar as evidências relacionadas ao problema requer informações sobre as operações executadas e suas dependências.

## 2.2 Observabilidade e registros de log

A observabilidade está relacionada à possibilidade de compreender o comportamento interno de um sistema a partir das informações que ele disponibiliza durante a execução. Silva Neto (2023) e Chaves (2025) discutem três sinais utilizados nesse processo: métricas, logs e rastreamentos distribuídos. Esses sinais representam aspectos diferentes do funcionamento da aplicação e podem ser empregados de maneira complementar.

As métricas expressam informações quantitativas sobre o sistema, como utilização de recursos, quantidade de requisições e duração de operações. Os logs registram eventos específicos, acompanhados de informações contextuais. O rastreamento distribuído representa o percurso de uma requisição entre componentes, permitindo examinar as etapas que participam de seu processamento. Chaves (2025) explora a associação entre métricas e rastreamentos para relacionar alterações observadas no comportamento do sistema às operações envolvidas.

Os logs são particularmente úteis quando a investigação depende de detalhes de uma ocorrência. Uma mensagem pode informar que determinada operação foi iniciada, que uma consulta foi concluída ou que uma exceção interrompeu o processamento. Esses registros permitem examinar acontecimentos individuais que podem não estar evidentes em uma medida agregada.

Entretanto, a existência de logs não garante que eles contenham informações suficientes para explicar um problema. Cândido, Aniche e van Deursen (2021) destacam que a utilidade dos registros depende de decisões de instrumentação, como os pontos em que as mensagens são produzidas e o conteúdo incluído nelas. A ausência de contexto, a heterogeneidade dos formatos e o volume de dados podem limitar a interpretação dos eventos.

A avaliação dos logs deve, portanto, considerar sua adequação ao propósito da análise. Para investigar erros distribuídos, são relevantes informações que permitam reconhecer a operação executada, identificar o serviço responsável pelo registro e relacionar o evento às demais etapas da requisição.

## 2.3 Logs estruturados e correlação de requisições

Logs estruturados organizam as informações de um evento em campos identificáveis. Silva Neto (2023) apresenta formatos como JSON e conjuntos de pares de chave e valor como alternativas para representar esses registros. Essa organização permite selecionar e comparar informações sem depender exclusivamente da interpretação do texto livre das mensagens.

Entre os campos que podem compor um registro estão o horário do evento, o serviço, o nível da mensagem, a operação executada e os detalhes de uma exceção. A escolha desses campos deve acompanhar as necessidades da investigação. Cândido, Aniche e van Deursen (2021) ressaltam que os registros precisam ser informativos e adequados aos requisitos da análise para a qual serão utilizados.

Em uma aplicação distribuída, a estruturação também pode incorporar um identificador associado à requisição. Chaves (2025) descreve a propagação de identificadores entre chamadas no contexto do rastreamento distribuído. Quando um identificador compartilhado também aparece nos logs, ele permite agrupar eventos produzidos por diferentes serviços durante o atendimento da mesma requisição.

A correlação ajuda a distinguir registros relacionados entre mensagens geradas por operações concorrentes. A combinação do identificador com o serviço, a operação e o horário fornece elementos para reconstruir o percurso da execução. O horário contribui para organizar a sequência observada, enquanto as informações sobre as chamadas ajudam a interpretar as relações entre os componentes.

A presença de um identificador nos logs, contudo, não constitui, isoladamente, uma implementação completa de rastreamento distribuído. A correlação dos registros permite associar eventos da requisição; uma infraestrutura de rastreamento pode representar adicionalmente suas etapas e relações de execução. Essa distinção delimita o papel dos logs correlacionáveis na análise desenvolvida neste trabalho.

## 2.4 Centralização de logs

A centralização reúne registros produzidos por diferentes componentes em uma infraestrutura comum de armazenamento e consulta. No ciclo de vida apresentado por Cândido, Aniche e van Deursen (2021), a produção dos logs, a infraestrutura que os processa e a análise de seu conteúdo são atividades relacionadas, mas com responsabilidades distintas.

A produção determina quais eventos e informações serão registrados pela aplicação. A infraestrutura recebe, processa e armazena esses dados, tornando-os disponíveis para consulta. A análise utiliza os registros para interpretar comportamentos, reconhecer anomalias ou investigar problemas. Essa separação permite compreender que a qualidade do diagnóstico depende tanto das evidências geradas quanto dos recursos disponíveis para examiná-las.

Quando os registros permanecem nas fontes locais, sua análise pode exigir a seleção de mensagens de diferentes serviços e a combinação das informações pertinentes. Uma infraestrutura centralizada permite executar consultas sobre os registros reunidos, utilizando critérios como serviço, intervalo temporal e identificador de requisição.

Sousa (2024) discute ferramentas de observabilidade com funções de coleta, armazenamento, consulta e visualização. Entre elas, apresenta o Loki como uma solução de agregação e consulta de logs, utilizada em conjunto com o Grafana. Essas funções apoiam o acesso aos registros e a apresentação das informações, enquanto a interpretação dos acontecimentos depende do conteúdo disponível e do procedimento de investigação.

A centralização modifica, assim, as condições de disponibilização dos dados. Sua contribuição para o diagnóstico precisa ser examinada conforme o objetivo da avaliação. Verificar se os registros chegaram ao repositório e preservaram seus campos permite avaliar aspectos da infraestrutura. Demonstrar maior precisão ou menor tempo de investigação exige evidências correspondentes ao desempenho dessa atividade.

## 2.5 Injeção de falhas e análise de diagnóstico

A injeção de falhas consiste na introdução deliberada de condições que podem produzir comportamentos indesejados no sistema sob teste. Seu emprego em experimentos permite conhecer a condição provocada e examinar como ela se manifesta durante a execução.

Cândido, Aniche e van Deursen (2021, p. 15) discutem essa técnica como uma possibilidade para avaliar se os logs evidenciam a presença de falhas. O mapeamento apresenta estudos que introduzem alterações no sistema, executam testes capazes de manifestar os problemas e analisam os registros resultantes. Entre os exemplos relatados estão a omissão de chamadas de métodos e de atribuições a variáveis. Esses exemplos pertencem aos estudos revisados e não constituem uma classificação obrigatória de cenários experimentais.

A aplicação dessa perspectiva a uma pesquisa requer definir as condições provocadas e as evidências que serão examinadas. O confronto entre a condição conhecida e os registros produzidos permite investigar se as mensagens representam o comportamento ocorrido e se oferecem informações sobre os componentes envolvidos.

Essa análise também exige distinguir a manifestação externa do erro das evidências disponíveis internamente. Uma resposta recebida pelo cliente pode indicar que a operação falhou, mas não explicar qual dependência ou etapa foi afetada. Mensagens de exceção, operações registradas e eventos correlacionados podem oferecer elementos adicionais para interpretar o problema.

Na discussão sobre análise de causa raiz, Cândido, Aniche e van Deursen (2021) distinguem a identificação de um comportamento anormal da investigação de suas causas e impactos. Essa distinção é relevante para avaliações com erros controlados: reconhecer que uma requisição terminou com erro não equivale, necessariamente, a explicar o que ocorreu ao longo de seu processamento.

A injeção de falhas também possui limites. Os autores observam que sua efetividade depende da qualidade dos testes e de sua capacidade de manifestar os problemas introduzidos. Dessa forma, os resultados de uma avaliação se relacionam às condições efetivamente executadas, sem representar uma garantia de que os logs evidenciarão qualquer falha possível.

## 2.6 Trabalhos relacionados

Cândido, Aniche e van Deursen (2021) realizaram um mapeamento sistemático de 108 estudos sobre monitoramento baseado em logs. A organização da literatura acompanha o ciclo de vida dos registros, abrangendo sua geração, a infraestrutura de processamento e armazenamento e a análise dos dados. Para esta pesquisa, o trabalho oferece uma base para distinguir a preservação e a disponibilização dos registros da interpretação de seu conteúdo. A discussão sobre injeção de falhas também fundamenta o confronto entre condições provocadas e evidências produzidas durante a execução.

Silva Neto (2023) desenvolveu a ferramenta Application Performance Monitoring with Metrics, denominada APME, para monitoramento de métricas e indicação de possíveis falhas em microsserviços. A avaliação utilizou a aplicação de referência TeaStore em condições com e sem sobrecarga computacional, examinando informações de CPU, memória, rede e disco. Sua abordagem se concentra no comportamento dos recursos monitorados. O presente trabalho utiliza registros de eventos para investigar como diferentes condições de erro são representadas e disponibilizadas em dois ambientes.

Sousa (2024) analisou e implementou práticas de observabilidade em uma aplicação de gerenciamento de cursos, abordando instrumentação e integração de ferramentas para acompanhar o funcionamento do sistema. O trabalho contribui para contextualizar o papel das métricas, dos logs e do rastreamento distribuído. Nesta pesquisa, o recorte concentra-se nos logs e na comparação entre sua disponibilização local e centralizada, mantendo a instrumentação de origem nos dois ambientes.

Chaves (2025) apresentou a solução FOCUS, que associa métricas e rastreamentos distribuídos para detectar anomalias e falhas em microsserviços. A proposta relaciona valores de métricas às operações envolvidas e utiliza informações de rastreamento para apoiar a investigação. Sua avaliação empregou a aplicação Spring Petclinic e condições destinadas a produzir comportamentos anômalos. Enquanto essa abordagem explora a combinação de sinais de observabilidade, o presente estudo examina registros de log correlacionáveis e verifica sua correspondência com erros controlados.

Esses trabalhos apresentam diferentes formas de produzir, organizar e interpretar informações sobre sistemas distribuídos. O recorte desta pesquisa consiste em comparar as evidências dos mesmos tipos de erro em dois ambientes de uma aplicação de referência, examinando sua representação nos logs e sua preservação na infraestrutura centralizada. A arquitetura implementada e os procedimentos utilizados nessa comparação são apresentados na metodologia.

## Referências citadas

CÂNDIDO, Jeanderson; ANICHE, Maurício; VAN DEURSEN, Arie. Log-based software monitoring: a systematic mapping study. PeerJ Computer Science, v. 7, e489, 2021. DOI: https://doi.org/10.7717/peerj-cs.489.

CHAVES, Adalberto Felipe Pinheiro. Fusão de dados de sinais de observabilidade para detectar anomalias e falhas em microsserviços. 2025. Trabalho de Conclusão de Curso (Graduação em Ciência da Computação) — Universidade Federal do Ceará, Campus de Crateús, Crateús, 2025. Disponível em: https://repositorio.ufc.br/handle/riufc/81876.

SILVA NETO, Antonio Airton da. Monitoramento de aplicações baseadas em microsserviços utilizando métricas de desempenho. 2023. Trabalho de Conclusão de Curso (Graduação em Sistemas de Informação) — Universidade Federal do Ceará, Campus de Crateús, Crateús, 2023. Disponível em: https://repositorio.ufc.br/handle/riufc/73623.

SOUSA, Willian Withi Alves de. Análise e implementação de práticas de observabilidade específica para microsserviços. 2024. Trabalho de Conclusão de Curso (Graduação em Engenharia de Computação) — Universidade Federal do Ceará, Campus de Sobral, Sobral, 2024. Disponível em: https://repositorio.ufc.br/handle/riufc/79176.
