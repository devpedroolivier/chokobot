# Modelo Estrutural de Tenant

## Objetivo
Registrar a decisao estrutural minima de multi-tenant antes da consolidacao final da camada de dados.

## Decisao
O sistema passa a assumir `tenant_id` como campo obrigatorio de contrato, mesmo operando inicialmente com um tenant padrao chamado `default`.

## Regras por camada
- APIs internas e externas:
  - devem aceitar identificacao de tenant por header, token ou resolucao de contexto
  - devem propagar `tenant_id` para comandos, eventos e logs
- Eventos:
  - todo envelope canonico inclui `tenant_id`
  - consumidores rejeitam eventos sem tenant resolvido
- Persistencia:
  - novas tabelas, migracoes e repositorios devem prever `tenant_id` como coluna ou chave de particionamento
  - consultas operacionais devem filtrar por tenant de forma explicita
- Observabilidade:
  - logs estruturados devem aceitar `tenant_id` como campo opcional desde ja
  - metricas agregadas precisam manter possibilidade de segmentacao por tenant

## Estrategia de transicao
1. Fase atual:
   - runtime assume `tenant_id=default`
   - contratos e novas abstrações já carregam o conceito
2. Fase de consolidacao de dados:
   - schema e repositorios passam a persistir `tenant_id`
   - backfills usam `default` para registros legados
3. Fase de produto replicavel:
   - autenticacao, painel e APIs resolvem tenant dinamicamente

## Limites iniciais de ownership
- `edge-gateway` resolve ou propaga o tenant da requisicao.
- `conversation-service` nao decide tenant; apenas consome o contexto resolvido.
- `orders-service` e `delivery-service` persistem e validam isolamento por tenant.
- `backoffice-service` opera sempre em escopo de tenant explicito.

## Impacto pratico na Sprint 5
- Baseline de migracao deve considerar `tenant_id`.
- Repositorios novos nao devem nascer sem estrategia de isolamento.
- Qualquer extracao de servico sem `tenant_id` no contrato passa a ser considerada incompleta.
