# Contratos de Eventos

## Objetivo
Definir o contrato canonico minimo para eventos internos durante a fase de transicao entre monolito modular e servicos extraidos.

## Envelope canonico
Todo evento publicado entre limites de servico deve seguir este envelope logico:

```json
{
  "event_name": "order.created",
  "event_version": 1,
  "event_id": "uuid",
  "occurred_at": "2026-03-16T19:00:00Z",
  "producer": "orders-service",
  "tenant_id": "default",
  "aggregate_id": "42",
  "correlation_id": "request-or-flow-id",
  "payload": {}
}
```

## Regras obrigatorias
- `event_name` usa nome canonico estavel e sem ambiguidade de origem.
- `event_version` sobe apenas quando houver mudanca breaking no payload.
- `event_id` precisa ser unico para permitir idempotencia no consumo.
- `tenant_id` existe desde ja no contrato, mesmo quando o runtime ainda operar com tenant unico.
- `correlation_id` deve reaproveitar `request_id` ou identificador equivalente do fluxo.

## Eventos canonicos iniciais
- `message.received`
  - produtor inicial: `edge-gateway`
  - agregado: mensagem inbound
  - uso: auditoria, deduplicacao e analytics operacional
- `ai.reply.generated`
  - produtor inicial: `conversation-service`
  - agregado: resposta ao cliente
  - uso: trilha de atendimento e replay operacional
- `order.created`
  - produtor inicial: `orders-service`
  - agregado: pedido persistido
  - uso: backoffice, entrega e notificacoes internas
- `delivery.created`
  - produtor inicial: `delivery-service`
  - agregado: agendamento ou abertura de entrega
  - uso: operacao, painel e trilha logistica
- `delivery.status_updated`
  - produtor inicial: `delivery-service`
  - agregado: entrega
  - uso: sincronizacao de status e automacoes

## Responsabilidade inicial por limite de servico
- `edge-gateway`: publica somente eventos de entrada e seguranca de webhook.
- `conversation-service`: publica eventos de orquestracao conversacional e handoff.
- `orders-service`: publica eventos ligados a criacao e mudanca de pedido.
- `delivery-service`: publica eventos ligados a entrega, retirada e status.
- `backoffice-service`: consome eventos operacionais; nao deve ser dono do contrato de dominio.

## Politica de idempotencia
- Consumidores devem deduplicar por `event_id`.
- Reprocessamento do mesmo evento nao pode criar pedido ou entrega duplicados.
- Eventos de escrita devem registrar origem e identificador externo quando houver retry.

## Mapeamento atual
- `MessageReceivedEvent` corresponde a `message.received`.
- `AiReplyGeneratedEvent` corresponde a `ai.reply.generated`.
- `OrderCreatedEvent` corresponde a `order.created`.

Enquanto o barramento local continuar em processo, o nome das classes Python pode divergir do nome canonico do evento. O contrato oficial para futuras extracoes passa a ser o nome canonico acima.
