---
name: whatsapp-e2e-panel-flow
description: Use when creating, strengthening, or auditing complete end-to-end tests for the Chokobot flow from the customer's first WhatsApp contact through confirmation, order persistence, and final visibility in the panel.
---

# WhatsApp E2E Panel Flow

Use this skill when the goal is to validate the full customer journey with real or near-real test coverage:

- customer sends the first WhatsApp message
- bot or humano handles the conversation
- data collection and confirmation happen
- order is persisted only when appropriate
- the confirmed order appears in the operational panel

## Main Use Cases

- create or improve E2E tests for WhatsApp -> pedido -> painel
- verify confirmation boundaries before persistence
- diagnose why a conversation does not become a panel-visible order
- validate the sync between runtime conversation state, `customer_processes`, and `encomendas`
- lock the panel snapshot contract with end-to-end assertions before and after confirmation

## Focus Areas

- `app/api/routes/webhook.py`
- `app/application/use_cases/process_inbound_message.py`
- `app/application/use_cases/process_delivery_flow.py`
- `app/application/use_cases/process_cafeteria_flow.py`
- `app/application/use_cases/process_cesta_box_flow.py`
- `app/ai/tool_execution.py`
- `app/ai/tools.py`
- `app/application/use_cases/panel_dashboard.py`
- `app/api/routes/painel.py`
- `tests/test_e2e.py`
- `tests/test_split_http_smoke.py`
- `tests/test_whatsapp_e2e_panel_flow.py`
- panel/process/snapshot tests

## E2E Questions To Answer

### 1. Contact and Intake

- Did the inbound webhook normalize the message correctly?
- Was the customer/contact saved?
- Was the message deduplicated correctly?
- Did the conversation enter the right flow?

### 2. Conversation and Context

- Is the current customer intent clear?
- Is the conversation in bot flow, handoff humano, or process draft?
- Is enough context collected before asking for confirmation?

### 3. Confirmation Boundary

- Was the order only persisted after explicit confirmation?
- If not confirmed, did it remain only as draft/process?
- Does the panel distinguish draft from confirmed order?

### 4. Panel Visibility

- Did the confirmed order appear in the operational panel?
- Did the WhatsApp side appear in atendimento/operacoes with correct status?
- Can the operator understand what happened in the conversation from the panel?
- Before confirmation, does the snapshot keep the flow as conversation/process instead of confirmed order?
- After confirmation, does the flow leave the active conversation view and appear in orders/kanban?

## Workflow

1. Trace the exact E2E path:
   - webhook
   - inbound handling
   - AI/manual flow
   - process persistence
   - order creation
   - panel snapshot / admin screen

2. Define the scenario under test:
   - first contact only
   - draft without confirmation
   - explicit confirmation and order creation
   - human handoff
   - delivery versus retirada

3. Prefer test coverage in layers:
   - focused unit tests for confirmation logic
   - integration tests for repository/process persistence
   - panel snapshot contract tests
   - E2E/smoke test for the complete business path

4. Prefer real repositories and local gateways over mocks when feasible:
   - temporary SQLite database
   - `criar_tabelas()` plus `ensure_views()`
   - injected repositories into `painel_snapshot`
   - stubbed event bus only when avoiding side effects matters

5. Assert both sides of the boundary:
   - before confirmation: process/WhatsApp visible, no order in operations
   - after confirmation: order visible in operations, process no longer active

## Test Construction Guidance

Prefer a complete test to answer these checkpoints in one flow:

- inbound message normalized and customer saved
- draft/process persisted while confirmation is still pending
- panel snapshot reflects the conversation/process state before conversion
- explicit confirmation creates the order and delivery rows
- converted process no longer appears as active in `customer_processes`
- panel snapshot now reflects the confirmed order in `operational_orders` and `kanban_columns`

## Project Rules

- Do not treat `cliente` as `pedido`.
- Do not create orders before explicit business confirmation.
- Keep the distinction between atendimento and operação.
- Prefer `customer_processes` as persisted process history when available.
- Use runtime state only as fallback or support, not as primary business truth.

## Validation

Useful checks:

- `python3 -m unittest tests.test_ai_tool_execution`
- `python3 -m unittest tests.test_order_flows tests.test_order_write_repository`
- `python3 -m unittest tests.test_panel_process_cards tests.test_panel_whatsapp_cards tests.test_panel_snapshot_payload`
- `python3 -m unittest tests.test_whatsapp_e2e_panel_flow`
- `python3 -m unittest tests.test_e2e tests.test_split_http_smoke`
- `python3 -m compileall app tests`

If `pytest` is available, broader suites are fine, but do not assume it exists.

## Output Expectations

When using this skill, report:

- what scenario was validated
- where the flow broke or succeeded
- whether the order stayed draft or became confirmed
- whether the panel reflected both conversation and confirmed order correctly
- what tests ran
