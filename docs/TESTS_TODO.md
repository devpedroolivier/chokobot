# TESTS TODO — Trufinha

**Data:** 2026-04-25
**Escopo:** três frentes — corrigir falhas pré-existentes, fechar lacunas
de cobertura no estado atual e desenhar o plano de testes da Fase B
multi-tenant. Complementa `docs/PIVOT_TODO.md`.

> Suíte hoje: **327 testes em 56 arquivos** (6 excluídos como
> exploratórios). Smoke determinístico em `scripts/smoke_chokodelicia.py`
> (11 cenários). **0** testes com `tenant_id`, **0** com RLS.

---

## Resumo executivo

| Frente | Estado | Esforço | Bloqueia |
|---|---|---|---|
| **B — Corrigir 7 falhas pré-existentes** | Falham na main há tempo, **não** introduzidas por mim | 2–3h | Confiança no CI / pré-Fase B |
| **A — Lacunas de cobertura no estado atual** | Suíte boa em prompts/regras; fraca em rotas, repos, painel, observability | 3–5 dias | Qualidade / regressão |
| **C — Testes para Fase B (multi-tenant)** | A escrever do zero | 5–7 dias (junto da implementação Fase B) | Onboarding 2º tenant |

Recomendação: **B agora** (ganho de confiança imediato), **A em paralelo** quando houver folga, **C escrito antes do código de Fase B** (TDD para isolamento).

---

## FRENTE B — Corrigir 7 falhas pré-existentes

Falhas estáveis na main (verificadas 2026-04-25 com `git stash` + `run_tests.py`).

### B.1 — Cluster auto-schedule (6 testes)

**Falham porque:** o `.env`/test env tem `AI_AUTO_SCHEDULE_ENABLED=1` (default em `app/settings.py`). O dia atual (sábado) cai dentro da janela "off" (sex 19h → seg 6h). O handler entra no fast-path `handler_ai_schedule_off` antes de chamar `responder_usuario` ou checar opt-out. Mocks dos testes nunca são exercitados.

**Testes afetados:**
- `tests.test_store_closure.StoreClosureTests.test_handler_respects_store_closed_flag_and_skips_ai_flow`
- `tests.test_process_inbound_message.ProcessInboundMessageTests.test_customer_opt_out_command_pauses_phone_automation`
- `tests.test_process_inbound_message.ProcessInboundMessageTests.test_paused_phone_ignores_messages_until_menu_reactivates`
- `tests.test_process_inbound_message.ProcessInboundMessageTests.test_paused_phone_reactivation_honors_configured_delay`
- `tests.test_process_inbound_message.ProcessInboundMessageTests.test_phone_opt_out_auto_reactivates_after_timeout`
- `tests.test_process_inbound_message.ProcessInboundMessageTests.test_reactivate_with_ativar_chat_while_handoff_is_active`

**Fix proposto:**
- [ ] Em `scripts/run_tests.py`, adicionar `"AI_AUTO_SCHEDULE_ENABLED": "0"` em `DEFAULT_ENV`.
- [ ] Validar que nenhum teste **espera** auto-schedule on por default. Caso algum espere, ele deve ligar explicitamente via `patch.dict(os.environ, ...)`.
- [ ] Critério: 6 testes voltam a verde em qualquer dia da semana.

**Impacto cruzado:** o smoke `scripts/smoke_chokodelicia.py` já desliga (`AI_AUTO_SCHEDULE_ENABLED=0`). Padronizar o env de teste.

### B.2 — `test_contact_to_confirmation_moves_from_whatsapp_flow_to_panel_order`

**Falha em:** `assertIn("oi, quero um bolo com entrega", whatsapp_card["last_message"])` — mas a mensagem real é `"Bolo de chocolate • 25/03/2026 • 14:00"`.

