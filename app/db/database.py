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

Phase B will swap the SQLite-backed ``Database`` for a Postgres
implementation; legacy ``get_connection()`` callers will be migrated
in the same cutover.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator

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
