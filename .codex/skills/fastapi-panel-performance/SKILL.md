---
name: fastapi-panel-performance
description: Use when improving performance of the Chokobot backend, especially FastAPI panel routes, snapshot endpoints, SQLite repositories, query patterns, payload shaping, and duplicated work between API/use case/frontend consumers.
---

# FastAPI Panel Performance

Use this skill for performance work in the Chokobot backend when the bottleneck is likely in panel reads, snapshot generation, SQLite access, or repeated transformations between repository, use case, and API layers.

## Focus Areas

- `app/api/routes/painel.py`
- `app/api/routes/pedidos.py`
- `app/api/routes/clientes.py`
- `app/application/use_cases/panel_dashboard.py`
- `app/infrastructure/repositories/sqlite_*.py`
- `app/db/`
- `tests/test_panel_*.py`
- `tests/test_frontend_snapshot_routes.py`

## Workflow

1. Map the hot path first.
   Usually this is one of:
   - `/painel/api/snapshot`
   - `/painel/api/encomendas`
   - `/painel/api/clientes`
   - data loading used by `frontend/src/lib/panel-api.ts`

2. Check for these issues before editing:
   - N+1 lookups by phone or id
   - repeated `list_*` calls on the same request path
   - duplicated sorting/normalization across repository and use case
   - fetching wide rows when only a few fields are needed
   - extra serialization work only to discard fields later
   - missing SQLite indexes for `WHERE`, `JOIN`, `ORDER BY`

3. Prefer the narrowest fix that changes the critical path:
   - preload in bulk instead of per-row lookups
   - reuse already-fetched status/data instead of re-querying
   - move shaping closer to the first trustworthy layer
   - keep response contracts stable unless the user asked for a contract change

4. Validate with focused tests first, then broader checks if the environment supports them.

## Project Rules

- Treat `dados/` as runtime artifacts; do not rewrite or clean them unless the user explicitly asks.
- Avoid introducing caches that can hide correctness issues in operational data.
- Prefer query reduction and payload reduction before adding memoization.
- Keep the current architecture direction:
  `api -> application -> domain -> infrastructure`

## Validation

Try the smallest relevant validation set first:

- `python3 -m unittest tests.test_panel_process_cards tests.test_frontend_snapshot_routes`
- `python3 -m unittest tests.test_panel_snapshot_payload tests.test_panel_sync_overview`
- `python3 -m compileall app tests`

If `pytest` exists, you may use it, but do not assume it is installed.

## Output Expectations

When using this skill, report:

- the hot path you optimized
- what repeated work was removed
- whether you changed query count, payload size, or transformation count
- what validation ran and what could not run
