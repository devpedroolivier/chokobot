#!/usr/bin/env python3
"""Smoke test the Postgres cutover (Phase B.8b).

Run AFTER ``alembic upgrade head`` and
``scripts/migrate_sqlite_to_postgres.py --apply``, with the new
DATABASE_URL exported. Validates:

  1. Alembic is at 0003_tenant_id_on_domain.
  2. The Chokodelícia tenant seed (id=1) exists.
  3. Row counts in PG match the legacy SQLite (read read-only).
  4. A round-trip write/read/delete on ``clientes`` works under tenant 1.
  5. A synthetic domain event lands in the ``events`` table.

Prints a per-check status. Exits non-zero on any failure.

Usage::

    DATABASE_URL=postgresql+psycopg://trufinha:...@host:5433/trufinha \\
        python scripts/smoke_postgres_cutover.py \\
        --sqlite-backup dados/backups/chokobot_PRE_PG_20260427.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Match the table list of the migration script.
DOMAIN_TABLES = (
    "clientes", "encomendas", "entregas", "pedidos_cafeteria",
    "encomenda_doces", "atendimentos", "customer_processes",
)


def _green(msg: str) -> str:
    return f"\033[32m[ok]\033[0m {msg}"


def _red(msg: str) -> str:
    return f"\033[31m[fail]\033[0m {msg}"


def _yellow(msg: str) -> str:
    return f"\033[33m[warn]\033[0m {msg}"


def check_alembic(pg_conn) -> bool:
    with pg_conn.cursor() as cur:
        cur.execute("SELECT version_num FROM alembic_version")
        row = cur.fetchone()
    if row and row[0] == "0003_tenant_id_on_domain":
        print(_green(f"alembic_version = {row[0]}"))
        return True
    print(_red(f"alembic_version = {row[0] if row else None!r} (expected 0003_tenant_id_on_domain)"))
    return False


def check_tenant_seed(pg_conn) -> bool:
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, slug, display_name FROM tenants WHERE id = 1")
        row = cur.fetchone()
    if row and row[1] == "chokodelicia":
        print(_green(f"tenants[1] = {row[1]} ({row[2]})"))
        return True
    print(_red(f"tenants[1] = {row!r} (expected slug=chokodelicia)"))
    return False


def check_row_counts(pg_conn, sqlite_backup: Path | None) -> bool:
    if sqlite_backup is None:
        print(_yellow("--sqlite-backup not provided; skipping count parity check"))
        return True
    if not sqlite_backup.exists():
        print(_red(f"--sqlite-backup not found: {sqlite_backup}"))
        return False
    sqlite_conn = sqlite3.connect(f"file:{sqlite_backup}?mode=ro", uri=True)
    try:
        all_match = True
        for table in DOMAIN_TABLES:
            (sqlite_count,) = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            with pg_conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {table} WHERE tenant_id = 1")
                (pg_count,) = cur.fetchone()
            ok = sqlite_count == pg_count
            label = _green if ok else _red
            print(label(f"{table:<22} sqlite={sqlite_count:<6} pg={pg_count}"))
            if not ok:
                all_match = False
        return all_match
    finally:
        sqlite_conn.close()


def check_round_trip(pg_conn) -> bool:
    """Insert a sentinel row under tenant 1, read it back, delete it."""
    sentinel_phone = "55_smoke_99999"
    try:
        with pg_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO clientes (nome, telefone, criado_em, tenant_id) "
                "VALUES (%s, %s, NOW(), 1) RETURNING id",
                ("smoke", sentinel_phone),
            )
            (sentinel_id,) = cur.fetchone()

            cur.execute(
                "SELECT nome FROM clientes WHERE id = %s AND tenant_id = 1",
                (sentinel_id,),
            )
            row = cur.fetchone()
            if not row or row[0] != "smoke":
                print(_red(f"round-trip readback failed for id={sentinel_id}"))
                pg_conn.rollback()
                return False

            cur.execute(
                "DELETE FROM clientes WHERE id = %s AND tenant_id = 1",
                (sentinel_id,),
            )
        pg_conn.commit()
        print(_green(f"round-trip insert/select/delete on clientes (sentinel id={sentinel_id})"))
        return True
    except Exception as exc:
        pg_conn.rollback()
        print(_red(f"round-trip failed: {type(exc).__name__}: {exc}"))
        return False


def check_event_sink(pg_conn) -> bool:
    """Drop a synthetic event into the events table and read it back."""
    try:
        with pg_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO events (tenant_id, event_type, payload) "
                "VALUES (1, %s, %s::jsonb) RETURNING id",
                ("SmokeTestEvent", '{"smoke": true}'),
            )
            (event_id,) = cur.fetchone()

            cur.execute(
                "SELECT event_type, payload FROM events WHERE id = %s",
                (event_id,),
            )
            row = cur.fetchone()
            cur.execute("DELETE FROM events WHERE id = %s", (event_id,))
        pg_conn.commit()
        if row and row[0] == "SmokeTestEvent":
            print(_green(f"events sink round-trip (sentinel id={event_id})"))
            return True
        print(_red(f"events readback unexpected: {row!r}"))
        return False
    except Exception as exc:
        pg_conn.rollback()
        print(_red(f"events sink failed: {type(exc).__name__}: {exc}"))
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pg-url",
        default=None,
        help="Postgres URL. Defaults to settings.database_url.",
    )
    parser.add_argument(
        "--sqlite-backup",
        type=Path,
        default=None,
        help="Optional path to the pre-cutover SQLite backup, for parity check.",
    )
    args = parser.parse_args(argv)

    pg_url = args.pg_url
    if pg_url is None:
        from app.settings import get_settings
        pg_url = get_settings().database_url
    if not pg_url.startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
        raise SystemExit(f"--pg-url must be Postgres (got {pg_url!r})")

    raw_url = pg_url.replace("postgresql+psycopg://", "postgresql://", 1)

    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError:
        raise SystemExit("psycopg not installed. `pip install -r requirements.txt`.")

    print(f"--- Postgres cutover smoke ({raw_url.split('@')[-1]}) ---")

    failures = 0
    with psycopg.connect(raw_url, autocommit=False) as pg_conn:
        if not check_alembic(pg_conn):
            failures += 1
        if not check_tenant_seed(pg_conn):
            failures += 1
        if not check_row_counts(pg_conn, args.sqlite_backup):
            failures += 1
        if not check_round_trip(pg_conn):
            failures += 1
        if not check_event_sink(pg_conn):
            failures += 1

    print("---")
    if failures:
        print(_red(f"{failures} check(s) failed"))
        return 1
    print(_green("all checks passed"))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
