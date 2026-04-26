# Jornada de Pivot — Chokobot → Trufinha

**Início:** 2026-04-25
**Última atualização:** 2026-04-26
**Estado:** 14 commits locais; suíte 351/351 verde; smoke 11/11.

Este documento é o registro narrativo de tudo que foi feito para evoluir
o Chokobot (single-tenant Chokodelícia) em direção ao produto Trufinha
multi-tenant. Complementa:
- `docs/PIVOT_TODO.md` — plano executável
- `docs/MULTI_TENANT.md` — arquitetura alvo
- `docs/PHASE_B_DECISIONS.md` — decisões aprovadas
- `docs/TESTS_TODO.md` — backlog e plano de testes

---

## Resumo em 3 frases

A confeitaria continua atendendo igual: mesmo PIX, mesmo cardápio,
mesmas mensagens, todos os clientes felizes. **A casa foi reformada por
dentro** — fundações, estrutura, instalações elétricas — para aguentar
um segundo andar (segunda confeitaria). Falta só **mudar a fechadura**
(cutover SQLite → Postgres) na janela combinada de terça 09:00 e
**convidar o segundo morador** (segundo tenant piloto).

---

## Cronologia técnica

### Fase A — Fundações (8 commits)

1. **`c5edbb9` Pydantic settings + lazy init + rename Trufinha + tools split (schemas/commons)**
   Fase A.1 (Pydantic v2 com validação tipada), A.2 (zero `get_settings()` em module-load), rename de marca para Trufinha (preservando container/package técnico como chokobot), Fase A.3.2 (extrair Pydantic schemas e helpers genéricos do `tools.py` 2322 → package).

2. **`3515f49` Extract cake domain from tools/__init__.py**
   Fase A.3.3. `tools/cake.py` (740 linhas): constantes, pricing, validações, builders, prepare, get_cake_pricing, get_cake_options. `__init__.py`: 2086 → 1464.

3. **`6a1f5bf` Extract sweet/gift/cafeteria domains**
   Fase A.3.4. `tools/sweet.py`, `tools/gift.py`, `tools/cafeteria.py`, builders compartilhados em `_common.py`. `__init__.py`: 1464 → 704.

4. **`03e6769` Fix 7 pre-existing test failures**
   Frente B.1 do TESTS_TODO. Adiciona `AI_AUTO_SCHEDULE_ENABLED=0` em `scripts/run_tests.py:DEFAULT_ENV`. Suíte vai de 320/327 verde para 327/327.

5. **`8620f54` Replace @lru_cache singletons with tenant-aware ServiceRegistry**
   Fase A.4. Classe `ServiceRegistry` com `_PerTenantCache` por gateway/repo/state-store. `get_*(tenant_id=None)`. Tests trocam `cache_clear()` por `reset_registry()`.

6. **`9aa7d9c` Add Database wrapper as forward-compat for Phase B Postgres pool**
   Fase A.5. `Database` class com pool single-connection RLock-protected. `execute / query_one / query_all / transaction`, todos com `tenant_id` como kwarg silencioso. Legacy `get_connection()` preservado.

7. **`18d7b04` Wire Alembic with idempotent baseline migration**
   Fase A.6. `alembic.ini` + `migrations/env.py` + `script.py.mako` + `0001_baseline_schema` (idempotente, snapshot do schema atual). `alembic current/heads` funcionam.

8. **`cc4be62` Add webhook e2e tests**
   Frente A.2.1 do TESTS_TODO. 14 testes em `tests/test_webhook_endpoint.py` cobrindo HMAC, replay, ignore rules (group/from_me/automated/test_phone), JSON malformado, e o lock por phone (concorrência + cleanup em exception).

### Fase B — Multi-tenant em curso (6 commits)

9. **`dc7904e` Document Phase B blockers awaiting product decisions**
   `docs/PHASE_B_DECISIONS.md` consolida 10 decisões. Posteriormente todas aprovadas com as recomendações.