**Hipótese de causa raiz:** o teste cria um pedido salvo. O `last_message` do card de WhatsApp é sobrescrito pelo resumo do pedido em vez de manter o texto original do cliente. Pode ser comportamento legítimo do produto que o teste não acompanhou — ou regressão da Sprint 5.

**Investigação necessária:**
- [ ] Ler `tests/test_whatsapp_e2e_panel_flow.py:153` em conjunto com o `painel_snapshot` para entender o que `whatsapp_card["last_message"]` deveria mostrar.
- [ ] Ver se houve mudança em `panel_dashboard.py` ou `process_inbound_message.py` que mudou o campo.
- [ ] Decidir: ajustar teste para refletir comportamento atual, ou consertar produto se for regressão real.

### B.3 — Saída

- [ ] Após B.1+B.2 fechados: `python scripts/run_tests.py` retorna `OK` em qualquer ambiente / dia da semana.
- [ ] CI pipeline limpo torna detecção de regressões nas Fases B/C/D 100x mais útil.

---

## FRENTE A — Lacunas de cobertura no estado atual

### A.1 — Onde a cobertura é forte (manter)
- AI prompts e roteamento (`test_ai_agent_prompts`, `test_ai_policies`, `test_sprint5_regression`)
- Regras comerciais (`test_commercial_rules`, `test_ai_payment_rules`, `test_ai_time_rule`)
- Pricing e validação de bolo (`test_ai_cake_pricing`, `test_ai_cake_options`, `test_delivery_and_line_rules`)
- Páscoa (`test_ai_easter_flow`)
- Repositórios SQLite (`test_customer_repository`, `test_order_write_repository`, `test_customer_process_repository`)
- Gateways de mensagem (`test_messaging_gateway`, `test_evolution_messaging_gateway`)
- Observabilidade básica (`test_observability_hardening`)
- Schema guard (`test_sqlite_schema_indexes`)

### A.2 — Lacunas críticas

#### A.2.1 — Webhook end-to-end com dedup, lock, replay
**Estado:** existe `test_normalize_incoming.py` cobrindo parsing. **Não há** teste do fluxo completo `/api/webhook` que exercita: assinatura HMAC, replay window, lock por phone, ignore de from_me/group/automated.
- [ ] Criar `tests/test_webhook_endpoint.py` com `httpx.AsyncClient` ou `TestClient` cobrindo:
  - Webhook válido → 200 + dispatch
  - Replay (mesmo `message_id` 2x) → 200 ignored
  - Mensagem de grupo → ignored
  - Phone de teste → ignored
  - HMAC inválido → 401 (quando `WEBHOOK_VERIFY_ENABLED=1`)
  - Lock por phone serializa duas mensagens do mesmo número

#### A.2.2 — `runner.py` como caixa-preta
**Estado:** smoke cobre os caminhos determinísticos (PIX, Páscoa, opt-out, etc.). **Não há** teste com mock de OpenAI cobrindo o LOOP de tool-calling, transferência entre agentes, retries, falhas do LLM.
- [ ] Criar `tests/test_ai_runner_completion.py`:
  - Mock OpenAI retornando `transfer_to_agent` → muda `current_agent`
  - Mock retornando tool call inválida → resposta de erro, sem crash
  - Mock retornando tool call que falha → fallback gracioso
  - Limite de iterações no loop (sem infinite loop)

#### A.2.3 — Painel admin (FastAPI rotas)
**Estado:** existe `test_panel_*` (snapshot, orders, conversation_actions, process_cards/sections, sync_overview, whatsapp_cards) e `test_admin_frontend_redirects`. Bom. Lacunas:
- [ ] Auth: HTTP Basic com credenciais corretas/erradas (atualmente só `test_security_hardening`)
- [ ] CRUD `/api/clientes`, `/api/encomendas` em modo HTTP (e não só repo)
- [ ] Status updates de pedido pelo painel (mark ready, mark delivered)
- [ ] Healthz/readyz/metrics retornam estrutura esperada

