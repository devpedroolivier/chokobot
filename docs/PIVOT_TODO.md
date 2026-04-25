# PIVOT TODO — Trufinha (ex-Chokobot) → Produto Multi-Tenant

**Data:** 2026-04-25
**Última atualização:** 2026-04-25 — adicionado rename Trufinha + 2º tenant.
**Objetivo:** Lista acionável e priorizada para evoluir o produto de
single-tenant (Chokodelícia) para um produto SaaS replicável, mantendo
a lógica de negócio existente. Complementa `docs/MULTI_TENANT.md`
(plano arquitetural) com qualidade + escalabilidade + execução.

---

## Identidade do produto: "Trufinha"

A partir de 2026-04-25, o produto é **Trufinha** (mesmo nome da personagem
da IA já presente nos prompts). "Chokobot" continua como nome técnico do
package Python e dos containers para reduzir blast radius — só vira
"trufinha" no cutover da Fase B.

| Camada | Estado |
|---|---|
| Marca exibida (templates, welcome, README, frontend, env exemplo) | **Trufinha** (Fase A em andamento) |
| Nome técnico do package `app/` + caminho `/root/projects/chokobot` | Continua como está até Fase B |
| Container names (`chokobot_container`, `chokobot-redis`, etc.) | Continuam até Fase B |
| Banco/Volumes (`chokobot.db`, volume `chokobot_redis_data`) | Continuam até Fase B |

---

## Resumo Executivo da Análise

### O que está bom (manter)
- Arquitetura **hexagonal** já estruturada (`domain/`, `application/`, `infrastructure/`, `services/`).
- **Ports & Adapters** definidos para messaging, catalog, order, delivery, conversation.
- **Command/Event bus** locais funcionais; eventos persistidos em JSONL.
- **Observabilidade** razoável: Prometheus `/metrics`, structured logs, healthz/readyz.
- **Webhook** com dedup por `message_id`, HMAC, replay protection, lock por phone.
- **Evolution gateway** já implementado (provider flag), pronto para multi-instância.
- **64 arquivos de teste** cobrindo agentes, prompts, repos, regras comerciais.

### Pontos críticos (bloqueiam escala)
| # | Problema | Impacto |
|---|---|---|
| C1 | SQLite single-tenant, **zero coluna `tenant_id`** em qualquer tabela | Não dá pra hospedar 2 clientes |
| C2 | **11 `@lru_cache`** em `service_registry.py` cacheando gateways/repos como singletons globais | Não há como ter gateway por tenant |
| C3 | Knowledge (`menus.md`, catálogos JSON) compartilhado em `app/ai/knowledge/` | Cada tenant precisaria de fork |
| C4 | **Prompts hardcoded com "Chokodelícia"** em `agents.py` (794 linhas, 2+ menções diretas) | LLM responde como Chokodelícia para qualquer tenant |
| C5 | **Templates HTML** com nome/branding fixo (10+ arquivos) | Painel "Chokodelícia" para todos |
| C6 | Settings monolítico mistura **infra + regras de negócio** (`PIX_KEY`, `ADMIN_PHONES`, `EVOLUTION_INSTANCE` no `AppSettings`) | Configs que deveriam ser per-tenant estão globais |
| C7 | Redis com prefixo global `chokobot:state:*` — sem `tenant_id` na chave | Vazamento entre tenants |
| C8 | `migrations/versions/` **vazio** — schema vive em `app/db/schema.sql` + `schema_guard.py` | Não há histórico nem rollback |
| C9 | `domain_events.jsonl` global, sem `tenant_id` | Inviável separar telemetria/auditoria por cliente |
| C10 | Painel: HTTP Basic com **um único usuário/senha** | Sem multi-user, sem roles |

