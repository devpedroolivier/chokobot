import unittest
from unittest.mock import patch

from fastapi import APIRouter

from app.application.use_cases.bootstrap_runtime import bootstrap_runtime
from app.infrastructure.web.app_factory import create_http_app


class AppBootstrapTests(unittest.TestCase):
    def test_bootstrap_runtime_runs_legacy_schema_setup(self):
        with patch("app.application.use_cases.bootstrap_runtime.criar_tabelas") as mocked_tables:
            with patch("app.application.use_cases.bootstrap_runtime.ensure_views") as mocked_views:
                with patch("app.application.use_cases.bootstrap_runtime.log_event") as mocked_log:
                    bootstrap_runtime("startup_complete")

        mocked_tables.assert_called_once_with()
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


if __name__ == "__main__":
    unittest.main()