10. **`45e1583` Add chokobot-postgres service under postgres profile**
    Fase B.1. Serviço Postgres no compose com profile dedicado, volume separado, port 5433, envs em `.env.example`. Não sobe em produção até cutover.

11. **`f804b26` Author Phase B schema migrations**
    Fase B.2. `0002_tenant_tables` (tenants/tenant_config/tenant_knowledge/users + seed Chokodelícia em tenant_id=1) e `0003_tenant_id_on_domain` (adiciona tenant_id em todas as tabelas + outbox + events + reescreve views v_encomendas/v_entregas com tenant_id no SELECT e no JOIN). Postgres-only — não roda contra SQLite.

12. **`cd23663` Add tenant_id to every repository signature**
    Fase B.4. 5 interfaces × 23 métodos com `tenant_id: str | None = None` keyword-only. SQLite impls aceitam e descartam (`del tenant_id`).

13. **`b86695a` Tenant-prefix Redis/SQLite/memory state namespaces**
    Fase B.6. `ConversationStateStore(tenant_id=...)` prefixa namespaces com `tenant:{tenant_id}:`. Backend único compartilhado, isolamento por namespace. `ServiceRegistry.get_state_store(tenant_id)`. **5 testes de isolamento** (`test_state_store_tenant_isolation.py`).

14. **`ebe78a9` Plumb tenant_id through commands, handlers and use cases**
    Fase B.5. `resolve_tenant_id(payload)` em `app/utils/payload.py` (Evolution `instance` → tenant slug; Z-API → None). `HandleInboundMessageCommand` e `GenerateAiReplyCommand` carregam `tenant_id`. Handlers e use cases propagam. **5 testes de propagação** (`test_tenant_id_propagation.py`).

### Total acumulado

| Categoria | Antes | Agora |
|---|---|---|
| Testes na suíte | 327 (7 falhando) | **351 (todos verdes)** |
| Cenários de smoke | 11 | 11 |
| `tools/__init__.py` | 2322 linhas | **704 linhas** |
| Módulos em `tools/` | 1 | 7 |
| Falhas pré-existentes | 7 | 0 |
| Migrations Alembic | 0 (pasta vazia) | **3** (`0001_baseline`, `0002_tenant_tables`, `0003_tenant_id_on_domain`) |
| Tests com `tenant_id` | 0 | **10** (5 isolamento + 5 propagação) |
| Refs hardcoded "Chokodelícia" | 35+ | só nos prompts (Fase C) |
| `get_settings()` em module-load | 60+ | 0 |

---

## O que ainda falta (Fase B)

| Sub-item | Nota |
|---|---|
| **B.3** — Script SQLite → Postgres | Pode ser escrito agora; só roda na janela do cutover |
| **B.7** — Eventos de domínio com `tenant_id` | Pequeno: adicionar campo nos `*Event` dataclasses + persist |
| **B.8** — Cutover real | Janela combinada: **terça 09:00**. Chokodelícia mantém SQLite até lá |
| **Decisão #3** — Identidade do segundo tenant | Bloqueia Fase D, não bloqueia B |

---

## Riscos atuais (e mitigação)

| Risco | Mitigação atual |
|---|---|
| Esquecer `tenant_id` em algum repo silenciar vazamento | Suíte multi-tenant cresce em cada fase. Pré-cutover precisa adicionar AST audit + RLS Postgres (Fase E.4) |
| Cutover corrompe dados | B.3 ainda não foi escrito. Quando for, exige dry-run em staging + backup SQLite + counts validation antes da janela |
| Migrações 0002/0003 acumulam dívida sem rodar | Risco baixo: são código declarativo. CI lint pode validar parsing em cada PR |
| Container `chokobot-postgres` deixa de subir | Está no profile `postgres` — opt-in. `docker compose up` não muda |
| `tenant_id` plumbed mas não usado em todas as queries | Hoje `del tenant_id` em SQLite é intencional (sem coluna). No cutover vira Postgres com filtro real |