### Pontos de qualidade (técnicos)
| # | Problema | Impacto |
|---|---|---|
| Q1 | Arquivos gigantes: `tools.py` (2322), `runner.py` (1336), `encomendas.py` (1307), `policies.py` (1086), `store_schedule.py` (801), `agents.py` (794) | Difícil de testar, alto risco de regressão |
| Q2 | `services/encomendas.py` mistura formatação de mensagem + persistência + regras de bolo | Acoplamento; não dá para reusar lógica |
| Q3 | `get_settings()` é chamado em **module load time** em `agents.py`, `tools.py` (`_PIX_KEY` resolvido na importação) | Quebra hot-reload de config; impede config por tenant |
| Q4 | Settings via `dataclass + os.getenv` (sem Pydantic) — sem validação, sem casting tipado | Erros de config descobertos em runtime |
| Q5 | 60 ocorrências de `@lru_cache`/`get_settings()`/singleton | Estado escondido em todo lugar |
| Q6 | Sem rate limit por phone/tenant; sem circuit-breaker no OpenAI/Evolution | Um tenant ruidoso afeta os outros |
| Q7 | Conexões SQLite abertas/fechadas por chamada (`get_connection()` cria nova conexão) | Não escala em concorrência; pool inexistente |
| Q8 | `responder_usuario` em `app/utils/mensagens.py` ainda mistura responsabilidades antigas | Caminho de saída de mensagem não é único |
| Q9 | Tests cobrem agente/prompt mas **nenhum teste com 2 tenants paralelos** | Regressão de isolamento passaria silenciosa |
| Q10 | `dados/` no host com SQLite + outbox + qr png + state_store.db — tudo no FS | Não funciona em deploy distribuído |

### O que NÃO precisa pivotar (ganho marginal)
- Sub-agentes especializados (`CakeOrderAgent` etc.): **mantém**, viram template de "perfil de negócio" parametrizável.
- Padrão de tools OpenAI: **mantém**, só passa `tenant_id` no contexto.
- Webhook lock por phone: **mantém**, só prefixa key com `tenant_id`.
- Frontend Next.js: **mantém**, troca para roteamento `/t/{slug}/*`.

---

## Ordem de execução sugerida

> **Princípio:** primeiro **estabilizar** (sem quebrar Chokodelícia), depois
> **tenantizar** (sem quebrar Chokodelícia), depois **abstrair** branding/UI,
> só então **onboardar** segundo tenant. Cada fase deixa o sistema funcional.

```
Fase A — Fundações (qualidade, sem mudança visível) ─────────► 1 sprint
Fase B — Postgres + tenant_id (cutover SQLite → PG)  ─────────► 1 sprint
Fase C — Config/knowledge per-tenant                  ─────────► 1 sprint
Fase D — Painel multi-tenant + onboarding concierge   ─────────► 1 sprint
Fase E — Hardening, observabilidade per-tenant, billing ──────► quando 2+ no ar
```

---

## FASE A — Fundações de qualidade (pré-requisito para multi-tenant)

Sem esses passos, qualquer refactor de tenanting fica pesado demais.

### A.0. Rename de marca para Trufinha (sem tocar package técnico)

- [x] `app/main.py` — title FastAPI vira "Trufinha"
- [x] Templates HTML em `app/templates/` — substituir "Chokodelícia" por nome dinâmico do tenant ou "Trufinha" como fallback de marca
- [x] `app/welcome_message.py` — manter "Trufinha" como persona (já é)
- [x] `frontend/src/` — page title, nav, login screen
- [x] `README.md`, `CLAUDE.md`
- [x] `.env.example` — comentários e branding
- [ ] Container/volume rename (`chokobot_container` → `trufinha_app`) — **adiado para Fase B** junto com cutover Postgres

**Critério:** `grep -i "chokobot" app/templates/ frontend/src/` só retorna refs técnicas (paths, nomes de container).

### A.1. Tipar settings com Pydantic v2
- [ ] Migrar `app/settings.py` de `dataclass + os.getenv` para `pydantic_settings.BaseSettings`.
- [ ] Validar tipos no boot, mensagens claras pra envs faltando.
- [ ] **NÃO** mudar nomes de envs ainda — só a estrutura interna.
- [ ] Critério: `python -c "from app.settings import get_settings; get_settings()"` valida tudo.

### A.2. Eliminar `get_settings()` em module load
- [ ] Procurar todas as ocorrências de `get_settings()` e `settings.X` chamadas no top-level de módulos (`agents.py`, `tools.py`).
- [ ] Substituir por leitura lazy dentro de funções.
- [ ] Justificativa: settings vai virar **per-request** (per-tenant) na Fase C.
- [ ] Critério: `grep -n "get_settings()" app/**/*.py | grep -v "def \|async def "` não retorna nada fora de funções.

### A.3. Quebrar arquivos gigantes em módulos coesos
> Não é refactor visual; é viabilizar tenanting sem mexer em arquivos de 2000 linhas.
- [ ] `app/ai/tools.py` (2322 linhas) → quebrar por agente:
  - `ai/tools/cake.py`, `ai/tools/sweet.py`, `ai/tools/gift.py`, `ai/tools/cafeteria.py`, `ai/tools/common.py`.
