# Roteiro completo de testes e coleta de resultados

Os comandos abaixo são para Bash, executados na raiz de `microsservice_tcc`. Cada etapa deve terminar com sucesso antes da próxima. Os nomes das pastas são `non_centralized` e `centralized`, com underscore.

## 1. Estado do código em 12/10/2026

A revisão encontrou uma pendência na classificação de E05: `HttpConnectTimeoutException` era tratada como timeout de resposta, produzindo 504 / `DOWNSTREAM_TIMEOUT` quando Product estava parado. A classificação foi corrigida igualmente nos dois ambientes:

- Timeout ao estabelecer a conexão: 502 / `DOWNSTREAM_UNAVAILABLE`.
- Timeout enquanto se aguarda a resposta: 504 / `DOWNSTREAM_TIMEOUT`.

O teste de regressão reproduziu o 504 antes da correção e passou depois do ajuste. Os builds passaram com 16 testes Java por ambiente; passaram também 14 testes Python por executor, seis testes de observabilidade, a paridade dos 55 arquivos compartilhados e a validação dos dois Compose.

É necessário reconstruir as imagens e repetir os experimentos em Docker, especialmente E03 e E05, para confirmar o comportamento em runtime. O agente não executou essa etapa: `sudo -n` ainda exige senha. Os resultados antigos permanecem preservados.

O coordenador geral discutido anteriormente continua sendo uma opção futura. Os comandos deste roteiro usam os scripts que já existem.

## 2. Preparar a pasta de coleta

```bash
cd "/home/ricardo/Área de trabalho/microsservice_tcc"
set -o pipefail
mkdir -p coleta/rodada-01/non_centralized coleta/rodada-01/centralized
```

`pipefail` mantém o código de falha dos comandos quando a saída é salva com `tee`. A pasta `coleta/` é ignorada pelo Git e fica dentro do projeto. Para uma bateria independente posterior, use `rodada-02`, `rodada-03` etc. Uma repetição do cenário recebe sempre um novo `runId`.

Requisitos: Python 3, Docker Engine com Compose e Java 21 para os builds locais. Os comandos de Docker usam sudo; os builds Maven e testes Python locais usam seu usuário.

## 3. Conferir paridade e configuração

```bash
python3 scripts/check-parity.py 2>&1 | tee coleta/rodada-01/paridade.log
(cd non_centralized && docker compose config --quiet) 2>&1 | tee coleta/rodada-01/non_centralized/compose-config.log
(cd centralized && docker compose config --quiet) 2>&1 | tee coleta/rodada-01/centralized/compose-config.log
```

A paridade deve confirmar 55 arquivos idênticos. `compose config --quiet` não imprime nada quando a configuração está válida; um arquivo vazio é esperado nesse caso. Confirme o código de saída imediatamente após cada comando, se necessário, com `echo $?`: zero indica sucesso.

## 4. Executar os builds e testes Java

```bash
(cd non_centralized && ./mvnw clean verify) 2>&1 | tee coleta/rodada-01/non_centralized/maven.log
(cd centralized && ./mvnw clean verify) 2>&1 | tee coleta/rodada-01/centralized/maven.log
```

Cada build deve terminar com `BUILD SUCCESS`, com 16 testes, zero falhas e zero erros na versão atual. Os testes verificam as APIs e a infraestrutura; usam H2 nos testes de persistência. Os experimentos posteriores usam PostgreSQL real.

Preserve os relatórios detalhados:

```bash
cp -a non_centralized/target/surefire-reports coleta/rodada-01/non_centralized/
cp -a centralized/target/surefire-reports coleta/rodada-01/centralized/
```

O build gera quatro JARs executáveis em cada `target/`:

```text
microservices-1.0.0-SNAPSHOT-gateway.jar
microservices-1.0.0-SNAPSHOT-user-service.jar
microservices-1.0.0-SNAPSHOT-product-service.jar
microservices-1.0.0-SNAPSHOT-order-service.jar
```

## 5. Executar os testes Python

