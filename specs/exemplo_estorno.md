# Especificação Funcional: Processamento Automatizado de Estornos

## 1. Visão Geral e Contexto

O ecossistema do e-commerce exige um mecanismo robusto, rastreável e assíncrono para devolução de valores de pedidos cancelados. O objetivo deste fluxo é garantir que o cliente receba seu dinheiro de volta no menor tempo possível, reduzindo a carga operacional do time de atendimento financeiro (backoffice) e evitando o risco de estornos duplicados.

## 2. Atores e Sistemas Envolvidos

* **E-commerce Core (Sistema Principal):** Detém o ciclo de vida do pedido e a base de dados principal.
* **Microsserviço Financeiro:** Responsável por orquestrar regras financeiras, comunicar-se com provedores externos e garantir a integridade da transação.
* **Gateway de Pagamento / Adquirente:** Provedor externo que processará a devolução do dinheiro na fatura do cartão ou via PIX.
* **Mensageria (Google Pub/Sub):** Fila de eventos que garante o desacoplamento e a entrega garantida das solicitações de estorno.

## 3. Regras de Negócio (RN)

* **RN01 - Idempotência Obrigatória:** Um estorno jamais pode ser processado duas vezes para o mesmo pedido/pagamento. Toda requisição ao Gateway deve possuir uma chave de idempotência (ex: `refund_id` gerado via UUIDv4 atrelado ao número do pedido).
* **RN02 - Estorno na Origem:** O valor deve obrigatoriamente ser estornado para o mesmo método de pagamento utilizado na compra original (ex: Pix de volta para a mesma chave/conta, Cartão de Crédito para a mesma fatura).
* **RN03 - Validação de Montante:** O sistema deve validar se o valor solicitado para estorno não ultrapassa o valor líquido capturado originalmente no pedido.
* **RN04 - Prazo Limite de Automação:** Estornos de transações com mais de 90 dias (ou conforme contrato do gateway) não devem ser processados automaticamente. Devem ser marcados com status para "Intervenção Manual" via backoffice.

## 4. Máquina de Estados do Estorno
Cada solicitação de estorno deverá transitar pelos seguintes status no banco de dados do Core:

1.  `PENDENTE`: Pedido cancelado, elegível para estorno, aguardando captura pelo Job.
2.  `ENFILEIRADO`: Capturado pelo Job e enviado ao Pub/Sub com sucesso.
3.  `EM_PROCESSAMENTO`: Microsserviço financeiro consumiu a mensagem e iniciou a chamada ao Gateway.
4.  `CONCLUIDO`: Gateway confirmou o estorno com sucesso.
5.  `FALHA_TEMPORARIA`: Erro de comunicação ou indisponibilidade, aguardando nova tentativa (Retry).
6.  `FALHA_MANUAL`: Esgotadas as tentativas de retry ou falha de regra de negócio (ex: cartão do cliente expirado). Exige ação humana no backoffice.

## 5. Requisitos Funcionais (RF)

### 5.1. Agendamento e Extração (CronJob)

* **RF01:** O sistema deve executar uma rotina (CronJob) configurável (default: `0 0 * * *` - meia-noite) para buscar pedidos com status de pagamento "Cancelado" e status de estorno "Pendente".
* **RF02:** A busca deve utilizar paginação e *locking* no banco de dados (ex: `SELECT FOR UPDATE SKIP LOCKED` no Postgres) para evitar que execuções concorrentes do Job capturem os mesmos pedidos.

### 5.2. Enfileiramento e Mensageria

* **RF03:** O sistema publicará um *payload* JSON no tópico do Google Pub/Sub contendo, no mínimo: `order_id`, `payment_transaction_id`, `amount_to_refund`, `currency`, e `idempotency_key`.
* **RF04:** Após o *ACK* de publicação com sucesso no Pub/Sub, o sistema Core deve atualizar o status do estorno no banco para `ENFILEIRADO`.

### 5.3. Processamento no Microsserviço Financeiro

* **RF05:** O microsserviço consumirá a fila e fará uma requisição HTTP/REST ao Gateway de Pagamento.
* **RF06:** O microsserviço deve mapear e tratar os códigos de erro do Gateway (HTTP 4xx para erros de negócio, HTTP 5xx para indisponibilidade).

### 5.4. Resolução e Callback

* **RF07:** Em caso de SUCESSO (HTTP 200/201 do Gateway), o microsserviço disparará um *webhook/callback* via POST para a API do sistema Core informando a conclusão, o `gateway_refund_id` e a data/hora da efetivação.
* **RF08:** A API de callback do sistema Core deve ser protegida por autenticação (Token JWT ou mTLS).

### 5.5. Fila de Mensagens Mortas (DLQ)

* **RF09:** Mensagens no Pub/Sub que não puderem ser processadas após o número máximo de tentativas do broker devem ser movidas automaticamente para uma *Dead Letter Queue* (DLQ).
* **RF10:** O microsserviço deve ter uma rotina para alertar sobre mensagens na DLQ e disponibilizar uma interface/API para reenfileirá-las manualmente após correção do incidente.

## 6. Requisitos Não Funcionais (RNF)

### 6.1. Desempenho e Escalabilidade

* **RNF01:** O banco de dados e a query de extração devem ser otimizados (índices adequados) para varrer e processar lotes de até 10.000 pedidos em menos de 5 minutos durante a execução do Job.
* **RNF02:** O timeout máximo configurado para a requisição de estorno individual contra o Gateway deve ser de 30 segundos (Read Timeout).
* **RNF03:** O consumo do Pub/Sub deve ser assíncrono e suportar escalabilidade horizontal (*auto-scaling* baseado no tamanho da fila).

### 6.2. Resiliência

* **RNF04 - Retry Pattern:** O consumo e chamada ao Gateway devem implementar *Retry* com *Exponential Backoff* (ex: 2s, 4s, 8s, 16s) para erros de rede ou HTTP 5xx, limitado a 5 tentativas por mensagem.
* **RNF05 - Circuit Breaker:** O microsserviço financeiro deve implementar o padrão *Circuit Breaker*. Se a taxa de falha do Gateway ultrapassar 50% em uma janela de 1 minuto, o circuito abre (Open), paralisando o consumo da fila para evitar sobrecarga inútil, tentando fechar (Half-Open) após 5 minutos.

### 6.3. Observabilidade e Auditoria

* **RNF06 - Logs Estruturados:** Todos os logs devem ser no formato JSON, contendo as chaves `order_id` e `transaction_id` para facilitar buscas em ferramentas como Datadog, ELK ou Cloud Logging.
* **RNF07 - Tracing Distribuído:** Propagação de *trace ID* (OpenTelemetry) deve ser injetada no cabeçalho das mensagens do Pub/Sub e das requisições HTTP para que seja possível visualizar o caminho completo desde o Job do Core até o Callback do Financeiro.
* **RNF08 - Alertas:** Regras de alerta devem ser configuradas (via Slack/PagerDuty) caso a DLQ contenha mais de 10 mensagens ou caso o *Circuit Breaker* seja ativado.

### 6.4. Segurança e Compliance

* **RNF09:** PII (Informações Pessoais Identificáveis) e dados sensíveis de cartão (PCI-DSS) **não** devem ser trafegados na fila e **jamais** devem ser impressos nos logs (uso de mascaramento/ofuscação em logs). O payload deve trafegar apenas IDs e valores monetários.