- [ ] `app/ai/runner.py` (1336) → extrair `runner/orchestration.py`, `runner/intent_handlers.py`, `runner/post_processing.py`.
- [ ] `app/ai/policies.py` (1086) → quebrar por área (intent detection, retry instructions, conflict detection).
- [ ] `app/services/encomendas.py` (1307) → separar `encomendas/persistence.py`, `encomendas/messaging.py`, `encomendas/validation.py`.
- [ ] `app/services/store_schedule.py` (801) → manter regras puras; mover formatação.
- [ ] Cada extração: roda suíte de testes antes/depois.

### A.4. Substituir `@lru_cache` por DI explícita
- [ ] Trocar `@lru_cache` em `service_registry.py` por classe `ServiceRegistry` instanciada uma vez no startup.
- [ ] Gateways/repos viram **factories** com cache interno chaveado por `tenant_id` (preparação Fase B).
- [ ] FastAPI: usar `Depends(get_registry)` nas rotas em vez de import direto.

### A.5. Pool de conexão e abstração de DB
- [ ] Trocar `sqlite3.connect()` por `aiosqlite` ou pool único reutilizado.
- [ ] Wrapper `Database.execute()` / `fetchone()` / `fetchall()` que aceita `tenant_id` e injeta `WHERE tenant_id = ?` opcional (preparação Fase B).
- [ ] Não muda comportamento ainda — só centraliza.

### A.6. Adotar Alembic de verdade
- [ ] Gerar `alembic.ini` apontando para `DATABASE_URL`.
- [ ] Migration inicial = snapshot do schema atual (`schema.sql`).
- [ ] Rodar `alembic upgrade head` no startup local + container.
- [ ] Critério: `alembic current` mostra revision; `migrations/versions/` deixa de estar vazio.

---

## FASE B — Postgres + tenant_id (cutover)

> Janela de downtime ~10–15 min. Reusa plano detalhado em `MULTI_TENANT.md` §4–§9.
> O foco aqui é o **checklist mínimo** acionável.

### B.1. Subir Postgres
- [ ] Adicionar serviço `chokobot-postgres` no `docker-compose.yml` (separado do `evolution-postgres`).
- [ ] Volume dedicado, healthcheck, env `CHOKOBOT_DB_PASS`.
- [ ] Driver: **psycopg3 async**. Adicionar a `requirements.txt`.

### B.2. Schema multi-tenant (Alembic migration #002)
- [ ] Tabela `tenants` (id, slug, display_name, status, evolution_instance, timezone, admin_phones, webhook_secret, branding).
- [ ] Tabela `tenant_config` (JSONB com schedule, commercial, cutoffs, branding).
- [ ] Tabela `tenant_knowledge` (slot, content_type, content).
- [ ] Tabela `users` (id, email, password_hash, tenant_id NULL=platform_admin, role).
- [ ] Adicionar `tenant_id BIGINT NOT NULL REFERENCES tenants(id)` em: `clientes`, `encomendas`, `entregas`, `pedidos_cafeteria`, `encomenda_doces`, `customer_processes`, `atendimentos`.
- [ ] Índices compostos `(tenant_id, telefone)`, `(tenant_id, criado_em)`, etc.
- [ ] Views `v_encomendas`, `v_entregas` filtram por `tenant_id`.

### B.3. Script de migração SQLite → Postgres
- [ ] `scripts/migrate_sqlite_to_postgres.py`:
  - Lê SQLite read-only.
  - Cria tenant seed `chokodelicia` (`evolution_instance=chokodelicia`).
  - Itera tabelas em ordem de FK, insere com `tenant_id=1`.
  - Valida row counts.
- [ ] Dry-run em staging com cópia do `chokobot.db` real.
- [ ] Backup: `cp dados/chokobot.db dados/backups/chokobot_PRE_PG_$(date +%Y%m%d).db`.

### B.4. Repositórios recebem `tenant_id`
- [ ] `CustomerRepository.get_by_phone(tenant_id, phone)` — assinatura mexe em todas as implementações.
- [ ] Idem para `OrderRepository`, `OrderWriteRepository`, `DeliveryWriteRepository`, `CustomerProcessRepository`.
- [ ] Implementações passam de `SQLite*` para `Postgres*`.
- [ ] Manter `SQLite*` como fallback dev opcional ou apagar (recomendo apagar para não dever).