```bash
(cd non_centralized && python3 -m unittest discover -s experiments -p 'test_*.py' -v) 2>&1 | tee coleta/rodada-01/non_centralized/testes-executor.log
(cd centralized && python3 -m unittest discover -s experiments -p 'test_*.py' -v) 2>&1 | tee coleta/rodada-01/centralized/testes-executor.log
(cd centralized && python3 -m unittest discover -s scripts -p 'test_*.py' -v) 2>&1 | tee coleta/rodada-01/centralized/testes-observabilidade.log
```

Resultados esperados: 14 testes do executor em cada ambiente e seis de observabilidade, todos com `OK`. Esses testes verificam registro, recuperação e entrega usando servidores HTTP locais e substitutos do controle Docker. A bateria abaixo verifica o ambiente real.

## 6. Validar a versão sem centralização

### 6.1. Iniciar e conferir

Os ambientes usam as mesmas portas; execute somente um por vez. `down` preserva os volumes.

```bash
sudo ./tcc.sh centralized down
sudo env FAULT_ENABLED=true ./tcc.sh non_centralized up --build -d --wait 2>&1 | tee coleta/rodada-01/non_centralized/inicializacao.log
sudo ./tcc.sh non_centralized ps | tee coleta/rodada-01/non_centralized/containers-iniciais.txt
```

Confirme os quatro serviços e três bancos saudáveis. `--build` é necessário nesta primeira execução depois da correção Java de E05.

### 6.2. Executar o smoke

```bash
sudo python3 non_centralized/scripts/smoke.py --faults --check-logs > coleta/rodada-01/non_centralized/smoke.json 2> coleta/rodada-01/non_centralized/smoke-erros.log
```

Confira o código de saída zero e o JSON com `checks: 20` e `logCorrelationChecked: true`. O smoke valida criação/consulta, contratos e correlação. Ele prepara dados e cria um pedido de sucesso; seus controles sintéticos não substituem a parada real de banco/serviço em E02/E05. Registre-o como validação técnica, separado das rodadas de diagnóstico humano.

### 6.3. Executar os cinco experimentos

Execute os comandos individualmente. Aguarde `E0X: concluído` e confirme a restauração antes de avançar. Se aparecer `falhou`, preserve os arquivos, verifique a causa e use a seção de recuperação.

```bash
sudo ./non_centralized/experiments/run-experiment.sh E01 --results-dir "$PWD/coleta/rodada-01/non_centralized/experiments" 2>&1 | tee coleta/rodada-01/non_centralized/E01-terminal.log
sudo ./non_centralized/experiments/run-experiment.sh E02 --results-dir "$PWD/coleta/rodada-01/non_centralized/experiments" 2>&1 | tee coleta/rodada-01/non_centralized/E02-terminal.log
sudo ./non_centralized/experiments/run-experiment.sh E03 --results-dir "$PWD/coleta/rodada-01/non_centralized/experiments" 2>&1 | tee coleta/rodada-01/non_centralized/E03-terminal.log
sudo ./non_centralized/experiments/run-experiment.sh E04 --results-dir "$PWD/coleta/rodada-01/non_centralized/experiments" 2>&1 | tee coleta/rodada-01/non_centralized/E04-terminal.log
sudo ./non_centralized/experiments/run-experiment.sh E05 --results-dir "$PWD/coleta/rodada-01/non_centralized/experiments" 2>&1 | tee coleta/rodada-01/non_centralized/E05-terminal.log
```

Cada caso cria seus próprios dados e restaura seu recurso afetado. O POST experimental é executado uma vez; as consultas GET de recuperação podem ser repetidas com prazo limitado. O reset manual não é necessário entre execuções aprovadas.

### 6.4. Investigar e encerrar

Antes de trocar o ambiente, examine os arquivos individuais de cada execução em `logs/`, usando o trace informado em `metadata.json`. Compare mensagens, timestamps, operações e stack traces dos serviços participantes.

```bash
sudo ./non_centralized/experiments/reset-environment.sh 2>&1 | tee coleta/rodada-01/non_centralized/reset.log
sudo ./tcc.sh non_centralized ps | tee coleta/rodada-01/non_centralized/containers-finais.txt
sudo ./tcc.sh non_centralized down
```

