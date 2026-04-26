# Migrations

Alembic-driven database migrations for Trufinha.

## Status

* `0001_baseline_schema` — idempotent snapshot of the Chokodelícia
  schema (clientes, encomendas, entregas, pedidos_cafeteria,
  encomenda_doces, atendimentos, customer_processes + the v_encomendas /
  v_entregas views).

The legacy startup helpers (`app/db/init_db.py:ensure_views()` and
`app.models.criar_tabelas()`) still create the schema so production
keeps working unchanged. The Phase B cutover replaces those helpers
with `alembic upgrade head` after the schema is migrated to Postgres.

## Common commands

```bash
# Show current revision applied to the configured database
.venv/bin/alembic current

# Mark an existing database as already at the baseline (production
# Chokodelícia: run once after first deploy with this code).
.venv/bin/alembic stamp head

# Apply pending migrations
.venv/bin/alembic upgrade head

# Generate a new revision from a message
.venv/bin/alembic revision -m "describe the change"
```

## Configuration

`alembic.ini` is committed at the project root. The actual database URL
is resolved at runtime by `migrations/env.py` from
`app.settings.get_settings().database_url`, so the same migrations work
across SQLite (today) and Postgres (Phase B).

## Phase B follow-up

The next migration adds:
- `tenants`, `tenant_config`, `tenant_knowledge`, `users` tables
- `tenant_id` column (NOT NULL, FK) on every domain table
- Compound indexes on `(tenant_id, …)`
- View rewrites that filter by `tenant_id`
- (Optional) Postgres Row-Level Security policies

That migration is intentionally not yet checked in — it lands together
with the Postgres cutover described in `docs/MULTI_TENANT.md` §4.
