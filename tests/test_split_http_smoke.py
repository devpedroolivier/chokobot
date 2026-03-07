import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

import httpx

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.api.routes import conversation_internal as conversation_internal_module
from app.api.routes import webhook as webhook_module
from app.conversation_main import app as conversation_app
from app.infrastructure.gateways.http_conversation_gateway import HttpConversationGateway
from app.security import clear_replay_cache
from app.services.estados import clear_runtime_state


class FakeWebhookRequest:
    def __init__(self, body: dict, headers: dict[str, str] | None = None):
        self._raw = json.dumps(body).encode("utf-8")
        self.headers = headers or {}

    async def body(self) -> bytes:
        return self._raw


class SplitHttpSmokeTests(unittest.TestCase):
    def setUp(self):
        clear_replay_cache()
        clear_runtime_state()

    def test_edge_webhook_dispatches_to_conversation_service_over_http(self):
        transport = httpx.ASGITransport(app=conversation_app)

        def client_factory():
            return httpx.AsyncClient(transport=transport, base_url="http://conversation.test")

        gateway = HttpConversationGateway(
            "http://conversation.test",
            client_factory=client_factory,
        )
        request = FakeWebhookRequest(
            {"id": "msg-http-1", "phone": "5511999999999", "message": "Oi"},
            headers={"X-Webhook-Secret": "super-secret"},
        )

        with patch.dict(os.environ, {"WEBHOOK_SECRET": "super-secret"}, clear=False):
            with patch.object(
                conversation_internal_module,
                "dispatch_inbound_via_bus",
                AsyncMock(),
            ) as mocked_dispatch:
                with patch.object(webhook_module, "get_conversation_gateway", return_value=gateway):
                    result = asyncio.run(webhook_module.receber_webhook(request))

        self.assertEqual(result, {"status": "ok"})
        mocked_dispatch.assert_awaited_once_with(
            {"id": "msg-http-1", "phone": "5511999999999", "message": "Oi"}
        )


if __name__ == "__main__":
    unittest.main()
