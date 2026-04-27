#!/usr/bin/env python3
"""Migrate the legacy Chokodelícia SQLite database into Postgres (Phase B.3).

Reads ``dados/chokobot.db`` read-only and copies every domain row into a
freshly migrated Postgres database under ``tenant_id=1`` (Chokodelícia,
seeded by Alembic migration 0002). Tables are processed in foreign-key
order; sequences are resynced after each table; row counts are
validated at the end.

Default mode is **dry-run** — no writes, but the script still connects
to Postgres to verify schema/seed/empty target. Pass ``--apply`` to
commit. The dry-run rolls back at the end.

Run from the project root:

    # 1. backup the SQLite first
    cp dados/chokobot.db "dados/backups/chokobot_PRE_PG_$(date +%Y%m%d).db"

    # 2. ensure psycopg is installed (uncomment in requirements.txt)
    pip install 'psycopg[binary]>=3.2'

    # 3. ensure Postgres is up and at HEAD
    docker compose --profile postgres up -d chokobot-postgres
    DATABASE_URL=postgresql+psycopg://trufinha:...@localhost:5433/trufinha \
        alembic upgrade head

    # 4. dry-run first
    DATABASE_URL=postgresql+psycopg://trufinha:...@localhost:5433/trufinha \
        python scripts/migrate_sqlite_to_postgres.py

    # 5. apply
    DATABASE_URL=postgresql+psycopg://trufinha:...@localhost:5433/trufinha \
        python scripts/migrate_sqlite_to_postgres.py --apply
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("migrate_sqlite_to_postgres")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


EXPECTED_REVISION = "0003_tenant_id_on_domain"


@dataclass(frozen=True)
class TableSpec:
    """One legacy SQLite table to copy into Postgres."""

    name: str
    columns: tuple[str, ...]
    # Optional FK constraints to validate against the SQLite source before
    # we attempt to insert into PG (catches dangling references early).
    fk_validate: tuple[tuple[str, str], ...] = field(default_factory=tuple)


# Insertion order respects FKs: parents before children.
TABLES: tuple[TableSpec, ...] = (
    TableSpec(
        name="clientes",
        columns=("id", "nome", "telefone", "criado_em"),
    ),
    TableSpec(
        name="encomendas",
        columns=(
            "id", "cliente_id", "categoria", "produto", "tamanho",
            "massa", "recheio", "mousse", "adicional", "kit_festou",
            "quantidade", "data_entrega", "horario", "valor_total",
            "serve_pessoas", "criado_em",
        ),
        fk_validate=(("cliente_id", "clientes"),),
    ),
    TableSpec(
        name="entregas",
        columns=(
            "id", "encomenda_id", "tipo", "endereco",
            "data_agendada", "status",
        ),
        fk_validate=(("encomenda_id", "encomendas"),),
    ),
    TableSpec(
        name="pedidos_cafeteria",
        columns=("id", "cliente_id", "pedido", "criado_em"),
        fk_validate=(("cliente_id", "clientes"),),
    ),
    TableSpec(
        name="encomenda_doces",
        columns=("id", "encomenda_id", "nome", "qtd", "preco", "unit"),
        fk_validate=(("encomenda_id", "encomendas"),),
    ),
    TableSpec(
        name="atendimentos",
        columns=("id", "cliente_id", "mensagem", "criado_em"),
        fk_validate=(("cliente_id", "clientes"),),
    ),
    TableSpec(
        name="customer_processes",
        columns=(
            "id", "phone", "customer_id", "process_type", "stage",
            "status", "source", "draft_payload", "order_id",
            "created_at", "updated_at",
        ),
        # customer_id and order_id may legitimately be NULL.
        fk_validate=(),
    ),
)


def open_sqlite_readonly(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"SQLite file not found: {path}")
    uri = f"file:{path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_rows(conn: sqlite3.Connection, table: TableSpec) -> list[dict[str, Any]]:
    cols = ", ".join(table.columns)
    cur = conn.execute(f"SELECT {cols} FROM {table.name} ORDER BY id")
    return [dict(row) for row in cur.fetchall()]


def project_row(
    row: dict[str, Any],
    tenant_id: int,
    columns: tuple[str, ...],
) -> tuple[Any, ...]:
    """Pure helper: turn a SQLite row dict into the tuple PG insert expects.

    Order matches ``build_insert_sql``: declared columns first, ``tenant_id`` last.
    """
    return tuple(row[col] for col in columns) + (tenant_id,)


def build_insert_sql(table: str, columns: tuple[str, ...]) -> str:
    cols = list(columns) + ["tenant_id"]
    placeholders = ", ".join(["%s"] * len(cols))
    return f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"


def resync_sequence_sql(table: str) -> str:
    """SQL that bumps the BIGSERIAL sequence past the highest copied id.

    ``setval(seq, MAX(id), is_called=true)`` if the table has rows, else a
    no-op (we leave the sequence at its initial value).
    """
    return (
        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'),"
        f" GREATEST(COALESCE((SELECT MAX(id) FROM {table}), 1), 1),"
        f" (SELECT MAX(id) IS NOT NULL FROM {table}))"
    )


def validate_sqlite_fks(
    sqlite_conn: sqlite3.Connection,
) -> list[str]:
    """Return human-readable warnings for dangling FKs in the source DB."""
    warnings: list[str] = []
    for table in TABLES:
        for child_col, parent_table in table.fk_validate:
            cur = sqlite_conn.execute(
                f"SELECT COUNT(*) FROM {table.name} t "
                f"WHERE t.{child_col} IS NOT NULL AND NOT EXISTS ("
                f"SELECT 1 FROM {parent_table} p WHERE p.id = t.{child_col})"
            )
            (orphans,) = cur.fetchone()
            if orphans:
                warnings.append(
                    f"{table.name}.{child_col}: {orphans} rows reference a "
                    f"missing {parent_table}.id"
                )
    return warnings


def assert_postgres_ready(pg_conn: Any, tenant_id: int) -> None:
    """Refuse to migrate if PG isn't on the right Alembic revision, the tenant
    seed is missing, or any target table already has rows."""
    with pg_conn.cursor() as cur:
        cur.execute("SELECT version_num FROM alembic_version")
        row = cur.fetchone()
        if not row:
            raise RuntimeError(
                "alembic_version is empty — run `alembic upgrade head` "
                "against Postgres before migrating data."
            )
        revision = row[0]
        if revision != EXPECTED_REVISION:
            raise RuntimeError(
                f"Postgres is at Alembic revision {revision!r}; expected "
                f"{EXPECTED_REVISION!r}. Run `alembic upgrade head` first."
            )

        cur.execute("SELECT slug FROM tenants WHERE id = %s", (tenant_id,))
        seed = cur.fetchone()
        if not seed:
            raise RuntimeError(
                f"tenants table has no row with id={tenant_id}. "
                "The 0002 migration's seed didn't run."
            )
        LOGGER.info("Postgres at %s; tenant %d (%s) ready.", revision, tenant_id, seed[0])

        for table in TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {table.name}")
            (existing,) = cur.fetchone()
            if existing:
                raise RuntimeError(
                    f"{table.name} already has {existing} row(s) in Postgres; "
                    "refusing to migrate on top of existing data. "
                    "Truncate first if this is a re-run."
                )


def migrate(
    sqlite_conn: sqlite3.Connection,
    pg_conn: Any,
    tenant_id: int,
    apply: bool,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLES:
        rows = fetch_rows(sqlite_conn, table)
        counts[table.name] = len(rows)
        if not rows:
            LOGGER.info("%-22s 0 rows (skipped)", table.name)
            continue

        sql = build_insert_sql(table.name, table.columns)
        params = [project_row(r, tenant_id, table.columns) for r in rows]

        if apply:
            with pg_conn.cursor() as cur:
                cur.executemany(sql, params)
                cur.execute(resync_sequence_sql(table.name))
            LOGGER.info("%-22s %d rows inserted", table.name, len(rows))
        else:
            preview = params[0]
            LOGGER.info(
                "%-22s %d rows (dry-run; first row preview: %s)",
                table.name, len(rows), preview,
            )
    return counts


def validate_counts(
    pg_conn: Any,
    expected: dict[str, int],
    tenant_id: int,
) -> None:
    with pg_conn.cursor() as cur:
        for table in TABLES:
            cur.execute(
                f"SELECT COUNT(*) FROM {table.name} WHERE tenant_id = %s",
                (tenant_id,),
            )
            (got,) = cur.fetchone()
            if got != expected[table.name]:
                raise RuntimeError(
                    f"Row count mismatch for {table.name}: SQLite had "
                    f"{expected[table.name]}, Postgres has {got}."
                )
            LOGGER.info(
                "verified %-22s %d == %d", table.name, expected[table.name], got,
            )


def _resolve_pg_url(explicit: str | None) -> str:
    if explicit:
        return explicit
    from app.settings import get_settings

    return get_settings().database_url


def _strip_sqlalchemy_driver(url: str) -> str:
    """psycopg.connect() doesn't accept SQLAlchemy's `+psycopg` driver hint."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite-path",
        default="dados/chokobot.db",
        type=Path,
        help="Path to the legacy SQLite database (read-only).",
    )
    parser.add_argument(
        "--pg-url",
        default=None,
        help="Postgres URL (psycopg-style). Defaults to settings.database_url.",
    )
    parser.add_argument(
        "--tenant-id",
        type=int,
        default=1,
        help="Tenant id to attach all rows to (default 1 = Chokodelícia seed).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the migration. Without this flag the script dry-runs.",
    )
    parser.add_argument(
        "--ignore-fk-warnings",
        action="store_true",
        help="Proceed even if the SQLite source has dangling FK references.",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    sqlite_conn = open_sqlite_readonly(args.sqlite_path)
    LOGGER.info("Opened SQLite read-only at %s", args.sqlite_path)

    fk_warnings = validate_sqlite_fks(sqlite_conn)
    if fk_warnings:
        for warn in fk_warnings:
            LOGGER.warning("FK warning: %s", warn)
        if not args.ignore_fk_warnings:
            raise SystemExit(
                "SQLite source has dangling FK references. "
                "Re-run with --ignore-fk-warnings if intentional."
            )

    pg_url = _resolve_pg_url(args.pg_url)
    if not pg_url.startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
        raise SystemExit(
            f"--pg-url must be a Postgres URL (got {pg_url!r}). "
            "Set DATABASE_URL=postgresql+psycopg://... or pass --pg-url."
        )

    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - import guard
        raise SystemExit(
            "psycopg is not installed. Uncomment psycopg[binary] in "
            "requirements.txt and run `pip install -r requirements.txt`."
        ) from exc

    raw_pg_url = _strip_sqlalchemy_driver(pg_url)
    LOGGER.info("Connecting to Postgres (apply=%s)…", args.apply)

    with psycopg.connect(raw_pg_url, autocommit=False) as pg_conn:
        assert_postgres_ready(pg_conn, args.tenant_id)
        try:
            counts = migrate(sqlite_conn, pg_conn, args.tenant_id, args.apply)
            if args.apply:
                validate_counts(pg_conn, counts, args.tenant_id)
                pg_conn.commit()
                LOGGER.info("Migration committed.")
            else:
                pg_conn.rollback()
                LOGGER.info("Dry-run complete. Re-run with --apply to commit.")
        except Exception:
            pg_conn.rollback()
            raise

    total = sum(counts.values())
    LOGGER.info("Total: %d rows across %d tables.", total, len(counts))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
