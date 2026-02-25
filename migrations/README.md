# Migrations

This project is prepared for Alembic-driven migrations.

Suggested bootstrap:
1. `alembic init migrations` (if you want full Alembic runtime files)
2. Configure `sqlalchemy.url` in `alembic.ini` from `DATABASE_URL`
3. Create baseline revision from current SQLite schema
4. Apply incremental revisions only (remove startup DDL over time)
