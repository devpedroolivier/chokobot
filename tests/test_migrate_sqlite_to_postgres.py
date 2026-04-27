"""Pure-function tests for the SQLite→Postgres migration script (Phase B.3).

Postgres-touching paths are exercised manually during the cutover
rehearsal; here we only validate the deterministic pieces:

- ``project_row`` puts columns in the order PG expects, with tenant_id last
- ``build_insert_sql`` matches ``project_row`` shape
- ``resync_sequence_sql`` is the no-op-safe variant
- ``validate_sqlite_fks`` flags dangling references
- ``open_sqlite_readonly`` actually opens read-only (writes raise)
- ``_strip_sqlalchemy_driver`` normalises the URL for psycopg.connect
"""
from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.migrate_sqlite_to_postgres import (
    TABLES,
    _strip_sqlalchemy_driver,
    build_insert_sql,
    open_sqlite_readonly,
    project_row,
    resync_sequence_sql,
    validate_sqlite_fks,
)


class ProjectRowTests(unittest.TestCase):
    def test_appends_tenant_id_after_declared_columns(self):
        row = {"id": 1, "nome": "Ana", "telefone": "5511", "criado_em": "2024-01-01"}
        result = project_row(row, tenant_id=42, columns=("id", "nome", "telefone", "criado_em"))
        self.assertEqual(result, (1, "Ana", "5511", "2024-01-01", 42))

    def test_preserves_column_order_strictly(self):
        row = {"a": "x", "b": "y", "c": "z"}
        result = project_row(row, tenant_id=7, columns=("c", "a", "b"))
        self.assertEqual(result, ("z", "x", "y", 7))

    def test_passes_through_none(self):
        row = {"id": 1, "valor": None}
        result = project_row(row, tenant_id=1, columns=("id", "valor"))
        self.assertEqual(result, (1, None, 1))


class InsertSqlTests(unittest.TestCase):
    def test_matches_project_row_shape(self):
        columns = ("id", "nome", "telefone", "criado_em")
        sql = build_insert_sql("clientes", columns)
        self.assertIn("clientes (id, nome, telefone, criado_em, tenant_id)", sql)
        # 4 declared cols + tenant_id = 5 placeholders
        self.assertEqual(sql.count("%s"), 5)

    def test_full_clientes_insert_string(self):
        columns = ("id", "nome", "telefone", "criado_em")
        self.assertEqual(
            build_insert_sql("clientes", columns),
            "INSERT INTO clientes (id, nome, telefone, criado_em, tenant_id) "
            "VALUES (%s, %s, %s, %s, %s)",
        )


class ResyncSequenceTests(unittest.TestCase):
    def test_uses_setval_with_is_called_guard(self):
        sql = resync_sequence_sql("encomendas")
        self.assertIn("pg_get_serial_sequence('encomendas', 'id')", sql)
        self.assertIn("MAX(id) IS NOT NULL", sql)
        self.assertIn("GREATEST", sql)


class StripSqlAlchemyDriverTests(unittest.TestCase):
    def test_strips_psycopg_driver(self):
        self.assertEqual(
            _strip_sqlalchemy_driver("postgresql+psycopg://u:p@h:5432/db"),
            "postgresql://u:p@h:5432/db",
        )

    def test_leaves_plain_url_alone(self):
        self.assertEqual(
            _strip_sqlalchemy_driver("postgresql://u:p@h:5432/db"),
            "postgresql://u:p@h:5432/db",
        )


class TableSpecsTests(unittest.TestCase):
    """Lock the FK-safe insertion order. Reordering breaks the migration."""

    def test_clientes_first_then_children(self):
        names = [t.name for t in TABLES]
        self.assertLess(names.index("clientes"), names.index("encomendas"))
        self.assertLess(names.index("encomendas"), names.index("entregas"))
        self.assertLess(names.index("encomendas"), names.index("encomenda_doces"))
        self.assertLess(names.index("clientes"), names.index("pedidos_cafeteria"))
        self.assertLess(names.index("clientes"), names.index("atendimentos"))


class SqliteReadonlyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "src.db"
        # Build a minimal source DB.
        rw = sqlite3.connect(self.path)
        rw.executescript(
            """
            CREATE TABLE clientes (
                id INTEGER PRIMARY KEY, nome TEXT, telefone TEXT, criado_em TEXT
            );
            INSERT INTO clientes VALUES (1, 'Ana', '5511', '2024-01-01');
            """,
        )
        rw.commit()
        rw.close()

    def tearDown(self):
        self._tmp.cleanup()

    def test_open_readonly_blocks_writes(self):
        conn = open_sqlite_readonly(self.path)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("INSERT INTO clientes VALUES (2, 'B', '5512', '2024-01-02')")
        finally:
            conn.close()

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            open_sqlite_readonly(Path(self._tmp.name) / "does-not-exist.db")


class ValidateSqliteFksTests(unittest.TestCase):
    """Build a tiny SQLite mirror of the real schema and make sure the FK
    sweep finds dangling refs (without us having to spin up Postgres)."""

    def _build_db(self, path: Path, *, with_orphan: bool) -> None:
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE clientes (
                id INTEGER PRIMARY KEY, nome TEXT, telefone TEXT, criado_em TEXT
            );
            CREATE TABLE encomendas (
                id INTEGER PRIMARY KEY, cliente_id INTEGER NOT NULL,
                categoria TEXT, produto TEXT, tamanho TEXT, massa TEXT,
                recheio TEXT, mousse TEXT, adicional TEXT,
                kit_festou INTEGER DEFAULT 0, quantidade INTEGER DEFAULT 1,
                data_entrega TEXT, horario TEXT, valor_total REAL,
                serve_pessoas INTEGER, criado_em TEXT
            );
            CREATE TABLE entregas (
                id INTEGER PRIMARY KEY, encomenda_id INTEGER NOT NULL,
                tipo TEXT, endereco TEXT, data_agendada TEXT, status TEXT
            );
            CREATE TABLE pedidos_cafeteria (
                id INTEGER PRIMARY KEY, cliente_id INTEGER NOT NULL,
                pedido TEXT, criado_em TEXT
            );
            CREATE TABLE encomenda_doces (
                id INTEGER PRIMARY KEY, encomenda_id INTEGER NOT NULL,
                nome TEXT, qtd INTEGER, preco REAL, unit REAL
            );
            CREATE TABLE atendimentos (
                id INTEGER PRIMARY KEY, cliente_id INTEGER NOT NULL,
                mensagem TEXT, criado_em TEXT
            );
            CREATE TABLE customer_processes (
                id INTEGER PRIMARY KEY, phone TEXT, customer_id INTEGER,
                process_type TEXT, stage TEXT, status TEXT, source TEXT,
                draft_payload TEXT, order_id INTEGER,
                created_at TEXT, updated_at TEXT
            );
            INSERT INTO clientes VALUES (1, 'Ana', '5511', '2024-01-01');
            INSERT INTO encomendas (id, cliente_id) VALUES (1, 1);
            """,
        )
        if with_orphan:
            # encomenda_doces row referencing a non-existent encomenda
            conn.execute(
                "INSERT INTO encomenda_doces "
                "(id, encomenda_id, nome, qtd) VALUES (1, 999, 'Brigadeiro', 5)",
            )
        conn.commit()
        conn.close()

    def test_clean_db_yields_no_warnings(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "clean.db"
            self._build_db(path, with_orphan=False)
            conn = open_sqlite_readonly(path)
            try:
                self.assertEqual(validate_sqlite_fks(conn), [])
            finally:
                conn.close()

    def test_dangling_fk_is_reported(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "dirty.db"
            self._build_db(path, with_orphan=True)
            conn = open_sqlite_readonly(path)
            try:
                warnings = validate_sqlite_fks(conn)
                self.assertTrue(any("encomenda_doces.encomenda_id" in w for w in warnings))
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
