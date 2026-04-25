# Multi-tenant — virar produto

**Status:** proposta — aguardando aprovação antes de implementar.
**Data:** 2026-04-24.
**Objetivo:** transformar o Chokobot (hoje single-tenant dedicado à
Chokodelícia) em um produto SaaS que hospeda múltiplos clientes (cada um
com seu WhatsApp, catálogo, regras e painel).

---

## 1. Decisões tomadas

| Decisão | Escolha |
|---|---|
| Isolamento de dados | **Postgres único com `tenant_id`** em cada tabela |
| Escopo inicial | **2 tenants no ar** ao fim da Fase 1 (Chokodelícia + um segundo real) |
| Onboarding | **Concierge** (manual pela equipe) nas Fases 0–2; self-service adiado |
| SQLite | **Corte imediato** (janela curta de downtime) — sem convivência dual |

Decisões derivadas:
- Backend **um processo** servindo todos os tenants (não um processo por tenant).
- Evolution API: **uma instância por tenant** no mesmo servidor Evolution
  (suportado nativo via `/instance/create`).
- OpenAI: **uma chave compartilhada** no começo (custos vêm do billing agregado;
  segregação de custo por tenant = telemetria, não infra).
- Knowledge (menus, catálogos, prompts de agente específicos): **por tenant**,
  persistidos em DB ou arquivos com `tenant_id` no caminho — não mais em
  `app/ai/knowledge/` compartilhado.
- Painel: **rota por slug** (`/t/{tenant_slug}/...`) no começo; subdomínio fica
  para depois.

---

## 2. Estado atual (o que é "Chokodelícia-specific" hoje)

### 2.1 Código hardcoded

| Lugar | O que assume Chokodelícia |
|---|---|
| `app/ai/knowledge/menus.md` | Catálogo, preços, regras de bolo/doces/presentes |
| `app/ai/knowledge/catalogo_produtos.json` | Produtos cafeteria + Páscoa + presentes |
| `app/ai/knowledge/catalogo_presentes_regulares.json` | Caixas de chocolate, flores |
| `app/ai/knowledge/operational_calendar.json` | Feriados, overrides |
| `app/ai/agents.py` | Agentes especializados (CakeOrder, SweetOrder, Gift, Cafeteria) refletem catálogo atual |
| `app/services/commercial_rules.py` | Taxa entrega R$10, cartão mín. R$100, PIX/Dinheiro/Cartão, parcelamento 2x |
| `app/services/store_schedule.py` | Domingo fechado, seg 12–18, ter-sáb 9–18 |
| `app/services/encomendas.py`, `precos.py` | Linhas B3/B4/B6/B7, adicionais (Morango, Ameixa, Nozes…) |
| `app/welcome_message.py` | Mensagem de boas-vindas da Chokodelícia |
| `app/settings.py` | `ADMIN_PHONES` (telefones dos donos), `ZAPI_*`, `EVOLUTION_INSTANCE=chokodelicia` |
| `frontend/` | Branding (nome, logo, paleta) |

### 2.2 Dados

- SQLite `dados/chokobot.db` — **sem coluna `tenant_id` em nenhuma tabela**.
- `clientes` (1.735), `encomendas` (162), `entregas`, `pedidos_cafeteria`,
  `encomenda_doces`, `customer_processes`, `atendimentos` (vazia).
- Estado de sessão em Redis — keys sem prefixo de tenant.

### 2.3 Infra

- 6 containers: `chokobot`, `chokobot_admin`, `chokobot_redis`,
  `evolution_api`, `evolution_postgres`, `evolution_redis`. Já temos
  Postgres rodando — vamos reutilizá-lo ou subir um `chokobot_postgres`
  separado (recomendação: **separado**, por ciclo de vida e backup).

---

## 3. Arquitetura alvo

```
                            ┌───────────────────────────────────────┐
                            │             chokobot (FastAPI)        │
                            │                                       │
  WhatsApp(tenant A)         │   ┌──────────────────────────┐       │
         │                   │   │ TenantResolverMiddleware │       │
         ↓                   │   │  (inbound webhook,       │       │
  evolution-api              │──→│   admin panel, API)      │       │
    instance=A  ──webhook──→ │   └──────────┬───────────────┘       │
  evolution-api              │              ↓                       │
    instance=B  ──webhook──→ │     request.state.tenant_id           │
         ↑                   │              ↓                       │
  WhatsApp(tenant B)         │   commands/use_cases/repos           │
                            │   todos recebem tenant_id             │
                            │              ↓                       │
                            │    chokobot-postgres (multi-tenant)   │
                            │    chokobot-redis (keys prefixadas)   │
                            └───────────────────────────────────────┘
```

