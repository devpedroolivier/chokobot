# Chokobot

Base FastAPI para operacao do Chokobot, com modo monolitico e modo `split` entre `edge` e `conversation`.

## Requisitos
- Python 3.11+
- Docker e Docker Compose opcionais para execucao em container

## Setup rapido
1. Crie o arquivo de ambiente:

```bash
cp .env.example .env
```

Para ligar o admin moderno em `Next.js`, crie tambem o ambiente do frontend:

```bash
cp frontend/.env.local.example frontend/.env.local
```

2. Instale as dependencias:

```bash
make install-dev
```

3. Rode a suite principal:

```bash
make test
```

4. Suba a aplicacao local:

```bash
make run
```

5. Se for usar o admin moderno, suba o frontend:

```bash
cd frontend && npm install && npm run dev
```

## Comandos principais
- `make install`: instala dependencias da aplicacao
- `make install-dev`: instala dependencias da aplicacao e de desenvolvimento
- `make lint`: roda validacao estatica com `ruff`
- `make test`: roda a suite principal reproduzivel
- `make check`: executa `lint` e `test`
- `make run`: sobe o app principal em `http://localhost:8000`
- `make run-edge`: sobe o `edge` em `http://localhost:8004`
- `make run-conversation`: sobe o `conversation` em `http://localhost:8005`
- `make docker-build`: gera a imagem Docker
- `make docker-up`: sobe o monolito via Compose
- `make docker-down`: derruba o monolito via Compose
- `make split-up`: sobe `edge`, `conversation` e `redis` via Compose
- `make split-down`: derruba o perfil `split`

## Suite de testes
O comando `make test` usa `scripts/run_tests.py`, que:
- injeta variaveis de ambiente seguras para o ambiente de teste
- redireciona artefatos temporarios para `/tmp/chokobot-tests`
- executa a suite principal baseada em `unittest`
- exclui cenarios exploratorios e scripts manuais que hoje vivem em `tests/`

Arquivos como `tests/test_ai_advanced.py`, `tests/test_ai_agent.py`, `tests/test_ai_all_flows.py`, `tests/test_ai_final_rules.py`, `tests/test_ai_nlp_dates.py` e `tests/test_e2e.py` continuam disponiveis como cenarios manuais, mas nao fazem parte da suite principal reproduzivel.

## Ambientes e portas
- Monolito via Docker Compose: `http://localhost:8003`
- Admin moderno `Next.js` local: `http://localhost:3000`
- `edge` no perfil `split`: `http://localhost:8004`
- `conversation` no perfil `split`: `http://localhost:8005`
- Redis no perfil `split`: `6379`

## Admin moderno
Variaveis minimas para o fluxo novo:

- FastAPI `.env`:
  - `PANEL_AUTH_ENABLED=1`
  - `PANEL_AUTH_USERNAME=...`
  - `PANEL_AUTH_PASSWORD=...`
  - `ADMIN_FRONTEND_URL=http://localhost:3000`
- Next.js `frontend/.env.local`:
  - `PANEL_BACKEND_URL=http://localhost:8000`
  - `ADMIN_SESSION_SECRET=...`

Fluxo esperado:
- o login acontece no Next em `/login`
- o Next valida as credenciais contra o painel FastAPI
- a sessao fica em cookie HTTP-only no frontend
- quando `ADMIN_FRONTEND_URL` estiver configurado, `/painel`, `/painel/clientes` e `/painel/encomendas` no FastAPI redirecionam para o admin moderno

## Estrutura
- `app/`: aplicacao FastAPI e modulos de dominio
- `tests/`: testes automatizados e alguns cenarios exploratorios legados
- `scripts/`: utilitarios de operacao e execucao
- `docs/`: arquitetura, roadmap e planos de execucao
- `docs/project-general-analysis.md`: analise consolidada do estado atual e prioridades de melhoria
- `docs/admin-modernization-rollout.md`: consolidado do rollout do admin moderno, validacoes e pendencias
- `dados/`: artefatos locais de runtime

## Observacoes
- O bootstrap atual ainda depende de variaveis como `ZAPI_TOKEN` e `ZAPI_BASE` em partes do runtime.
- A inicializacao lazy do cliente OpenAI e o desacoplamento maior do nucleo de IA seguem como trabalho da Sprint 3 do roadmap.