### B.5. Use cases / handlers ganham `tenant_id`
- [ ] `process_inbound_message`, `generate_ai_reply`, `handle_inbound_message`, `persist_*` — assinatura ganha `tenant_id`.
- [ ] Webhook resolve tenant a partir de `payload.instance` (Evolution) ou `payload.token` (Z-API).
- [ ] Fallback: `DEFAULT_TENANT_SLUG=chokodelicia` em dev/test.

### B.6. Redis tenanteado
- [ ] `RedisStateStore._key()` muda de `chokobot:state:{ns}:{key}` para `chokobot:t:{tenant_id}:state:{ns}:{key}`.
- [ ] Migration de keys: script one-shot que copia keys antigas para o tenant seed.
- [ ] Adicionar teste: `keys()` de tenant A não vê chaves de tenant B.

### B.7. Eventos com tenant_id
- [ ] Todos `MessageReceivedEvent`, `AiReplyGeneratedEvent`, etc. ganham `tenant_id`.
- [ ] Persist em `dados/domain_events_{tenant_slug}.jsonl` ou tabela `events` com índice por `tenant_id`.
- [ ] Decidir: arquivo por tenant ou tabela única? **Recomendação:** tabela `events` em PG (já que PG entrou).

### B.8. Cutover
- [ ] Janela definida (sugestão: terça 09:00, antes do pico de bolo).
- [ ] Parar Chokobot.
- [ ] Backup SQLite.
- [ ] Rodar `alembic upgrade head` no PG.
- [ ] Rodar script de migração.
- [ ] Validar counts no `psql`.
- [ ] Subir Chokobot apontando para PG.
- [ ] Smoke test: enviar msg WhatsApp pra Chokodelícia, validar resposta + persistência.

---

## FASE C — Config e knowledge per-tenant

Lógica de negócio sai do código e vai para o banco.

### C.1. `tenant_config` carrega do PG
- [ ] `commercial_rules.py` vira classe `CommercialRules(config: dict)` instanciada por tenant.
- [ ] `store_schedule.py` idem (`StoreSchedule(config)`).
- [ ] `precos.py` idem.
- [ ] Cache in-memory por tenant (`dict[tenant_id, CommercialRules]`) com TTL 5 min e invalidação por evento de update.

### C.2. Knowledge per-tenant
- [ ] Repo `KnowledgeRepository.get(tenant_id, slot)` lê de `tenant_knowledge`.
- [ ] `app/ai/knowledge/` continua existindo como **default seed** copiado para Chokodelícia.
- [ ] `lookup_catalog_items`, `get_menu`, `get_cake_options` recebem `tenant_id`.
- [ ] Cache LRU com invalidação manual.

### C.3. Prompts dos agentes parametrizados
- [ ] `agents.py`: `TRIAGE_PROMPT`, `CAKE_ORDER_PROMPT` etc. viram **templates** com `{tenant_name}`, `{catalog_summary}`, `{rules_summary}`.
- [ ] Composição feita no runtime com dados do tenant.
- [ ] Substituir todas as 35+ referências hardcoded a "Chokodelícia" por `{tenant_name}`.
- [ ] Welcome message + handoff message + opt-out message: **template per-tenant** em `tenant_config.branding.messages`.

### C.4. PIX, taxa entrega, formas pagamento
- [ ] `PIX_KEY` sai do `.env` global, vira `tenant_config.commercial.pix_key`.
- [ ] Taxa entrega, limites cartão, parcelamento → `tenant_config.commercial`.
- [ ] `_PIX_INFO_LINE` resolvido em request-time, não em module load.

### C.5. Branding & assets
- [ ] `tenant_config.branding`: nome curto, nome longo, paleta hex, logo URL.
- [ ] Templates HTML do painel legado: trocar `Chokodelícia` literal por placeholder ou descontinuar (já redireciona p/ Next.js).
- [ ] Frontend Next.js: layout consome `/api/tenant/branding` e injeta CSS variables.

### C.6. Catálogo de produtos per-tenant
- [ ] `catalogo_produtos.json` vira linhas em `tenant_knowledge` slot=`catalogo_produtos` (ou tabela `tenant_products` se quiser estruturado).
- [ ] **Decisão técnica:** começar JSON em `tenant_knowledge` (mais flexível); só virar tabela quando 2+ tenants tiverem catálogo divergente o suficiente.

---

## FASE D — Painel multi-tenant + onboarding concierge