O reset inicia/recria as aplicações com `FAULT_ENABLED=false` e preserva dados/resultados. O `down` libera as portas para a versão centralizada.

## 7. Validar a versão centralizada

### 7.1. Iniciar e conferir a infraestrutura

```bash
sudo env FAULT_ENABLED=true ./tcc.sh centralized up --build -d --wait 2>&1 | tee coleta/rodada-01/centralized/inicializacao.log
sudo ./tcc.sh centralized ps | tee coleta/rodada-01/centralized/containers-iniciais.txt
sudo python3 centralized/scripts/observability.py > coleta/rodada-01/centralized/disponibilidade.json 2> coleta/rodada-01/centralized/disponibilidade-erros.log
```

A API deve estar disponível; o verificador deve retornar `success: true` e código de saída zero. Ele confere Fluent Bit, Loki, Grafana, Data Source e dashboard.

### 7.2. Executar o smoke

```bash
sudo python3 centralized/scripts/smoke.py --faults --check-logs > coleta/rodada-01/centralized/smoke.json 2> coleta/rodada-01/centralized/smoke-erros.log
```

Confira novamente os 20 checks e a correlação. A entrega dos traces dos experimentos ao Loki será conferida pelo wrapper de cada caso.

### 7.3. Executar os cinco experimentos

```bash
sudo ./centralized/experiments/run-experiment.sh E01 --results-dir "$PWD/coleta/rodada-01/centralized/experiments" 2>&1 | tee coleta/rodada-01/centralized/E01-terminal.log
sudo ./centralized/experiments/run-experiment.sh E02 --results-dir "$PWD/coleta/rodada-01/centralized/experiments" 2>&1 | tee coleta/rodada-01/centralized/E02-terminal.log
sudo ./centralized/experiments/run-experiment.sh E03 --results-dir "$PWD/coleta/rodada-01/centralized/experiments" 2>&1 | tee coleta/rodada-01/centralized/E03-terminal.log
sudo ./centralized/experiments/run-experiment.sh E04 --results-dir "$PWD/coleta/rodada-01/centralized/experiments" 2>&1 | tee coleta/rodada-01/centralized/E04-terminal.log
sudo ./centralized/experiments/run-experiment.sh E05 --results-dir "$PWD/coleta/rodada-01/centralized/experiments" 2>&1 | tee coleta/rodada-01/centralized/E05-terminal.log
```

Aguarde cada conclusão. O wrapper verifica a infraestrutura antes da injeção e, depois da restauração, compara os eventos dos arquivos de origem com os retornados pelo Loki. E01 exige Gateway/Order; E02–E04 exigem os quatro serviços; E05 exige Gateway/Order/User, porque Product está parado durante a requisição.

### 7.4. Investigar no Grafana e preservar a evidência

Acesse `http://localhost:3000`, usuário inicial `admin` e senha inicial `tcc-local`, salvo alterações locais. Abra Explore e selecione Loki.

Para cada execução:

1. Leia `traceId`, `requestStartedAt` e `logsCollectedAt` em `metadata.json`.
2. Ajuste o intervalo do Grafana para abranger esses horários, com margem antes/depois. Os metadados usam UTC; confira o fuso da interface.
3. Consulte todos os eventos do trace e exiba-os em ordem cronológica.
4. Expanda os eventos relevantes para examinar mensagens, campos e stack traces.
5. Exporte os eventos em JSON ou texto, conforme as opções da interface, e guarde-os junto da execução. Capturas de tela complementam os registros.

```logql
{job="tcc"} | json | traceId="TRACE_DA_EXECUCAO"
```

Consultas adicionais:

```logql
{job="tcc", service="product-service"}
{job="tcc"} | json | level="ERROR"
```

Comece pelo trace completo. E01 registra validação em WARN; uma consulta apenas por ERROR pode omitir essa evidência.

### 7.5. Restaurar e encerrar

Faça as exportações antes de encerrar o Grafana:

```bash
sudo ./centralized/experiments/reset-environment.sh 2>&1 | tee coleta/rodada-01/centralized/reset.log
sudo ./tcc.sh centralized ps | tee coleta/rodada-01/centralized/containers-finais.txt
sudo ./tcc.sh centralized down
```

