# CLAUDE.md — Chokobot

## Visão Geral

**Chokobot** é um bot de WhatsApp para a **Chokodelícia**, uma confeitaria artesanal. O sistema automatiza o atendimento via WhatsApp usando um agente de IA com múltiplos sub-agentes especializados por tipo de pedido.

---

## Stack Tecnológica

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.11+, FastAPI (async), Uvicorn |
| LLM | OpenAI API (GPT-4 ou compatível) via tool-calling |
| Banco de Dados | SQLite 3 (`dados/chokobot.db`) |
| Estado de Sessão | Redis (fallback: in-memory dict) |
| Migrações | Alembic 1.13+ |
| Validação | Pydantic 2.0+ |
| HTTP Client | HTTPX (async) |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Messaging | Z-API (gateway WhatsApp) |
| Linter | Ruff (strict, linha máx 100 chars) |
| Infra | Docker Compose (monolítico ou split) |
| CI/CD | GitHub Actions |

---

## Arquitetura

### Padrão Geral: Hexagonal (Ports & Adapters)

```
app/
├── ai/              # Agentes, runner OpenAI, tools, registry, policies
├── api/             # Rotas FastAPI (webhook, clientes, pedidos, painel)
├── application/     # Commands, Events, CommandBus, EventBus, ServiceRegistry, UseCases
├── domain/          # Modelos de domínio e interfaces de repositório
├── infrastructure/  # Gateways concretos (Z-API, SQLite), repositórios, state
├── services/        # Lógica de negócio (encomendas, preços, agenda, regras comerciais)
├── models/          # Modelos Pydantic e ORM
├── utils/           # Utilidades (datetime, mensagens, payload)
└── db/              # Setup SQLite e schema
```

### Modos de Deploy

- **Monolítico:** processo único na porta 8000
- **Split:** `edge_main.py` (8004) + `conversation_main.py` (8005) + Redis

### Fluxo de Mensagem

1. WhatsApp → Z-API → `POST /api/webhook`
2. `HandleInboundMessageCommand` → Handler → `GenerateAiReplyCommand`
3. Runner OpenAI: carrega histórico (Redis) → chama LLM → processa tool calls
4. Resposta enviada via Z-API
5. Eventos emitidos em `dados/domain_events.jsonl`

---

## Agentes de IA

Definidos em `app/ai/agents.py`. Sistema multi-agente com roteamento:

| Agente | Responsabilidade |
|--------|-----------------|
| `TriageAgent` | Analisa intent e roteia para o agente correto |
| `CakeOrderAgent` | Bolos sob encomenda (linhas Traditional, Gourmet, Aniversário, Simples) |
| `CafeteriaAgent` | Pronta entrega, croissants, cafeteria, Kit Festou |
| `SweetOrderAgent` | Doces avulsos (brigadeiros, bombons) em quantidade |
| `GiftOrderAgent` | Presentes (caixas de chocolate, cestas, flores) |
| `KnowledgeAgent` | FAQ: preços, horários, políticas |

Ferramenta `transfer_to_agent` realiza o roteamento interno.

---

## Regras de Negócio

### Horários de Funcionamento

- Domingo: **fechado**
- Segunda: 12:00–18:00
- Terça a Sábado: 09:00–18:00

### Cutoffs (prazos)

- Pedido de bolo no dia: até **11:00**
- Pedido de entrega: até **17:30**
- Croissant: preparo em **20 minutos**

### Pagamento

- PIX, Dinheiro, Cartão
- Parcelamento em cartão: mínimo **R$100,00**, máximo **2x**
- Troco disponível apenas para pagamento em dinheiro

### Entrega

- Taxa de entrega: **R$10,00**
- Modalidades: retirada (`retirada`) ou entrega (`entrega`)

### Pedidos especiais

- Ovos de Páscoa prontos para retirada → escalar para humano
- Pedidos fora do escopo → escalar para humano
- Palavra-chave "falar com humano" → escalada imediata

---

## Catálogo de Produtos

Estruturado em `app/ai/knowledge/`:

- `menus.md` — categorias, preços e regras de pedido (fonte principal do LLM)
- `catalogo_produtos.json` — produtos da cafeteria, Páscoa, presentes (26 KB)
- `catalogo_presentes_regulares.json` — caixas de chocolate, flores
- `operational_calendar.json` — feriados e overrides de capacidade

### Linhas de Bolo

- **Traditional:** B3, B4, B6, B7 (recheio + mousse + adicionais)
- **Gourmet:** Langue de Chat, Floresta Negra, etc.
- **Aniversário:** P4, P6
- **Simples:** base chocolate ou cenoura
- **Tortas:** linha própria

