# Microservices Blueprint

## Objetivo
Preparar o MVP atual para uma migracao por estrangulamento, preservando a logica de negocio existente e trocando apenas as fronteiras de infraestrutura.

## Boundaries iniciais
- `edge-gateway`: webhook, auth, replay e normalizacao de payload
- `conversation-service`: sessao, roteamento, IA e handoff
- `catalog-service`: cardapio, regras de produto, pricing e learnings controlados
- `orders-service`: encomendas, cafeteria e cestas
- `delivery-service`: entrega, retirada e status
- `backoffice-service`: painel interno, clientes e consultas operacionais

## Fundacao aplicada nesta etapa
- Portas de aplicacao para `catalog`, `orders`, `delivery`, `messaging` e `attention`
- Adaptadores locais que encapsulam o runtime atual
- `ai.tools` e `utils.mensagens` consumindo as portas, sem mudar a API publica
- Bus interno de comandos para separar `edge-gateway` e `conversation-service`
- `webhook` despachando `HandleInboundMessageCommand`
- `handler` despachando `GenerateAiReplyCommand`
- Bus interno de eventos com outbox local em `jsonl`
- Publicacao de `MessageReceivedEvent`, `AiReplyGeneratedEvent` e `OrderCreatedEvent`
- `conversation gateway` com fallback local e modo HTTP por `CONVERSATION_SERVICE_URL`
- Apps separados no mesmo repo: `edge_main.py` e `conversation_main.py`
- `docker-compose` com modo padrao monolitico e perfil `split` para `edge` + `conversation`
- `redis` no perfil `split` para sessao conversacional e estado compartilhado

## Proximas fases
1. Fazer o `edge-gateway` usar HTTP real contra `conversation-service` em ambiente separado
2. Trocar event bus local por fila/outbox consumido por worker
3. Extrair `catalog-service` e `backoffice-service`
4. Extrair `orders-service` e `delivery-service`
5. Publicar `delivery_status_updated` e demais eventos operacionais
6. Remover o fallback local quando os serviços estiverem estabilizados

## Execucao
- Monolito atual:
  - `docker compose up -d chokobot`
- Split local:
  - `docker compose --profile split up -d chokobot-redis chokobot-conversation chokobot-edge`
- Portas:
  - monolito: `8003`
  - edge: `8004`
  - conversation: `8005`
  - redis: `6379`