### D.1. Roteamento `/t/{slug}/*`
- [ ] Next.js middleware: extrai slug do path, valida contra cookie de sessão.
- [ ] Rotas existentes (`/dashboard`, `/customers`, `/orders`) viram `/t/{slug}/dashboard` etc.
- [ ] Backend `/api/*` resolve tenant pela sessão.

### D.2. Auth com roles
- [ ] Substituir HTTP Basic por sessão cookie + JWT.
- [ ] `users` table: `platform_admin` | `tenant_admin` | `tenant_operator`.
- [ ] Login único; redireciona para tenant correto após auth.
- [ ] Logout, password reset.

### D.3. Painel platform admin (`/admin`)
- [ ] Lista tenants, cria, suspende, vê métricas agregadas.
- [ ] Botão "criar tenant" → modal com slug, nome, contato.

### D.4. Onboarding concierge (`scripts/create_tenant.py`)
- [ ] Args: `--slug`, `--display-name`, `--admin-phone`.
- [ ] Steps: cria row em `tenants`, seed `tenant_config` default, cria instância Evolution via API, gera QR, persiste webhook secret.
- [ ] Output: link/QR para o cliente conectar WhatsApp.
- [ ] Idempotente: re-rodar com mesmo slug = no-op + mostra status.

### D.5. Sync de instância Evolution
- [ ] Worker (ou hook em request) escuta `CONNECTION_UPDATE` da Evolution.
- [ ] Atualiza `tenants.status` (active/disconnected) automaticamente.
- [ ] Notifica platform admin se conexão cair.

---

## FASE E — Hardening, observabilidade, billing

### E.1. Observabilidade per-tenant
- [ ] Todo `log_event(...)` ganha label `tenant_id`.
- [ ] Métricas Prometheus com label `tenant_id`.
- [ ] Dashboard Grafana ou similar com breakdown por tenant.

### E.2. Limites e isolamento
- [ ] Rate limit por tenant (msgs/min) — protege OpenAI/Evolution.
- [ ] Circuit breaker no OpenAI: tenant ruidoso não derruba os outros.
- [ ] Quota de mensagens/mês por tenant (telemetria).

### E.3. Custos OpenAI por tenant
- [ ] Logar `prompt_tokens` + `completion_tokens` em cada chamada com `tenant_id`.
- [ ] Tabela `ai_usage` ou métrica para reconciliação mensal.
- [ ] Cache de prompt (Anthropic ou via prefix hashing) para reduzir custo.

### E.4. Defesa em profundidade — Row Level Security
- [ ] Postgres RLS: policy `tenant_id = current_setting('app.tenant_id')::bigint`.
- [ ] Conexão seta `SET app.tenant_id = ?` por request.
- [ ] Mesmo se um repo esquecer o WHERE, o PG bloqueia.

### E.5. Backup e disaster recovery
- [ ] `pg_dump` agendado por tenant (sql ou tabela snapshot).
- [ ] Restore testado: derrubar dev, restaurar do backup, validar.
- [ ] Plano: o que acontece se Evolution derruba? Se PG cair?

### E.6. Billing (Fase 3 do MULTI_TENANT.md)
- [ ] Modelo de preço definido (por mensagem? por tenant ativo? híbrido?).
- [ ] Integração Stripe / Asaas.
- [ ] Suspensão automática por inadimplência (`tenants.status='suspended'`).
- [ ] Página de billing no painel tenant_admin.

---

## Onboarding de 2º tenant (confeitaria piloto)

**Status:** **bloqueado por Fase B.**

Solicitado em 2026-04-25: adicionar um segundo número de WhatsApp para
confeitarias testarem o produto. Hoje é **inseguro** porque o sistema
não tem `tenant_id` em nenhum lugar — mensagens, pedidos e clientes do
tenant 2 vazariam para a Chokodelícia (e vice-versa).

**Pré-requisitos antes de plugar o segundo número:**
- [ ] Fase B.1 (Postgres) e B.2 (schema multi-tenant) concluídas
- [ ] Fase B.4 (repositórios com tenant_id)
- [ ] Fase B.6 (Redis tenanteado)
- [ ] Migração SQLite → PG executada (B.8)
- [ ] Smoke test com 2 tenants paralelos passando

**Quando estiver pronto (parte da Fase B/D):**
- [ ] Criar instância Evolution para o tenant piloto via `/instance/create`
- [ ] Inserir row em `tenants` com slug + `evolution_instance` + `admin_phones`
- [ ] Seed de `tenant_config` (horários, PIX, taxa entrega, branding mínimo)
- [ ] Seed de `tenant_knowledge` (catálogo do tenant piloto)
- [ ] Conectar QR code com a confeitaria
- [ ] Validar que tenant piloto vê só seus dados no painel