### Adicionais disponíveis

Morango, Ameixa, Nozes, Cereja, Abacaxi — preço por adicional.

---

## Base de Dados

**SQLite** em `dados/chokobot.db`. Tabelas principais:

| Tabela | Descrição |
|--------|-----------|
| `clientes` | Clientes por telefone |
| `encomendas` | Pedidos de bolo/doces/presentes |
| `entregas` | Registros de entrega/retirada |
| `atendimentos` | Histórico de conversas |
| `pedidos_cafeteria` | Pedidos de pronta entrega |
| `encomenda_doces` | Pedidos de doces avulsos |
| `customer_processes` | Estado de processos longos por cliente |

Views: `v_encomendas`, `v_entregas`.

Migrações via Alembic. Schema validado no startup (`schema_guard.py`).

---

## Variáveis de Ambiente

Arquivo `.env` baseado em `.env.example`. Principais:

```env
ZAPI_TOKEN=          # Token Z-API WhatsApp
ZAPI_BASE=           # URL base Z-API
OPENAI_API_KEY=      # Chave OpenAI
DB_PATH=dados/chokobot.db
REDIS_URL=           # Redis (opcional)
BOT_TIMEZONE=America/Sao_Paulo
STORE_CLOSED=0       # 1 para fechar manualmente
WEBHOOK_SECRET=      # HMAC verification
ADMIN_PHONES=        # Números admin separados por vírgula
PANEL_AUTH_ENABLED=1
PANEL_AUTH_USERNAME=
PANEL_AUTH_PASSWORD=
AI_SAVE_LEARNING_ENABLED=0
```

---

## API Endpoints

| Método | Rota | Função |
|--------|------|--------|
| POST | `/api/webhook` | Inbound WhatsApp (Z-API) |
| GET/POST | `/api/clientes` | Gestão de clientes |
| GET/POST | `/api/encomendas` | Gestão de pedidos |
| GET/POST | `/painel/*` | Painel admin (redireciona ao Next.js) |
| GET | `/healthz` | Liveness probe |
| GET | `/readyz` | Readiness probe |
| GET | `/metrics` | Métricas Prometheus |

---

## Segurança

- Verificação de assinatura HMAC-SHA256 nos webhooks
- Proteção contra replay attacks (cache com expiração)
- Autenticação HTTP Basic no painel
- Redação de dados sensíveis nos logs (hash de telefone, preview de mensagem)
- Phones admin para comandos especiais

---

## Observabilidade

- Logs estruturados JSON para stdout
- Endpoint `/metrics` compatível com Prometheus
- X-Request-ID propagado entre serviços
- Event sourcing em `dados/domain_events.jsonl`

---

## Testes

```bash
python scripts/run_tests.py    # Roda a suíte completa (74+ testes)
```

Testes em `tests/`. CI via GitHub Actions.

---

## Comandos Úteis

```bash
# Desenvolvimento local
uvicorn app.main:app --reload --port 8000

# Docker monolítico
docker compose up chokobot

# Docker split (com Redis)
docker compose --profile split up

# Migrations
alembic upgrade head

# Lint
ruff check app/

# Backup do banco
cp dados/chokobot.db dados/backups/chokobot_$(date +%Y%m%d).db
```

---

## Convenções de Código

- **Python:** async-first, Pydantic para validação, repositórios abstratos em `domain/`
- **Imports:** absolutos a partir de `app.`
- **Configuração:** sempre via `app.config` ou `app.settings.AppSettings`
- **Logs:** `logging.getLogger(__name__)`, nunca `print()`
- **Banco:** preferir repositórios em `infrastructure/repositories/`, evitar SQL raw fora de `db/`
- **Novos agentes:** adicionar em `app/ai/agents.py` + registrar tools em `tool_registry.py`
- **Regras de negócio:** centralizar em `app/services/commercial_rules.py` ou `store_schedule.py`
- Linha máxima: **100 caracteres**
- Evitar lógica de negócio nas rotas FastAPI — usar UseCases/Handlers

---

## Estrutura de Eventos de Domínio

Eventos emitidos em `dados/domain_events.jsonl` (JSONL, um evento por linha):

- `MessageReceivedEvent`
- `AiReplyGeneratedEvent`
- `OrderCreatedEvent`

---

## Frontend Admin

Next.js em `frontend/`. Rotas:

- `/login` — autenticação
- `/dashboard` — visão geral
- `/customers` — clientes
- `/orders` — pedidos

Configura-se via `ADMIN_FRONTEND_URL` para redirect automático do painel legado.