### 3.1 Regras de ouro

1. **Tenant é resolvido no edge**, nunca no meio da stack. Middleware grava
   em `request.state.tenant_id`.
2. Todo repository, use case, gateway recebe `tenant_id` explicitamente.
   Nada de variável global ou context-var implícita além do middleware.
3. Todo SELECT/INSERT/UPDATE/DELETE em tabela multi-tenant **exige**
   `WHERE tenant_id = ?`. Enforcement via:
   - Repositórios abstratos que recebem `tenant_id` no construtor ou método.
   - Teste que varre SQLs gerados procurando falta de filtro (best-effort).
4. **Chave Redis tenanteada:** `tenant:{id}:session:{phone}`, `tenant:{id}:history:{phone}`.
5. **Event journal** recebe `tenant_id` em todos os eventos.

### 3.2 Resolução de tenant por superfície

| Superfície | Como resolve |
|---|---|
| Webhook Evolution | Payload tem `instance`. Lookup `tenants WHERE evolution_instance = ?` |
| Painel (Next.js) | URL `/t/{slug}/...`. Middleware Next.js extrai slug → cookie de sessão guarda `tenant_id` |
| API admin (`/api/*`) | Auth resolve `tenant_id` do usuário logado |
| Healthz/metrics | Global (sem tenant) |
| CLI/scripts | Exigem `--tenant` ou env `TENANT_SLUG` |

### 3.3 Admin global vs admin de tenant

Duas roles, mesma auth:
- `role=platform_admin`: vê todos tenants, cria tenants, troca status.
- `role=tenant_admin`: só seu tenant.

Implementação simples: tabela `users` com `tenant_id NULL` para platform admin.

---

## 4. Modelo de dados

### 4.1 Nova tabela `tenants`

