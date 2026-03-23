import unittest
from unittest.mock import patch

from fastapi import APIRouter

from app.db.schema_guard import SchemaValidationError, validate_runtime_schema
from app.application.use_cases.bootstrap_runtime import bootstrap_runtime
from app.infrastructure.web.app_factory import create_http_app
from app.models import criar_tabelas


class AppBootstrapTests(unittest.TestCase):
    def test_bootstrap_runtime_runs_legacy_schema_setup(self):
        with patch("app.application.use_cases.bootstrap_runtime.criar_tabelas") as mocked_tables:
            with patch("app.application.use_cases.bootstrap_runtime.validate_runtime_schema") as mocked_validate:
                with patch("app.application.use_cases.bootstrap_runtime.ensure_views") as mocked_views:
                    with patch("app.application.use_cases.bootstrap_runtime.log_event") as mocked_log:
                        bootstrap_runtime("startup_complete")

        mocked_tables.assert_called_once_with()
        mocked_validate.assert_called_once_with()
        mocked_views.assert_called_once_with()
        mocked_log.assert_called_once_with("startup_complete")

    def test_create_http_app_registers_router_and_static_mount_when_enabled(self):
        router = APIRouter()

        @router.get("/health")
        def health():
            return {"status": "ok"}

        app, middleware = create_http_app(
            title="Teste",
            router=router,
            startup_event="startup_complete",
            mount_static=True,
        )

        self.assertEqual(app.title, "Teste")
        self.assertTrue(callable(middleware))
        paths = {route.path for route in app.routes}
        self.assertIn("/static", paths)

    def test_validate_runtime_schema_accepts_current_bootstrap_schema(self):
        criar_tabelas()

        validate_runtime_schema()

    def test_validate_runtime_schema_rejects_legacy_encomendas_shape(self):
        with patch("app.db.schema_guard.get_connection") as mocked_get_connection:
            import sqlite3

            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            conn.executescript(
                """
                CREATE TABLE clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT,
                    telefone TEXT
                );
                CREATE TABLE customer_processes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT,
                    process_type TEXT,
                    stage TEXT,
                    status TEXT,
                    draft_payload TEXT
                );
                CREATE TABLE encomendas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_id INTEGER,
                    produto TEXT,
                    detalhes TEXT,
                    data_entrega TEXT
                );
                CREATE TABLE entregas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    encomenda_id INTEGER,
                    status TEXT
                );
                CREATE TABLE pedidos_cafeteria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_id INTEGER,
                    pedido TEXT
                );
                """
            )
            mocked_get_connection.return_value = conn

            with self.assertRaises(SchemaValidationError) as ctx:
                validate_runtime_schema()

        self.assertIn("encomendas", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
