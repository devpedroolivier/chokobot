# Arquitetura de Microsservicos

## Documentos relacionados
- `../executive-implementation-plan.md`: roadmap executivo com sprints, backlog e impacto esperado
- `event-contracts.md`: eventos canonicos, envelope e responsabilidade por servico
- `tenant-structural-model.md`: decisao estrutural minima de multi-tenant antes da Sprint 5

## Objetivo
Preparar o MVP atual para uma migracao por estrangulamento, preservando a logica de negocio existente e trocando apenas as fronteiras de infraestrutura.

## Leitura correta do estado atual
- O modo `split` entre `edge` e `conversation` ja existe no mesmo repositorio e ajuda a validar fronteiras.
- O uso de `redis` no perfil `split` comprova viabilidade tecnica local, mas ainda nao caracteriza operacao distribuida pronta para producao.
- O fallback local continua sendo parte da estrategia de transicao e precisa ser removido apenas depois de observabilidade, retries e contratos estaveis.

## Limites iniciais
- `edge-gateway`: webhook, auth, replay e normalizacao de payload
- `conversation-service`: sessao, roteamento, IA e handoff
- `catalog-service`: cardapio, regras de produto, pricing e learnings controlados
- `orders-service`: encomendas, cafeteria e cestas
- `delivery-service`: entrega, retirada e status
- `backoffice-service`: painel interno, clientes e consultas operacionais

## Contratos minimos antes da extracao
- Cada servico extraido deve ter responsabilidade explicita sobre dados, APIs e eventos publicados.
- Eventos entre servicos precisam de nome canonico, payload versionado e politica de idempotencia.
- A estrategia de persistencia deve definir claramente o que continua compartilhado na transicao e o que passa a ser responsabilidade exclusiva do servico.
- O modelo de `tenant` precisa existir no contrato antes das extracoes relevantes, mesmo que a ativacao comercial fique para uma fase posterior.

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
3. Definir contratos canonicos de eventos, responsabilidade sobre dados e identificacao de `tenant`
4. Extrair `catalog-service` e `backoffice-service`
5. Extrair `orders-service` e `delivery-service`
6. Publicar `delivery_status_updated` e demais eventos operacionais
7. Remover o fallback local quando os servicos estiverem estabilizados

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