```sql
CREATE TABLE tenants (
  id               BIGSERIAL PRIMARY KEY,
  slug             TEXT UNIQUE NOT NULL,
  display_name     TEXT NOT NULL,
  status           TEXT NOT NULL DEFAULT 'active',   -- active, suspended, trial
  evolution_instance TEXT UNIQUE NOT NULL,
  timezone         TEXT NOT NULL DEFAULT 'America/Sao_Paulo',
  admin_phones     TEXT[] NOT NULL DEFAULT '{}',
  webhook_secret   TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 4.2 Tabela `tenant_config` (regras comerciais por tenant)

Em vez de 20 colunas que vão mudar, JSONB validado por Pydantic.

```sql
CREATE TABLE tenant_config (
  tenant_id    BIGINT PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
  schedule     JSONB NOT NULL,     -- horários de funcionamento
  commercial   JSONB NOT NULL,     -- taxa entrega, formas pagamento, limites cartão
  branding     JSONB NOT NULL,     -- nome, cores, logo_url
  cutoffs      JSONB NOT NULL,     -- prazos (bolo no dia, entrega, croissant)
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 4.3 Tabela `tenant_knowledge`

```sql
CREATE TABLE tenant_knowledge (
  tenant_id       BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  slot            TEXT NOT NULL,    -- 'menus', 'catalogo_produtos', 'catalogo_presentes', 'operational_calendar'
  content_type    TEXT NOT NULL,    -- 'markdown' | 'json'
  content         TEXT NOT NULL,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (tenant_id, slot)
);
```

Carrega em startup num cache in-memory com TTL + invalidação por evento.

### 4.4 Tabelas de domínio existentes — adicionar `tenant_id`

Todas ganham coluna `tenant_id BIGINT NOT NULL REFERENCES tenants(id)` + índice:

- `clientes` → PK vira `(tenant_id, id)`; unique `telefone` vira `(tenant_id, telefone)`
- `encomendas`, `entregas`, `pedidos_cafeteria`, `encomenda_doces`,
  `customer_processes`, `atendimentos` → idem.
- Views `v_encomendas`, `v_entregas` → filtram por `tenant_id`.

### 4.5 `users` (painel)

```sql
CREATE TABLE users (
  id           BIGSERIAL PRIMARY KEY,
  email        TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  tenant_id    BIGINT REFERENCES tenants(id),  -- NULL = platform admin
  role         TEXT NOT NULL,                   -- platform_admin | tenant_admin | tenant_operator
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 5. Plano em fases

### Fase 0 — Postgres + schema multi-tenant (sem mudar UX)

1. Subir `chokobot_postgres` no compose (separado do Evolution).
2. Adotar Alembic de verdade — primeira migration cria todas as tabelas
   já com `tenant_id` + tabelas novas (`tenants`, `tenant_config`,
   `tenant_knowledge`, `users`).
3. Script `scripts/migrate_sqlite_to_postgres.py`:
   - Cria tenant seed `chokodelicia` com `evolution_instance=chokodelicia`
   - Copia todas as linhas do SQLite atribuindo esse `tenant_id`
   - Valida counts
4. Trocar `DB_PATH` por `DATABASE_URL` (Postgres) em todo lugar. SQLAlchemy
   já tá nas deps mas não usado como ORM — decidir: manter SQL raw via
   psycopg, ou migrar para SQLAlchemy Core. **Recomendação:** psycopg3
   async + SQL raw por enquanto (menos refactor).
5. Repositórios ganham `tenant_id` no construtor/método.
6. **Deploy:** janela curta de downtime (~10 min). Chokodelícia volta
   funcionando exatamente como antes.

**Bloqueio:** migration de dados é destrutiva (não dá pra voltar fácil).
Backup do SQLite antes + dry-run em ambiente staging.

### Fase 1 — Config e knowledge por tenant

1. `app/ai/knowledge/` vira fallback/default. Carregamento passa por
   `KnowledgeRepository(tenant_id)` que lê de `tenant_knowledge`.
2. `store_schedule.py`, `commercial_rules.py`, `precos.py` recebem
   `tenant_config` injetado (factory por request).
3. `welcome_message.py` usa `tenant.display_name` + `tenant_config.branding`.
4. Prompts dos agentes aceitam variáveis `{tenant_name}`, `{catalog}`,
   `{rules}` preenchidas no runtime.
5. Seed do segundo tenant (real, com dados reais): row em `tenants`,
   linhas em `tenant_config` + `tenant_knowledge`, criar instância Evolution
   pela API, webhook apontando pro mesmo `/webhook`.
6. **Validação:** segundo tenant conversa no WhatsApp dele, Chokodelícia
   não vê as mensagens, vice-versa. Testes unitários com 2 tenants paralelos.

### Fase 2 — Painel multi-tenant

1. Next.js middleware extrai slug de `/t/{slug}/...`.
2. Login unificado: email+senha → cookie com `tenant_id` + `role`.
3. Dashboard platform admin (`/admin`): lista tenants, cria, suspende.
4. Dashboard tenant admin (`/t/{slug}/dashboard`): igual ao atual, mas
   escopado ao seu tenant.
5. Onboarding concierge: platform admin cria tenant → gera link "conectar
   WhatsApp" → tenant abre, vê QR do Evolution, escaneia.
6. Billing/cobrança **fica para Fase 3**. Por ora, status manual.

### Fase 3 — Self-service (muito depois)

Pré-requisito: ≥10 tenants concierge já no ar, modelo de preço validado.

Signup público, QR pelo painel, Stripe/Asaas, legal (termos, LGPD),
suspensão automática por falta de pagamento.

---

## 6. Mudanças por módulo (Fase 0+1)

### `app/`

| Módulo | Mudança |
|---|---|
| `settings.py` | Sai `ZAPI_*` hardcoded-per-instance, entra `DATABASE_URL`, `DEFAULT_TENANT_SLUG` (fallback dev). Per-tenant vira DB lookup. |
| `api/routes/webhook.py` | Middleware ou dependency resolve `tenant` por `payload.instance`. `normalize_incoming` ganha `tenant_id`. |
| `api/routes/painel.py`, `clientes.py`, `encomendas.py` | Dependency `get_current_tenant` obrigatório. |
| `application/service_registry.py` | Gateways/repos viram factories: `get_messaging_gateway(tenant)`, `get_encomendas_repo(tenant)`. Cache por `tenant_id`. |
| `application/use_cases/*` | Assinatura ganha `tenant_id`. |
| `application/handlers/*` | Idem. |
| `domain/repositories/*.py` | Interface ganha `tenant_id`. |
| `infrastructure/repositories/*.py` | Implementações Postgres com WHERE tenant_id. |
| `infrastructure/state/` | Keys Redis com prefixo `tenant:{id}:`. |
| `infrastructure/gateways/evolution_messaging_gateway.py` | `__init__(tenant)` pega `evolution_instance` e `EVOLUTION_API_KEY` (global ou per-tenant) do tenant. |
| `ai/runner.py` | Carrega histórico por `tenant_id` + `phone`. Prompt composition por tenant. |
| `ai/agents.py` | Agentes recebem `tenant_config` e `tenant_knowledge` como contexto. |
| `services/commercial_rules.py`, `store_schedule.py`, `precos.py` | Funções viram métodos de classe que recebe `tenant_config`. |
| `observability.py` | Todo log/metric ganha label `tenant_id`. |
| `welcome_message.py` | Usa `tenant.display_name` + branding. |

### `scripts/`

- Novo: `scripts/migrate_sqlite_to_postgres.py` (one-shot).
- Novo: `scripts/create_tenant.py` (concierge onboarding).
- Existentes (`reprocess_outbox.py` já refatorado) ganham `--tenant` flag.

### `frontend/`

- Roteamento `/t/{slug}/...`.
- `/admin` para platform admin.
- Branding dinâmico do `tenant_config.branding`.

---

## 7. Redis — estratégia de chaves

Hoje: `history:{phone}`, `session:{phone}`.

Alvo: `tenant:{tenant_id}:history:{phone}`, `tenant:{tenant_id}:session:{phone}`.

Opção de isolamento: usar **DBs diferentes do Redis por tenant** (0..15) —
não escala além de 16 tenants, descartado. Prefixo resolve.

---

## 8. Evolution API — onboarding de tenant

Fluxo concierge (platform admin):

```
1. POST {evolution}/instance/create
   { instanceName: "tenant-slug", integration: "WHATSAPP-BAILEYS",
     webhook: { url: "https://chokobot/webhook", events: ["MESSAGES_UPSERT"] } }

2. INSERT INTO tenants (slug, evolution_instance, ...) VALUES (...)

3. GET {evolution}/instance/connect/{instanceName}
   → QR code → tenant escaneia pelo celular.

4. GET {evolution}/instance/connectionState/{instanceName}
   → "open" = pronto.
```

Tudo isso vira um comando `scripts/create_tenant.py --slug foo --display-name "Foo"`
ou um botão no painel platform admin.

---

## 9. Migração de dados SQLite → Postgres

Script `scripts/migrate_sqlite_to_postgres.py`:

1. Lê SQLite em read-only.
2. Cria tenant seed `chokodelicia`.
3. Itera tabelas na ordem de dependência (clientes → encomendas →
   entregas → etc), copia todas as linhas atribuindo `tenant_id=1`.
4. Valida row counts antes/depois.
5. Resequencia PKs se necessário.

**Pré-migração (obrigatório):**
- Backup `cp dados/chokobot.db dados/backups/chokobot_PRE_PG.db`
- Parar o Chokobot (downtime começa).
- `alembic upgrade head` no Postgres vazio.

**Pós-migração:**
- Rodar script.
- Validar no psql: `SELECT COUNT(*) FROM clientes; SELECT COUNT(*) FROM encomendas;`
- Subir Chokobot apontando para Postgres.
- Smoke test: mandar mensagem de teste pra Chokodelícia.

**Downtime estimado:** 10–15 minutos. Sugestão de janela: terça 09:00
(antes do pico de bolo do dia).

---

## 10. Riscos e mitigações

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Query sem `WHERE tenant_id` vaza dados entre tenants | **Alta** | **Crítico** | Repo pattern obrigatório + code review + testes com 2 tenants paralelos + (longo prazo) Row-Level Security no Postgres |
| Migration SQLite→PG corrompe dados | Média | Crítico | Backup, dry-run em staging, validation counts, rollback = restaurar SQLite + apontar app de volta |
| Redis key collision entre tenants | Média | Médio | Prefixo forçado em todas as chaves + audit script varrendo `KEYS *` |
| OpenAI cost explode quando N tenants crescem | Alta ao escalar | Alto | Telemetria por tenant desde Fase 0; throttle por tenant; cache de prompt |
| Evolution API cai e derruba todos os tenants | Média | Alto | Monitoria + plano de múltiplos servidores Evolution se passar de ~20 instâncias |
| QR de um tenant expira sem aviso | Alta ao longo do tempo | Médio | Webhook `CONNECTION_UPDATE` alerta platform admin |
| Breaking change no runtime quebra todos os tenants de uma vez | Média | Alto | Feature flag por tenant em mudanças de risco |

---

## 11. Envs propostas

```env
# Multi-tenant
DATABASE_URL=postgresql://chokobot:pass@chokobot-postgres:5432/chokobot
DEFAULT_TENANT_SLUG=chokodelicia   # usado em dev/tests

# OpenAI compartilhado (por enquanto)
OPENAI_API_KEY=...

# Evolution — global
EVOLUTION_SERVER_URL=http://evolution-api:8080
EVOLUTION_API_KEY=...

# Sai do .env: ZAPI_TOKEN, ZAPI_BASE, EVOLUTION_INSTANCE (vira per-tenant)
# ADMIN_PHONES (vira tenant.admin_phones)
# STORE_CLOSED, BOT_TIMEZONE (vira tenant_config)
```

---

## 12. O que NÃO está neste plano (e por quê)

- **Billing / cobrança** — Fase 3. Precisa modelo de preço primeiro.
- **Self-service signup** — Fase 3.
- **Subdomínios por tenant** (`{slug}.chokobot.com`) — Fase 2 tardia, primeiro `/t/{slug}`.
- **Marketplace de agentes** (tenant escolher quais agentes usa) — depois de validar.
- **Row-Level Security no Postgres** — primeiro repo-level enforcement, RLS como defesa em profundidade depois.
- **Deletar tabela `atendimentos`** — aproveitar migration pra Postgres pra não carregá-la. Confirmar antes.

---

## 13. Estimativa de esforço

| Fase | Esforço | Dependência externa |
|---|---|---|
| Fase 0 | 5–8 dias focados | Janela de downtime combinada |
| Fase 1 | 5–7 dias | Dados reais do segundo tenant (catálogo, horários) |
| Fase 2 | 7–10 dias | Design do painel para dois perfis de usuário |
| Fase 3 | 3+ semanas | Billing provider, legal (termos/LGPD) |

Fase 0+1 = **~2–3 semanas** de trabalho focado pra ter 2 tenants em produção.

---

## 14. Checklist de aprovação

Antes de começar Fase 0:

- [ ] **Confirmação:** Postgres separado (`chokobot_postgres`) ou reaproveitar o do Evolution? (recomendo separado)
- [ ] **Nome do segundo tenant** + contato de quem fornece dados (catálogo, horários, logo)
- [ ] **Janela de downtime** pra migração SQLite→PG (sugestão: terça 09:00)
- [ ] **Usar SQLAlchemy ORM** na Fase 0 ou manter SQL raw via psycopg? (recomendo psycopg raw)
- [ ] **`atendimentos` vazia:** dropar na migration ou manter por precaução?
- [ ] **Branding platform:** o produto tem nome? "Chokobot" vira o nome do produto ou só do primeiro tenant? (afeta painel admin global)

---

## 15. Próximos passos (se aprovado)

1. Merge deste plano (só doc).
2. PR Fase 0, parte 1: subir Postgres, schema Alembic, script de migration, sem tocar no runtime ainda.
3. PR Fase 0, parte 2: refactor de repos/use_cases/gateways pra receber `tenant_id`. Tudo default ao tenant seed.
4. Janela de cutover: rodar migration, flipar `DATABASE_URL`, smoke test.
5. PR Fase 1: knowledge/config per-tenant.
6. Onboardar segundo tenant via `scripts/create_tenant.py`.
7. PR Fase 2: painel.

Sugestão prática: fazemos Fase 0 completa e estabilizamos por 3–5 dias
antes de começar Fase 1, pra não empilhar risco.
