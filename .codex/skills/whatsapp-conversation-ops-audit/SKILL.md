---
name: whatsapp-conversation-ops-audit
description: Use when deeply analyzing the Chokobot WhatsApp conversation flow end to end, including customer context, runtime conversation state, handoff, draft versus confirmed order boundaries, persistence, panel synchronization, operational bottlenecks, performance risks, and opportunities to improve both client interaction and back-office flow.
---

# WhatsApp Conversation Ops Audit

Use this skill when the goal is not just to change code, but to understand the real behavior from WhatsApp inbound message to panel visibility.

This skill is for diagnosing:

- what the customer is trying to do
- what state the conversation is actually in
- where the process gets stuck
- when a draft should become a confirmed order
- how runtime state and persisted state diverge
- why the panel may show too early, too late, or with weak signal
- what to improve in both performance and customer interaction

## Start Here

Read these first when relevant:

- `docs/panel-e2e-analysis.md`
- `app/api/routes/webhook.py`
- `app/application/use_cases/process_inbound_message.py`
- `app/application/use_cases/panel_dashboard.py`
- `app/application/use_cases/manage_human_handoff.py`
- `app/application/use_cases/process_delivery_flow.py`
- `app/application/use_cases/process_cesta_box_flow.py`
- `app/application/use_cases/process_cafeteria_flow.py`
- `app/ai/tool_execution.py`
- `app/ai/tools.py`

Inspect these artifacts when they matter:

- `dados/atendimentos.txt`
- `dados/domain_events.jsonl`
- SQLite tables: `clientes`, `customer_processes`, `encomendas`, `entregas`, `pedidos_cafeteria`

## Audit Questions

### 1. Customer Intent

- What is the customer trying to buy or solve?
- Is the bot collecting enough context to understand that intent?
- Is the flow forcing the customer through unnecessary steps?
- Is the customer asked for confirmation at the right time?

### 2. Runtime Versus Business State

- Does the runtime state (`ai_sessions`, `estados_*`, `recent_messages`) match the business meaning of the conversation?
- Should this item still be “atendimento” or already be “pedido confirmado”?
- Is a handoff being treated as conversation state only, or leaking into the operational board?

### 3. Confirmation Boundary

- Is explicit confirmation really required before persistence?
- Are tools or flows persisting too early?
- Is the panel showing orders that are still drafts?
- Is there a missing intermediate state such as `rascunho`, `orcamento`, or `aguardando_confirmacao`?

### 4. WhatsApp to Panel Connection

- What exact path moves a conversation into panel visibility?
- Is the transition going through runtime state, `customer_processes`, `encomendas`, or `entregas`?
- Is the same process represented by more than one source of truth?
- Can the panel explain why something appears there?

### 5. Bottlenecks and Failures

- Where do conversations stall?
- Which messages or steps cause handoff?
- Which flow asks for data repeatedly or unclearly?
- Where do confirmation blocks occur?
- Where is there operational ambiguity between atendimento and produção?

### 6. Performance

- Is the analysis path doing repeated reads over the same customer/process/order?
- Are snapshot and panel reads reconstructing state expensively?
- Is runtime-only state forcing the panel to do extra work to understand current status?
- Are there schema/index/query gaps around `customer_processes`, `clientes`, `encomendas`, or `entregas`?

## Workflow

1. Map the path from inbound webhook to persisted state.
   Trace:
   - webhook receive
   - inbound handling
   - AI/session logic
   - draft/process persistence
   - order creation
   - panel snapshot/render

2. Separate entities clearly:
   - contato/cliente
   - atendimento em andamento
   - rascunho/processo
   - pedido confirmado
   - operação/logística

3. Compare three sources side by side when possible:
   - runtime state
   - persisted process/order state
   - what the panel shows

4. Identify mismatch classes:
   - pedido salvo cedo demais
   - conversa ativa sem visibilidade operacional
   - handoff humano sem trilha suficiente
   - pedido confirmado sem contexto suficiente
   - painel mostrando coisa que não é pedido

5. Recommend improvements in groups:
   - customer interaction
   - confirmation logic
   - state model
   - panel visibility and operator UX
   - performance/query/schema

## Preferred Deliverable Shape

When this skill is used for analysis, structure findings in this order:

1. Current flow summary
2. Customer-experience bottlenecks
3. Confirmation and persistence risks
4. WhatsApp-to-panel sync issues
5. Performance/SQLite/payload issues
6. Recommended next changes

## Project Rules

- Do not assume that “cliente” means “pedido”.
- Do not treat runtime state as the same thing as confirmed business state.
- Preserve the distinction between `atendimento` and `operação`.
- Prefer explaining where truth lives today before proposing new truth.
- If reviewing a real conversation artifact, be careful not to overgeneralize from one case.

## Validation

Useful checks after code changes:

- `python3 -m unittest tests.test_panel_process_cards tests.test_panel_sync_overview tests.test_frontend_snapshot_routes`
- `python3 -m unittest tests.test_order_write_repository tests.test_customer_process_repository`
- `python3 -m compileall app tests`
- `cd frontend && npm run build` when panel/admin UI changes are involved

## Output Expectations

When using this skill, report:

- where the conversation truly is in the business flow
- what the customer likely perceives
- what the operator sees in the panel
- what source of truth mismatch exists
- what should change in confirmation, persistence, panel flow, or performance
