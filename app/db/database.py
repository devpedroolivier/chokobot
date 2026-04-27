"""Database access layer.

Two APIs coexist while the codebase migrates:

* ``get_connection()`` — legacy: opens a fresh sqlite3 connection on
  every call, callers are responsible for ``conn.close()``. Used by
  every existing repository and model.

* ``Database`` / ``get_database()`` — centralized access used by new
  code. A single connection is cached for the process and shared
  across threads behind an RLock. ``execute() / query_one() /
  query_all()`` accept an optional ``tenant_id`` that is a no-op today
  but is the placeholder for Phase B (Postgres + tenant filtering).

Phase B.8a additions:

* ``is_postgres()`` — checks the configured ``DATABASE_URL`` so the
  rest of the codebase can branch on backend.
* ``open_postgres_connection()`` — opens a fresh psycopg connection,
  used by the Postgres repository implementations.

The SQLite path stays the default until cutover (B.8b) flips
``DATABASE_URL`` to Postgres in production.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from app.observability import increment_counter, log_event
from app.settings import get_settings


# ----------------------------------------------------------------------
#  Legacy API (unchanged)
# ----------------------------------------------------------------------

def get_db_path() -> str:
    return get_settings().db_path


def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    increment_counter("db_connections_total", db_path=os.path.abspath(db_path))
    log_event("db_connect", db_path=os.path.abspath(db_path))
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ----------------------------------------------------------------------
#  New centralized abstraction
# ----------------------------------------------------------------------

class Database:
    """Single-connection SQLite wrapper, thread-safe via RLock.

    Phase B replaces the implementation with an async Postgres pool.
    Public callers (``execute``, ``query_one``, ``query_all``,
    ``transaction``) keep the same signature — ``tenant_id`` is the
    placeholder that becomes load-bearing in Phase B.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path_override = db_path
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    @property
    def db_path(self) -> str:
        return self._db_path_override or get_db_path()

    def connection(self) -> sqlite3.Connection:
        with self._lock:
            if self._connection is None:
                path = self.db_path
                increment_counter("db_connections_total", db_path=os.path.abspath(path))
                log_event("db_pool_connect", db_path=os.path.abspath(path))
                conn = sqlite3.connect(path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys=ON")
                self._connection = conn
            return self._connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connection()
        with self._lock:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def execute(
        self,
        sql: str,
        params: tuple | list | dict = (),
        *,
        tenant_id: str | None = None,
    ) -> sqlite3.Cursor:
        # tenant_id is reserved for Phase B (Postgres + tenant filtering).
        # In single-tenant mode it is silently ignored.
        del tenant_id
        conn = self.connection()
        with self._lock:
            return conn.execute(sql, params)

    def query_one(
        self,
        sql: str,
        params: tuple | list | dict = (),
        *,
        tenant_id: str | None = None,
    ) -> sqlite3.Row | None:
        cur = self.execute(sql, params, tenant_id=tenant_id)
        return cur.fetchone()

    def query_all(
        self,
        sql: str,
        params: tuple | list | dict = (),
        *,
        tenant_id: str | None = None,
    ) -> list[sqlite3.Row]:
        cur = self.execute(sql, params, tenant_id=tenant_id)
        return list(cur.fetchall())

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None


_database: Database | None = None
_database_lock = threading.Lock()


def get_database() -> Database:
    global _database
    if _database is None:
        with _database_lock:
            if _database is None:
                _database = Database()
    return _database


def reset_database() -> None:
    """Drop the cached connection. Tests that mutate ``DB_PATH`` between
    runs must call this to avoid stale handles."""
    global _database
    with _database_lock:
        if _database is not None:
            _database.close()
        _database = None


# ----------------------------------------------------------------------
#  Phase B.8a — Postgres backend helpers
# ----------------------------------------------------------------------

def _normalised_database_url() -> str:
    return get_settings().database_url or ""


def is_postgres() -> bool:
    """True when DATABASE_URL points at Postgres (any psycopg variant)."""
    url = _normalised_database_url()
    return url.startswith(("postgresql://", "postgresql+psycopg://", "postgres://"))


def _strip_sqlalchemy_driver(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def open_postgres_connection() -> Any:
    """Open a fresh psycopg connection. ``psycopg`` is imported lazily
    so the SQLite-only Chokodelícia container keeps starting even when
    the package isn't installed."""
    import psycopg  # type: ignore[import-not-found]

    url = _strip_sqlalchemy_driver(_normalised_database_url())
    increment_counter("db_connections_total", db_path=url)
    log_event("pg_connect")
    return psycopg.connect(url)


_DEFAULT_TENANT_SLUG = "chokodelicia"
_tenant_pk_cache: dict[str, int] = {}
_tenant_pk_cache_lock = threading.Lock()


def resolve_tenant_pk(tenant_slug: str | None) -> int:
    """Translate the application-level tenant slug into the BIGINT
    primary key used by the Postgres schema. Cached in-process; the
    map is tiny (one row per tenant) and slugs are immutable."""
    slug = tenant_slug or _DEFAULT_TENANT_SLUG
    with _tenant_pk_cache_lock:
        cached = _tenant_pk_cache.get(slug)
        if cached is not None:
            return cached
    with open_postgres_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tenants WHERE slug = %s", (slug,))
            row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"Unknown tenant slug: {slug!r}")
    pk = int(row[0])
    with _tenant_pk_cache_lock:
        _tenant_pk_cache[slug] = pk
    return pk


def reset_tenant_pk_cache() -> None:
    with _tenant_pk_cache_lock:
        _tenant_pk_cache.clear()
