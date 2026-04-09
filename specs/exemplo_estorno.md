# Especificação Funcional: Processamento de Estorno de Pagamentos

## Contexto
O sistema de e-commerce precisa processar estornos de pagamentos para pedidos cancelados de forma automatizada.

## Requisitos Funcionais

1. **Agendamento**: Todos os dias, à meia-noite, o sistema deve buscar no banco de dados todos os pedidos com status "cancelado" que ainda não tiveram estorno processado.

2. **Enfileiramento**: Para cada pedido encontrado, o sistema deve publicar uma mensagem em uma fila (Google Pub/Sub) contendo os dados do pedido e do pagamento original, para que o microsserviço financeiro processe o estorno.

3. **Processamento de Estorno**: O microsserviço financeiro deve consumir as mensagens da fila e, para cada uma, chamar o gateway de pagamento para solicitar o estorno do valor.

4. **Callback de Atualização**: Após o processamento (sucesso ou falha), o microsserviço financeiro deve chamar uma API de callback do sistema principal para atualizar o status do estorno no banco de dados.

5. **Resiliência**: O processamento deve ser resiliente a falhas temporárias no gateway de pagamento, implementando retry com backoff exponencial.

## Requisitos Não-Funcionais
- O sistema deve processar até 10.000 estornos por execução.
- O tempo máximo de processamento por estorno individual é de 30 segundos.
- Todos os passos devem ser rastreáveis via logs estruturados e tracing distribuído.