`down` preserva os volumes de Loki/Grafana. Durante a coleta, preserve esses volumes; `down -v` os remove.

## 8. Conferir os resultados esperados de cada caso

| Caso | Falha provocada | HTTP esperado no Gateway | Código esperado | Evidência principal |
|---|---|---:|---|---|
| E01 | Quantidade inválida no pedido | 400 | VALIDATION_ERROR | Order registra os campos rejeitados |
| E02 | Banco de produtos parado | 502 | DOWNSTREAM_ERROR | Product registra DATABASE_UNAVAILABLE / 503 |
| E03 | Consulta ao Product atrasada | 504 | DOWNSTREAM_TIMEOUT | Order aguarda a resposta; Product conclui o GET depois |
| E04 | Exceção interna no Product | 502 | DOWNSTREAM_ERROR | Product registra INTERNAL_ERROR / 500 e stack trace |
| E05 | Product parado | 502 | DOWNSTREAM_UNAVAILABLE | Order registra recusa ou timeout ao estabelecer a conexão |

A classificação de E05 foi corrigida no código. A execução Docker depois da reconstrução precisa confirmar esse resultado; não edite os resultados anteriores que retornaram 504.

## 9. Arquivos de cada execução

```text
coleta/rodada-01/<ambiente>/experiments/<caso>/<run-id>/
  metadata.json
  response.json
  logs/
    gateway.log
    order-service.log
    user-service.log
    product-service.log
```

Em `metadata.json`, confira:

- `success`: sucesso técnico geral.
- `expectedResponse` e `observedResponse`: HTTP/código previsto e recebido.
- `traceId`: correlação da requisição experimental.
- `logCollection.success`: coleta dos arquivos.
- `cleanup.success`: restauração.
- `invariants.success`: pedidos e estoque preservados.
- `observability.success`: entrega ao Loki, somente no centralizado.
- `timeouts`, `images`, `fixtures` e horários: condições da execução.

Um campo ausente em uma execução interrompida ou rejeitada significa que aquela verificação pode não ter sido executada. Registre-o como não verificado. A ausência de `observability` no ambiente sem centralização é esperada.

## 10. Consolidar a tabela técnica em CSV

Depois da bateria, execute este bloco na raiz. Ele lê somente os resultados desta rodada, preserva execuções aprovadas e falhas e deixa os campos de diagnóstico humano vazios. Não interpreta a causa pelos logs.

```bash
python3 - <<'PY'
import csv
import json
from pathlib import Path

batch = Path('coleta/rodada-01')
types = {
    'E01': 'Dados inválidos',
    'E02': 'Banco de produtos indisponível',
    'E03': 'Timeout de resposta do Product',
    'E04': 'Exceção interna no Product',
    'E05': 'Product indisponível',
}

def check(data, name):
    value = data.get(name, {}).get('success')
    return 'não verificado' if value is None else ('sim' if value else 'não')

destination = batch / 'resultados-tecnicos.csv'
with destination.open('w', encoding='utf-8-sig', newline='') as file:
    writer = csv.writer(file)
    writer.writerow([
        'ambiente', 'caso', 'run_id', 'trace_id', 'tipo_esperado',
        'http_esperado', 'codigo_esperado', 'http_observado', 'codigo_observado',
        'contrato_confere', 'execucao_aprovada', 'coleta_aprovada',
        'restauracao_aprovada', 'invariantes_aprovadas', 'entrega_loki',
        'diagnostico_humano', 'acerto_humano', 'tempo_diagnostico_s',
        'evidencia', 'erro_execucao',
    ])
    for environment in ['non_centralized', 'centralized']:
        for path in sorted((batch / environment / 'experiments').glob('E*/*/metadata.json')):
            data = json.loads(path.read_text())
            expected = data.get('expectedResponse') or {}
            observed = data.get('observedResponse') or {}
            matches = ('sim' if observed == expected else 'não') if observed else 'não verificado'
            writer.writerow([
                environment, data.get('scenario'), data.get('runId'), data.get('traceId'),
                types.get(data.get('scenario'), ''), expected.get('status'), expected.get('code'),
                observed.get('status'), observed.get('code'), matches,
                'sim' if data.get('success') else 'não', check(data, 'logCollection'),
                check(data, 'cleanup'), check(data, 'invariants'),
                check(data, 'observability') if environment == 'centralized' else 'não se aplica',
                '', '', '', '', data.get('error') or data.get('cleanup', {}).get('error', ''),
            ])
print(destination)
PY
```