Sugestão: ao terminar a Fase B mínima, fazer o onboarding pelo script
`scripts/create_tenant.py` (D.4). Não improvisar antes.

---

## Decisões a tomar (bloqueiam Fase B)

Tirado do checklist de aprovação do `MULTI_TENANT.md` §14 + adicionais:

- [ ] **Postgres separado** (`chokobot-postgres`) ou reaproveitar `evolution-postgres`? — **Recomendo separado** (ciclo de vida, backup, segurança).
- [ ] **Driver:** psycopg3 async com SQL raw, ou SQLAlchemy Core/ORM? — **Recomendo psycopg3 + SQL raw** na primeira iteração (menor refactor); SQLAlchemy entra na Fase E se valer.
- [ ] **Segundo tenant:** quem é? Quando começa? Quem fornece dados (catálogo, horários, branding)?
- [ ] **Janela de downtime** para cutover SQLite→PG (sugestão: terça 09:00).
- [ ] **Nome do produto** vs nome do tenant. "Chokobot" continua nome técnico ou vira marca? Afeta painel platform admin.
- [ ] **Atendimentos vazia (`atendimentos` table):** dropar na migration ou manter?
- [ ] **Outbox JSONL** (`dados/outbox.jsonl`): migrar pra tabela PG ou manter por tenant?
- [ ] **Branding:** quem desenha o sistema de design tokenizável? (cores, logo, nome no painel)

---

## Critérios de "produto pronto para 2 tenants"

Saída da Fase D. Tudo abaixo precisa ser verdade simultaneamente:

- [ ] Chokodelícia + segundo tenant rodam no mesmo processo, mesmo Postgres.
- [ ] Mensagem do tenant A jamais aparece em consulta/painel do tenant B.
- [ ] Cada tenant tem seu próprio catálogo, horário, PIX, branding.
- [ ] Painel `/t/chokodelicia/*` e `/t/segundo/*` funcionam isolados.
- [ ] Platform admin (`/admin`) lista os 2 e cria um terceiro via UI/script.
- [ ] Suíte de testes inclui ≥3 cenários com 2 tenants paralelos (isolamento de DB, isolamento de Redis, isolamento de prompt).
- [ ] Deploy reversível: se algo der errado, restaurar SQLite + apontar app de volta funciona em <30 min.
- [ ] Nenhuma string "Chokodelícia" hardcoded em código Python (só em dados do tenant seed).

---

## Riscos principais e mitigação rápida

| Risco | Mitigação |
|---|---|
| Query sem `WHERE tenant_id` vaza dados | Repo recebe `tenant_id` no construtor + RLS no PG (Fase E) |
| Migration corrompe Chokodelícia | Backup + dry-run staging + counts validation + plano de rollback documentado |
| Refactor quebra suíte de testes | Cada PR de Fase A/B passa CI verde antes do merge; sem batch grande |
| Custo OpenAI explode com 2+ tenants | Telemetria desde Fase B; throttle por tenant na Fase E |
| QR Evolution expira | Webhook `CONNECTION_UPDATE` alerta admin (Fase D.5) |
| Equipe perde contexto entre fases | Toda Fase fecha com README curto do que mudou + smoke test passo-a-passo |

---

## Próxima ação concreta

1. **Aprovar este TODO** + responder as decisões pendentes acima.
2. Abrir PR da **Fase A.1 + A.2** (Pydantic settings + remover module-load `get_settings()`). Pequeno, sem risco. Valida o pipeline.
3. Em paralelo: **definir o segundo tenant real** (sem ele, Fase D não tem sentido).
4. Fase A.3–A.6 sequencial; cada subitem = 1 PR pequeno.
5. Fase B em uma janela de downtime combinada.

---

## Referências cruzadas

- `docs/MULTI_TENANT.md` — plano arquitetural detalhado (mantém como verdade arquitetural).
- `PLANO_ACAO_AUDITORIA.md` — backlog de qualidade de produto (PIX, escalações, prompts). **Independente** desta pivotagem mas itens 1.1–1.3 e 5.1 devem ser feitos antes ou em paralelo à Fase A para não amplificar bugs no pivot.
- `CLAUDE.md` — visão geral do projeto.
- `DOCUMENTACAO_ALTERACOES_AUDITORIA.md` — histórico de mudanças.