#### A.2.4 — Outbox + reprocess
**Estado:** `scripts/reprocess_outbox.py` existe; **não há** teste cobrindo retomada de mensagens enfileiradas após gateway 5xx.
- [ ] `tests/test_outbox_reprocess.py`: gateway falha → enfileira → reprocess → gateway sucede → arquivo limpo.

#### A.2.5 — Evolution gateway: connection state e QR
**Estado:** `test_evolution_messaging_gateway` cobre só `send_text`. Quando ligarmos 2º tenant na Fase B, vamos depender de `instance/create`, `instance/connect`, `CONNECTION_UPDATE` webhook.
- [ ] `tests/test_evolution_lifecycle.py`: criar instance, gerar QR, ler connectionState (mocked HTTP).

#### A.2.6 — Rate limit e circuit breaker
**Estado:** **não existe**. Mencionado no PIVOT_TODO Fase E.2.
- [ ] Por enquanto: spec de comportamento esperado em comentário em `test_messaging_gateway` ou TODO. Implementar testes junto com a feature.

#### A.2.7 — Migrações Alembic
**Estado:** `migrations/versions/` vazio. Nenhum teste.
- [ ] Quando Fase A.6 (Alembic) for feita: `tests/test_migrations.py` que aplica migrations num DB temporário e verifica schema.

#### A.2.8 — Sub-agentes individualmente
**Estado:** prompts são testados via `assertIn` (regras textuais). Comportamento via OpenAI fica nos arquivos excluídos (`test_ai_advanced`, `test_ai_agent`, `test_ai_all_flows`).
- [ ] **Decidir:** ou esses arquivos voltam para suíte com OpenAI mocked, ou viram suíte separada `make test-ai-fuzzy` que roda só localmente (custa $$).

### A.3 — Fluxos de pedido determinísticos (smoke expandido)

O `smoke_chokodelicia.py` cobre 11 caminhos. Vale expandir para:
- [ ] Pedido completo de bolo via `create_cake_order` (mock gateways) → encomenda persistida + draft confirmation
- [ ] Pedido completo cafeteria via `create_cafeteria_order` → idem
- [ ] Pedido com Kit Festou ofertado pós-confirmação
- [ ] Cesta personalizada → handoff (não escala)
- [ ] "Combo Relâmpago" terça → aceito; outros dias → rejeitado com mensagem correta

Hoje esses cenários existem como unit tests mas o smoke acaba dando uma visão de produto que vale ter.

---

## FRENTE C — Testes para Fase B (multi-tenant)

> Esta frente **só faz sentido escrever depois de aprovar Fase B**
> e idealmente **antes** de implementar (TDD).
> Premissa: tenant_id em DB, Redis prefixado, repos recebem tenant_id,
> middleware resolve tenant no edge.

### C.1 — Fundação: harness com 2 tenants

- [ ] **`tests/multi_tenant/conftest.py`** (ou helper se mantermos unittest):
  - Fixture `tenant_a` e `tenant_b` que criam rows em `tenants` + `tenant_config` no Postgres de teste
  - Cleanup após cada teste (TRUNCATE com CASCADE ou `BEGIN; ROLLBACK;`)
  - Helper `as_tenant(tenant_id)` que injeta `tenant_id` em request.state

- [ ] **DB de teste:** Postgres em container ephemeral (testcontainers) ou `dados/test.db` SQLite com `tenant_id` para os primeiros testes pré-cutover.

### C.2 — Isolamento de dados (repo level)

Cada repository ganha `tenant_id` na assinatura. Testes:
- [ ] `tests/multi_tenant/test_customer_isolation.py`:
  - Inserir `Cliente A` em tenant_a, `Cliente A` (mesmo telefone) em tenant_b
  - `get_customer_by_phone(tenant_a, phone)` retorna A do tenant_a
  - `get_customer_by_phone(tenant_b, phone)` retorna A do tenant_b
  - `list_customers(tenant_a)` não vê clientes de tenant_b