Guarde o CSV técnico original. Preencha os campos humanos em uma cópia destinada à análise, pois executar novamente o exportador sobrescreve o CSV gerado.

## 11. Coletar o diagnóstico humano

Esta etapa mede a investigação pelos logs, depois da validação técnica.

1. Defina previamente número de repetições, limite de tempo e critérios de diagnóstico correto, parcial e incorreto.
2. Para cada rodada, o operador registra caso, ambiente, `runId` e trace, e confere a evidência disponível.
3. Disponibilize os arquivos individuais ou o Grafana, com trace, intervalo e identificador neutro. Em avaliação cega, mantenha cenário, alvo, cabeçalhos e metadados completos com o operador.
4. Comece a contagem quando o avaliador receber a evidência pronta.
5. O avaliador registra tipo de falha, componente envolvido e evidência usada. Ao receber essa resposta, pare a contagem e registre o tempo em segundos.
6. Compare o diagnóstico com a falha conhecida usando os critérios definidos. Registre também ausência de diagnóstico dentro do prazo.
7. Repita com o mesmo número de rodadas e condições equivalentes nos dois ambientes. Registre diferenças de recursos da infraestrutura de logs e possíveis efeitos de aprendizagem.

E02 e E04 retornam o mesmo HTTP/código externo. O acerto do contrato técnico não equivale ao acerto do diagnóstico humano. O tempo total do runner inclui preparação, injeção e recuperação; mantenha-o separado do tempo de investigação. Se o operador investigar sabendo a causa, descreva a medida como localização/interpretação de evidências com causa conhecida.

O acesso a arquivos ou Grafana deve seguir o protocolo escolhido. Stack traces de E03/E04 podem revelar os hooks; registre essa limitação na metodologia. A latência de ingestão é uma medida separada do tempo de diagnóstico quando a contagem começa com a evidência disponível.

## 12. Repetições e problemas durante a coleta

- Uma nova execução do caso cria outro `runId`; preserve todas as execuções, incluindo as que falharam.
- Para uma bateria independente, mude todos os caminhos de `rodada-01` para `rodada-02` e crie as novas pastas.
- Na coleta com avaliadores, aguarde o diagnóstico de cada rodada antes de executar a próxima.
- Se a restauração falhar, use o reset do ambiente e confira sua disponibilidade antes de repetir.
- O reset desabilita os controles de injeção. Para voltar a E03/E04, execute `sudo env FAULT_ENABLED=true ./tcc.sh <ambiente> up -d --wait`; no centralizado, confira também `observability.py`.
- Se a recuperação exigir mais tempo, use `--ready-timeout 120` igualmente nos dois ambientes e registre a mudança.
- Não altere retrospectivamente um resultado divergente nem trate falha de execução/coleta como erro do avaliador.

## 13. Arquivar tudo

Depois de concluir as exportações e o CSV, preserve a pasta inteira:

```bash
tar -czf coleta/rodada-01.tar.gz -C coleta rodada-01
sha256sum coleta/rodada-01.tar.gz > coleta/rodada-01.tar.gz.sha256
```

O pacote contém os arquivos salvos sob `coleta/rodada-01`, incluindo logs dos testes, relatórios Java, resultados experimentais, CSV e exportações que você colocou nessa pasta. Ele não inclui volumes Docker nem substitui exportar os logs relevantes do Grafana antes de limpar o Loki. Faça uma cópia do pacote em outro local para preservar a evidência.

Documentação de apoio: [visão geral](README.md), [experimentos sem centralização](non_centralized/experiments/README.md), [experimentos centralizados](centralized/experiments/README.md), [observabilidade](centralized/observability/README.md) e [validação](centralized/observability/VALIDATION.md).
