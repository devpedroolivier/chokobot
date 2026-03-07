import os
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.conversation_main import app as conversation_app
from app.edge_main import app as edge_app
from app.api.routes import conversation_internal as conversation_internal_module


class ServiceAppsTests(unittest.TestCase):
    def test_edge_app_registers_webhook_and_health_routes(self):
        paths = {route.path for route in edge_app.routes}

        self.assertIn("/webhook", paths)
        self.assertIn("/healthz", paths)
        self.assertIn("/readyz", paths)

    def test_conversation_app_registers_internal_routes(self):
        paths = {route.path for route in conversation_app.routes}

        self.assertIn("/internal/messages/handle", paths)
        self.assertIn("/internal/messages/reply", paths)
        self.assertIn("/healthz", paths)

    def test_conversation_internal_reply_handler_dispatches_bus(self):
        request = conversation_internal_module.AiReplyRequest(
            telefone="5511999999999",
            text="oi",
            nome_cliente="Cliente Teste",
            cliente_id=1,
        )

        with patch.object(
            conversation_internal_module,
            "generate_ai_reply_via_bus",
            AsyncMock(return_value="Resposta interna"),
        ):
            response = asyncio.run(conversation_internal_module.generate_reply(request))

        self.assertEqual(response, {"status": "ok", "reply": "Resposta interna"})

    def test_conversation_internal_inbound_handler_dispatches_bus(self):
        request = conversation_internal_module.InboundMessageRequest(payload={"message": "oi"})

        with patch.object(
            conversation_internal_module,
            "dispatch_inbound_via_bus",
            AsyncMock(),
        ) as mocked_dispatch:
            response = asyncio.run(conversation_internal_module.handle_inbound_message(request))

        self.assertEqual(response, {"status": "ok"})
        mocked_dispatch.assert_awaited_once_with({"message": "oi"})


if __name__ == "__main__":
    unittest.main()
