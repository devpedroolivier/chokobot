---
name: trufinha-ops-hardening
description: Use when improving the Chokobot WhatsApp AI operation end to end, especially to reduce hallucinated prices and items, harden confirmation boundaries, fix catalog and payment behavior, align runtime with panel and business state, strengthen human handoff, and turn real conversation failures into deterministic code and test fixes.
---

# Trufinha Ops Hardening

Use this skill when the goal is to apply concrete corrections to the Trufinha operation, not just analyze it.

This skill is for work such as:

- fixing wrong prices, weights, flavors, or item availability
- separating `cardapio` from `opcoes` and item-specific lookup
- preventing “pedido salvo” before real persistence
- improving same-day, cutoff, and timezone behavior
- hardening payment, troco, PIX, and delivery rules
- reducing loops, repeated questions, and confusing summaries
- improving handoff to human with better context
- aligning WhatsApp runtime state, `customer_processes`, and panel visibility
- adding regression tests from real broken conversations

## Start Here

Read these first when relevant:

- `docs/panel-e2e-analysis.md`
- `app/ai/agents.py`
- `app/ai/runner.py`
- `app/ai/tool_execution.py`
- `app/ai/tool_registry.py`
- `app/ai/tools.py`
- `app/ai/policies.py`
- `app/infrastructure/gateways/local_catalog_gateway.py`
- `app/application/use_cases/process_inbound_message.py`
- `app/application/use_cases/manage_human_handoff.py`
- `app/application/use_cases/panel_dashboard.py`
- `app/api/routes/webhook.py`
- `app/security.py`

Inspect these artifacts when diagnosing real failures:

- `dados/domain_events.jsonl`
- `dados/atendimentos.txt`
- SQLite tables: `clientes`, `customer_processes`, `encomendas`, `entregas`, `pedidos_cafeteria`

## Primary Error Classes

Classify every failure before editing:

1. Catalog truth failure
- Item exists but bot denied it
- Item does not exist but bot invented it
- Weight, flavor, or option answered without catalog support

2. Pricing failure
- Wrong price
- Right base price but wrong additional or Kit Festou math
- Placeholder value like `R$XX`
- Bot quoted price without deterministic source

3. Confirmation failure
- Bot implied order was saved before persistence
- Draft or process was treated like confirmed order
- Summary was presented as final before explicit confirmation

4. Flow/CX failure
- Question order confused the customer
- Bot repeated itself or looped
- Bot asked for description or internal schema fields too early

5. Routing failure
- `cardapio` and `opcoes` mixed
- Páscoa, cafeteria, pronta entrega, and encomenda crossed
- Same-day logic or time cutoff routed incorrectly

6. Handoff/operations failure
- Bot should have transferred earlier
- Human handoff lacked context
- Panel, runtime, and business state diverged

7. Security/noise failure
- Automated messages entered AI flow
- Webhook or panel protection depended on weak config
- Logs or events exposed more data than needed

## Hardening Workflow

1. Reproduce from real evidence.
- Pull the exact conversation window from `dados/domain_events.jsonl`.
- Identify the first incorrect bot turn, not just the complaint.
- Confirm whether the wrong behavior was in prompting, tooling, persistence, or panel sync.

2. Find the truth source.
- Catalog/item truth: `local_catalog_gateway.py` and `catalogo_produtos.json`
- Cake price truth: `tools.py` plus `services/precos.py`
- Schedule/time truth: `policies.py`, `store_schedule.py`, `datetime_utils.py`
- Persistence truth: `tool_execution.py`, `tools.py`, `customer_processes`, `encomendas`
- Panel truth: `panel_dashboard.py` and repositories

3. Prefer deterministic fixes over prompt-only fixes.
- Use prompts to constrain intent and wording.
- Use tools and runtime to enforce price, payment, confirmation, and catalog truth.
- If a failure can be solved in code, do not leave it only in prompt text.

4. Patch the smallest real boundary.
- Wrong catalog answer: fix lookup or routing, not just wording.
- Wrong price: force canonical price tool, not just “be careful”.
- False confirmation: short-circuit on draft result and gate final save messaging.
- Wrong time: normalize to `America/Sao_Paulo` at the operational layer.

5. Add regression tests from the real case.
- Every production failure should become at least one deterministic test.
- Name tests by business behavior, not implementation trivia.
- Cover both the broken case and the protected case.

## Non-Negotiable Rules

- Do not let the bot quote price from memory when a deterministic source exists.
- Do not let the bot claim an order is saved if `order_id` does not exist.
- Do not invent item, flavor, weight, or availability outside tool output.
- Do not mix `atendimento`, `rascunho`, and `pedido confirmado`.
- Do not rely on UTC for customer-facing operational time.
- Do not leave `combos` or other marketed items in UX copy if there is no structured support for them.

## Preferred Fix Patterns

### 1. Catalog and menu

- General menu request: `get_menu`
- Item-specific request: `lookup_catalog_items`
- If item is not found, answer with “I need to confirm” or route correctly; never synthesize a variant

### 2. Pricing

- Use a canonical pricing tool for cakes, tortas, mesversário, and linha simples
- Include additionals and Kit Festou in the deterministic calculation
- Return backend-generated “official calculated value” text for draft summaries when possible

### 3. Confirmation boundary

- Before explicit confirmation: persist only draft or process
- After explicit confirmation: persist order or delivery and only then allow final saved wording
- If the model tries to say “pedido salvo” while the latest truth is a draft tool result, block and return the draft message instead

### 4. Time and schedule

- Normalize all operational times to `America/Sao_Paulo`
- Treat same-day cutoff and Sunday rules as deterministic business logic
- Keep observability timestamps in UTC if needed, but customer-facing and operation-facing logic must use Brasília time

### 5. Human handoff

- Transfer when the answer is unknown, risky, or blocked by business policy
- Prefer handoff with structured context: what customer wants, what was collected, what failed, what still needs action

## Operational Review Questions

When applying a fix, always answer:

- What truth source should own this answer?
- Can the model still bypass that truth source?
- Could the panel or operator still see the wrong business state?
- What exact customer message would still break this after the fix?
- What test proves that the failure is now blocked?

## Validation

Run the smallest relevant set plus compile checks.

Typical validation commands:

- `python3 -m unittest tests.test_catalog_gateway_lookup tests.test_ai_policies tests.test_ai_easter_flow`
- `python3 -m unittest tests.test_ai_cake_pricing tests.test_ai_tool_execution tests.test_ai_agent_prompts tests.test_message_formatting`
- `python3 -m unittest tests.test_brasilia_timezone tests.test_ai_time_rule tests.test_attention_handoff tests.test_security_hardening tests.test_split_http_smoke`
- `python3 -m unittest tests.test_whatsapp_e2e_panel_flow`
- `python3 -m compileall app tests`

Use E2E when the fix touches:

- confirmation boundaries
- WhatsApp to panel visibility
- handoff state
- persistence timing

## Output Expectations

When using this skill, report:

- what real failure was reproduced
- where the source of truth lived
- what deterministic guardrail was added
- what residual risk remains
- what tests were added or run
