import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials

from app.ai import tools as ai_tools
from app.api.routes import clientes as clientes_module
from app.api.routes import painel as painel_module
from app.api.routes import pedidos as pedidos_module
from app.api.routes import webhook as webhook_module
from app.observability import clear_metrics, snapshot_metrics
from app.security import clear_replay_cache, require_panel_auth
from app.utils.payload import is_automated_order_message


class FakeRequest:
    def __init__(self, body: dict, headers: dict[str, str] | None = None):
        self._raw = json.dumps(body).encode("utf-8")
        self.headers = headers or {}

    async def body(self) -> bytes:
        return self._raw


class SecurityHardeningTests(unittest.TestCase):
    def setUp(self):
        clear_replay_cache()
        clear_metrics()
        webhook_module._inbound_phone_locks.clear()

    def test_panel_routes_are_protected_by_auth_dependency(self):
        for router_module in (painel_module, pedidos_module, clientes_module):
            dependencies = [dep.dependency for dep in router_module.router.dependencies]
            self.assertIn(require_panel_auth, dependencies)

    def test_panel_auth_rejects_missing_credentials_when_enabled(self):
        with patch.dict(
            os.environ,
            {
                "PANEL_AUTH_ENABLED": "1",
                "PANEL_AUTH_USERNAME": "admin",
                "PANEL_AUTH_PASSWORD": "secret",
            },
            clear=False,
        ):
            with self.assertRaises(HTTPException) as ctx:
                require_panel_auth(None)

        self.assertEqual(ctx.exception.status_code, 401)

    def test_panel_auth_accepts_valid_credentials(self):
        credentials = HTTPBasicCredentials(username="admin", password="secret")
        with patch.dict(
            os.environ,
            {
                "PANEL_AUTH_ENABLED": "1",
                "PANEL_AUTH_USERNAME": "admin",
                "PANEL_AUTH_PASSWORD": "secret",
            },
            clear=False,
        ):
            self.assertIsNone(require_panel_auth(credentials))

    def test_webhook_rejects_missing_secret_when_verification_enabled(self):
        request = FakeRequest({"id": "msg-1", "phone": "5511999999999", "message": "Oi"})
        with patch.dict(os.environ, {"WEBHOOK_SECRET": "super-secret"}, clear=False):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(webhook_module.receber_webhook(request))

        self.assertEqual(ctx.exception.status_code, 401)

    def test_webhook_detects_replay_and_processes_once(self):
        request = FakeRequest(
            {"id": "msg-2", "phone": "5511999999999", "message": "Oi"},
            headers={"X-Webhook-Secret": "super-secret"},
        )
        with patch.dict(os.environ, {"WEBHOOK_SECRET": "super-secret"}, clear=False):
            with patch.object(webhook_module, "dispatch_inbound_message", AsyncMock()) as mocked_process:
                first = asyncio.run(webhook_module.receber_webhook(request))
                second = asyncio.run(webhook_module.receber_webhook(request))

        self.assertEqual(first, {"status": "ok"})
        self.assertEqual(second["status"], "ignored")
        self.assertEqual(mocked_process.await_count, 1)

    def test_automated_goomer_order_message_is_detected(self):
        payload = {
            "id": "msg-goomer-1",
            "phone": "5511999999999",
            "message": (
                "⭐ GOSTOU DE PEDIR NO NOSSO APP? ⭐\n"
                "Não precisa baixar nada.\n"
                "Confira o pedido abaixo:\n"
                "*Pedido Goomer Delivery #0004*\n"
                "_Pedido gerado pelo Goomer Delivery às 11:45_"
            ),
        }

        self.assertTrue(is_automated_order_message(payload))

    def test_webhook_ignores_automated_goomer_order_message(self):
        request = FakeRequest(
            {
                "id": "msg-goomer-2",
                "phone": "5511999999999",
                "message": (
                    "⭐ GOSTOU DE PEDIR NO NOSSO APP? ⭐\n"
                    "Não precisa baixar nada, adicione o nosso restaurante na tela inicial.\n"
                    "https://pascoachoko.goomer.app/?utm_source=whatsapp\n"
                    "Confira o pedido abaixo:\n"
                    "*Pedido Goomer Delivery #0004*\n"
                    "_Pedido gerado pelo Goomer Delivery às 11:45_"
                ),
            },
            headers={"X-Webhook-Secret": "super-secret"},
        )

        with patch.dict(os.environ, {"WEBHOOK_SECRET": "super-secret"}, clear=False):
            with patch.object(webhook_module, "dispatch_inbound_message", AsyncMock()) as mocked_process:
                result = asyncio.run(webhook_module.receber_webhook(request))

        self.assertEqual(result, {"status": "ignored"})
        mocked_process.assert_not_awaited()

    def test_regular_customer_message_with_order_word_still_processes(self):
        request = FakeRequest(
            {
                "id": "msg-customer-order-1",
                "phone": "5511999999999",
                "message": "Esse pedido e real, pode colocar para domingo?",
            },
            headers={"X-Webhook-Secret": "super-secret"},
        )

        with patch.dict(os.environ, {"WEBHOOK_SECRET": "super-secret"}, clear=False):
            with patch.object(webhook_module, "dispatch_inbound_message", AsyncMock()) as mocked_process:
                result = asyncio.run(webhook_module.receber_webhook(request))

        self.assertEqual(result, {"status": "ok"})
        mocked_process.assert_awaited_once()

    def test_webhook_ignored_test_phone_does_not_increment_metrics(self):
        request = FakeRequest(
            {
                "id": "msg-test-phone-1",
                "phone": "+55 11 88888-8888",
                "message": "⭐ GOSTOU DE PEDIR NO NOSSO APP? ⭐\nPedido Goomer Delivery #1",
            },
            headers={"X-Webhook-Secret": "super-secret"},
        )

        with patch.dict(os.environ, {"WEBHOOK_SECRET": "super-secret"}, clear=False):
            result = asyncio.run(webhook_module.receber_webhook(request))

        self.assertEqual(result, {"status": "ignored", "detail": "test_phone"})
        counters, _ = snapshot_metrics()
        self.assertEqual(counters, {})

    def test_webhook_ignores_configured_test_phone_before_dispatch(self):
        request = FakeRequest(
            {
                "id": "msg-test-phone-config-1",
                "phone": "5511777777777",
                "message": "oi",
            },
            headers={"X-Webhook-Secret": "super-secret"},
        )

        with patch.dict(
            os.environ,
            {
                "WEBHOOK_SECRET": "super-secret",
                "TEST_PHONES": "5511777777777",
            },
            clear=False,
        ):
            with patch.object(webhook_module, "dispatch_inbound_message", AsyncMock()) as mocked_process:
                result = asyncio.run(webhook_module.receber_webhook(request))

        self.assertEqual(result, {"status": "ignored", "detail": "test_phone"})
        mocked_process.assert_not_awaited()

    def test_webhook_cleans_phone_lock_after_processing(self):
        request = FakeRequest(
            {"id": "msg-lock-cleanup-1", "phone": "5511999999999", "message": "Oi"},
            headers={"X-Webhook-Secret": "super-secret"},
        )

        with patch.dict(os.environ, {"WEBHOOK_SECRET": "super-secret"}, clear=False):
            with patch.object(webhook_module, "dispatch_inbound_message", AsyncMock()) as mocked_process:
                result = asyncio.run(webhook_module.receber_webhook(request))

        self.assertEqual(result, {"status": "ok"})
        mocked_process.assert_awaited_once()
        self.assertEqual(webhook_module._inbound_phone_locks, {})

    def test_save_learning_is_blocked_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            learnings_path = os.path.join(tmpdir, "learnings.md")
            with patch.dict(
                os.environ,
                {
                    "AI_SAVE_LEARNING_ENABLED": "0",
                    "AI_LEARNINGS_PATH": learnings_path,
                },
                clear=False,
            ):
                result = ai_tools.save_learning("nao salvar")

        self.assertEqual(result, "Aprendizado persistente desativado neste ambiente.")
        self.assertFalse(os.path.exists(learnings_path))

    def test_save_learning_writes_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            learnings_path = os.path.join(tmpdir, "learnings.md")
            with patch.dict(
                os.environ,
                {
                    "AI_SAVE_LEARNING_ENABLED": "1",
                    "AI_LEARNINGS_PATH": learnings_path,
                },
                clear=False,
            ):
                result = ai_tools.save_learning("teste")

            with open(learnings_path, "r", encoding="utf-8") as handle:
                saved = handle.read()

        self.assertEqual(result, "Aprendizado salvo com sucesso! Vou me lembrar disso.")
        self.assertIn("- teste", saved)


if __name__ == "__main__":
    unittest.main()