- [ ] `tests/multi_tenant/test_order_isolation.py` — idem para encomendas
- [ ] `tests/multi_tenant/test_delivery_isolation.py`
- [ ] `tests/multi_tenant/test_customer_process_isolation.py`

### C.3 — Isolamento de Redis

- [ ] `tests/multi_tenant/test_redis_isolation.py`:
  - `tenant:1:state:session:5511...` setado em tenant 1
  - `keys()` filtrado por tenant 1 só retorna chaves de tenant 1
  - Listar `KEYS *` mostra prefixos distintos

### C.4 — Isolamento de eventos / outbox

- [ ] `tests/multi_tenant/test_events_isolation.py`:
  - Publicar `MessageReceivedEvent` em tenant_a e tenant_b
  - Tabela `events` (ou JSONL com tenant_id) tem ambos
  - Query `WHERE tenant_id = a` retorna só os de A

### C.5 — Webhook resolve tenant correto

- [ ] `tests/multi_tenant/test_webhook_routing.py`:
  - Webhook com `payload.instance="tenant_a_instance"` → `request.state.tenant_id = a.id`
  - Webhook com `payload.instance="tenant_b_instance"` → `b.id`
  - Webhook com instance desconhecida → 404
  - Mensagem do tenant_a NÃO aparece nos pedidos do tenant_b

### C.6 — Config / knowledge per-tenant

- [ ] `tests/multi_tenant/test_tenant_config.py`:
  - tenant_a tem `pix_key="A_KEY"`, tenant_b tem `pix_key="B_KEY"`
  - Pergunta de PIX no fluxo de A retorna A_KEY; B retorna B_KEY
  - Mesma lógica para taxa entrega, horários, branding
- [ ] `tests/multi_tenant/test_tenant_knowledge.py`:
  - tenant_a tem catálogo "bolo_traditional"; tenant_b NÃO tem
  - `lookup_catalog_items` no contexto B → "não encontrei" (não vaza A)

### C.7 — Prompts parametrizados

- [ ] `tests/multi_tenant/test_prompt_composition.py`:
  - Compose prompt com `tenant_name="Chokodelícia"` → contém "Chokodelícia"
  - Compose com `tenant_name="Doce Sonhos"` → contém "Doce Sonhos", **não** "Chokodelícia"
  - Mensagem de boas-vindas de B usa nome de B

### C.8 — Painel: roteamento `/t/{slug}/*`

- [ ] `tests/multi_tenant/test_panel_routing.py`:
  - `GET /t/chokodelicia/dashboard` com sessão tenant_admin de B → 403
  - `GET /t/chokodelicia/dashboard` com sessão tenant_admin de A → 200
  - `GET /admin` com platform_admin → vê os 2 tenants
  - `GET /admin` com tenant_admin → 403

### C.9 — Concurrent operation (carga)

- [ ] `tests/multi_tenant/test_concurrent_isolation.py`:
  - 2 mensagens chegam **simultaneamente**, uma para cada tenant
  - Asyncio gather com 2 webhooks paralelos
  - Cada uma deve ser persistida com `tenant_id` correto
  - Nenhuma mensagem aparece no banco do tenant errado

### C.10 — Defesa em profundidade: RLS Postgres (Fase E.4)

- [ ] `tests/multi_tenant/test_rls_enforcement.py`:
  - Conexão setando `SET app.tenant_id = 1`
  - `SELECT * FROM clientes` (sem WHERE) só retorna tenant 1
  - Repo bug que esquece WHERE não vaza dados (RLS bloqueia)
  - Conexão sem `SET` → policy default deny

> RLS é teste de defesa: garante que mesmo se um repo for refatorado errado, o vazamento é bloqueado pelo Postgres.

### C.11 — Adaptar testes existentes

A maioria dos testes atuais assume single-tenant implícito. Para virar multi-tenant:

- [ ] **Decisão de design:** todo teste que cria customer/order ganha um `default_tenant_id=1` (constante de teste). Ou: fixture `tenant` que injeta em todos os repos.
- [ ] **Estimativa:** ~30 arquivos precisam de pequeno ajuste (passar tenant_id em chamadas de repo). Bulk-edit factível.
- [ ] **Não-regressão:** testes single-tenant existentes devem continuar verdes contra o seed `tenant_id=1` representando Chokodelícia.

### C.12 — Smoke multi-tenant

- [ ] `scripts/smoke_multitenant.py`:
  - Conversa simulada com tenant A + tenant B em paralelo
  - Cada um vê seu próprio catálogo, PIX, branding
  - Nenhum log/evento mistura os 2

---

## Convenções de teste para Fase B

| Convenção | Razão |
|---|---|
| Sufixo `_isolation` em testes que validam não-vazamento | Fácil de identificar e rodar como suíte específica |
| Diretório `tests/multi_tenant/` separado | Permite `make test-multitenant` independente |
| Fixture `default_tenant_id=1` para tests legados | Reaproveita testes single-tenant pós-cutover |
| Sempre 2 tenants nos testes de isolamento (não 1) | Single-tenant não detecta vazamento — precisa do contraste |
| Mock de OpenAI/Evolution com tenant context no payload | Garante que `tenant_id` passa ponta-a-ponta |

---

## Métrica de saída

A Fase B só pode ser declarada "pronta" quando:

- [ ] Suíte single-tenant continua verde (incluindo os 7 da frente B corrigidos)
- [ ] **≥ 10 testes** novos com `_isolation` no nome, todos verdes
- [ ] Smoke multi-tenant passa
- [ ] Coverage report mostra que **toda** chamada de repo recebe `tenant_id` (varredura AST)
- [ ] Linter custom: warning quando alguém adiciona `SELECT/UPDATE/DELETE` sem `WHERE tenant_id` em SQL raw

---

## Ordem de execução sugerida

```
Hoje                                  ← B.1 + B.2 (corrige 7 falhas)
                                      ← A.2.1 (webhook e2e)
                                      ← A.2.4 (outbox reprocess)
Antes de Fase A.4 / A.5               ← A.2.2 (runner caixa-preta com mock OpenAI)
Antes de Fase B começar               ← C.1 (harness 2 tenants no Postgres)
Junto com Fase B.4 (repos)            ← C.2, C.3 (isolamento data + redis)
Junto com Fase B.7 (events)           ← C.4
Junto com Fase B.5 (use cases)        ← C.5
Junto com Fase C (config/knowledge)   ← C.6, C.7
Junto com Fase D (painel)             ← C.8
Antes do cutover                      ← C.9, C.12 (concorrência + smoke)
Junto com Fase E.4 (RLS)              ← C.10
Bulk antes do cutover                 ← C.11 (adaptar legados)
```

---

## Riscos específicos da frente C

| Risco | Mitigação |
|---|---|
| Tests com Postgres em container ficam lentos no CI | Reusar instance via `setUp/tearDown` em DB transaction; rollback ao invés de drop |
| Esquecer `tenant_id` em algum repo passa nos testes single-tenant | Suíte multi-tenant + audit AST que falha o build se algum repo público não recebe tenant_id |
| Migration bug deixa coluna NULL em produção | `tenant_id NOT NULL` desde a primeira migration; teste de migration valida |
| Dois tenants compartilharem mesmo OpenAI key estoura quota | Telemetria desde C.6 + circuit breaker (Fase E.2) |

---

## Referências

- `docs/PIVOT_TODO.md` — plano da pivotagem completa
- `docs/MULTI_TENANT.md` — arquitetura alvo
- `PLANO_ACAO_AUDITORIA.md` Fase 5 — testes de regras de negócio já fechados
- `scripts/smoke_chokodelicia.py` — smoke determinístico atual
- `scripts/run_tests.py` — orchestrator da suíte (precisa do fix B.1)