---

## Critérios de produto pronto para 2 tenants (do PIVOT_TODO §13)

| Critério | Status |
|---|---|
| Chokodelícia + 2º tenant rodam no mesmo processo | Pré-requisito: B.3 + B.7 + B.8 + Postgres impls dos repos |
| Mensagem de A nunca aparece em B | ✅ Garantido em **state store** (testes); falta nos repos pós-cutover |
| Catálogo/horário/PIX/branding por tenant | Fase C (knowledge per-tenant) |
| Painel `/t/{slug}/*` isolado | Fase D |
| Platform admin lista e cria tenants | Fase D |
| ≥3 cenários de testes 2-tenants paralelos | ✅ **10 já hoje** (state store 5 + propagação 5) |
| Deploy reversível em <30 min | Documentado em `docs/MULTI_TENANT.md §9` |
| Zero "Chokodelícia" hardcoded em código Python | ✅ Fora dos prompts. Prompts viram template per-tenant na Fase C |

---

## Convenções estabelecidas

Estas decisões foram tomadas durante a jornada e devem ser respeitadas
até o cutover:

1. **`tenant_id: str | None = None` keyword-only.** Todo método de domínio aceita. `None` = "default Chokodelícia". Default preserva back-compat single-tenant.
2. **Sem context-vars implícitas.** `tenant_id` flui explícito no parâmetro. (Decisão arquitetural do MULTI_TENANT.md §3.1.)
3. **Nome técnico não muda no cutover de marca.** Package `app/`, container `chokobot_*`, DB path `dados/chokobot.db`. Rename técnico só junto com Postgres.
4. **Migrations apenas Postgres a partir de 0002.** SQLite Chokodelícia fica congelado em 0001 até cutover.
5. **`AI_AUTO_SCHEDULE_ENABLED=0` no env de teste.** Garante determinismo independente do dia.
6. **Tests `*_isolation.py`** em `tests/` para isolamento de tenant. Critério de saída Fase B: ≥10.
7. **Smoke `scripts/smoke_chokodelicia.py`** roda antes de qualquer PR de pivot. 11 cenários determinísticos.

---

## Comandos úteis

```bash
# Suíte completa
.venv/bin/python scripts/run_tests.py

# Smoke determinístico
.venv/bin/python scripts/smoke_chokodelicia.py

# Estado das migrations
.venv/bin/alembic current
.venv/bin/alembic history

# Subir Postgres (só quando preparar cutover)
docker compose --profile postgres up -d chokobot-postgres

# Aplicar migrations contra a URL configurada
.venv/bin/alembic upgrade head
```

---

## Lições aprendidas (até aqui)

1. **Pequenos commits validados** > grandes refactors. Cada subitem foi commit isolado, com suíte verde antes de prosseguir. Reverts ficam triviais.
2. **Backward-compat por default**. `tenant_id=None` em todos os lugares = comportamento inalterado para Chokodelícia. O código está pronto para multi-tenant **antes** de o produto ser multi-tenant.
3. **Documentar antes de codificar fases longas**. PIVOT_TODO + MULTI_TENANT + PHASE_B_DECISIONS evitaram retrabalho.
4. **Profile no docker-compose** em vez de "vai pra prod". `chokobot-postgres` está no compose mas só sobe quando explicitado.
5. **Testes de isolamento** desde a primeira parte multi-tenant. Sem testes contraste (2 tenants), regressão de vazamento passaria silenciosa.

---

## Próximo passo natural

1. **B.3** — Escrever `scripts/migrate_sqlite_to_postgres.py`. Não roda contra produção; é código que viaja.
2. **B.7** — Eventos com `tenant_id`. Adicionar campo nos 5 `*Event` dataclasses + adaptar `persist_domain_event`.
3. **Identificar 2º tenant** (decisão #3 ainda em aberto).
4. **Marcar janela de cutover** com Chokodelícia (terça 09:00 confirmada como horário; falta data específica).
