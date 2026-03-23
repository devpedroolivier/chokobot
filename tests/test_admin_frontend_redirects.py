import asyncio
import os
import unittest
from unittest.mock import patch

from fastapi import Request
from fastapi.responses import RedirectResponse

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.api.routes.clientes import editar_cliente, listar_clientes, novo_cliente
from app.api.routes.painel import painel_principal
from app.api.routes.pedidos import detalhes_encomenda, listar_encomendas, novo_encomenda_form
from app.infrastructure.web.admin_frontend import resolve_admin_frontend_url


def _request(path: str) -> Request:
    return Request({"type": "http", "method": "GET", "path": path, "headers": []})


class AdminFrontendRedirectsTests(unittest.TestCase):
    def test_resolve_admin_frontend_url_returns_none_without_setting(self):
        with patch.dict(os.environ, {"ADMIN_FRONTEND_URL": ""}, clear=False):
            self.assertIsNone(resolve_admin_frontend_url("/clientes"))

    def test_resolve_admin_frontend_url_concatenates_configured_base(self):
        with patch.dict(os.environ, {"ADMIN_FRONTEND_URL": "https://admin.example.com"}, clear=False):
            self.assertEqual(
                resolve_admin_frontend_url("/encomendas/12"),
                "https://admin.example.com/encomendas/12",
            )

    def test_painel_principal_redirects_to_next_admin_when_frontend_url_is_enabled(self):
        with patch.dict(os.environ, {"ADMIN_FRONTEND_URL": "https://admin.example.com"}, clear=False):
            response = painel_principal(
                _request("/painel"),
                repository=object(),
                customer_repository=object(),
                process_repository=object(),
            )

        self.assertIsInstance(response, RedirectResponse)
        self.assertEqual(response.headers["location"], "https://admin.example.com/")

    def test_listar_clientes_redirects_to_next_admin_when_frontend_url_is_enabled(self):
        with patch.dict(os.environ, {"ADMIN_FRONTEND_URL": "https://admin.example.com"}, clear=False):
            response = listar_clientes(_request("/painel/clientes"), repository=object())

        self.assertIsInstance(response, RedirectResponse)
        self.assertEqual(response.headers["location"], "https://admin.example.com/clientes")

    def test_novo_cliente_redirects_to_next_admin_when_frontend_url_is_enabled(self):
        with patch.dict(os.environ, {"ADMIN_FRONTEND_URL": "https://admin.example.com"}, clear=False):
            response = novo_cliente(_request("/painel/clientes/novo"))

        self.assertIsInstance(response, RedirectResponse)
        self.assertEqual(response.headers["location"], "https://admin.example.com/clientes/novo")

    def test_editar_cliente_redirects_to_next_admin_when_frontend_url_is_enabled(self):
        with patch.dict(os.environ, {"ADMIN_FRONTEND_URL": "https://admin.example.com"}, clear=False):
            response = editar_cliente(_request("/painel/clientes/7/editar"), cliente_id=7, repository=object())

        self.assertIsInstance(response, RedirectResponse)
        self.assertEqual(response.headers["location"], "https://admin.example.com/clientes/7")

    def test_listar_encomendas_redirects_to_next_admin_when_frontend_url_is_enabled(self):
        with patch.dict(os.environ, {"ADMIN_FRONTEND_URL": "https://admin.example.com"}, clear=False):
            response = asyncio.run(listar_encomendas(_request("/painel/encomendas"), repository=object()))

        self.assertIsInstance(response, RedirectResponse)
        self.assertEqual(response.headers["location"], "https://admin.example.com/encomendas")

    def test_novo_encomenda_redirects_to_next_admin_when_frontend_url_is_enabled(self):
        with patch.dict(os.environ, {"ADMIN_FRONTEND_URL": "https://admin.example.com"}, clear=False):
            response = novo_encomenda_form(_request("/painel/encomendas/novo"))

        self.assertIsInstance(response, RedirectResponse)
        self.assertEqual(response.headers["location"], "https://admin.example.com/encomendas/nova")

    def test_detalhes_encomenda_redirects_to_next_admin_when_frontend_url_is_enabled(self):
        with patch.dict(os.environ, {"ADMIN_FRONTEND_URL": "https://admin.example.com"}, clear=False):
            response = asyncio.run(
                detalhes_encomenda(_request("/painel/encomendas/42"), id=42, repository=object())
            )

        self.assertIsInstance(response, RedirectResponse)
        self.assertEqual(response.headers["location"], "https://admin.example.com/encomendas/42")


if __name__ == "__main__":
    unittest.main()
