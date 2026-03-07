import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.application.service_registry import get_conversation_gateway
from app.infrastructure.gateways.http_conversation_gateway import HttpConversationGateway
from app.infrastructure.gateways.local_conversation_gateway import LocalConversationGateway


class _FakeResponse:
    def __init__(self, payload: dict | None = None, status_code: int = 200):
        self._payload = payload or {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http_{self.status_code}")

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json):
        self.calls.append((url, json))
        return self.responses.pop(0)


class ConversationGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_gateway_dispatches_to_command_bus(self):
        fake_bus = AsyncMock()
        fake_bus.dispatch.return_value = "ok"

        with patch("app.infrastructure.gateways.local_conversation_gateway.get_command_bus", return_value=fake_bus):
            gateway = LocalConversationGateway()
            await gateway.handle_inbound_message({"message": "oi"})
            reply = await gateway.generate_reply(
                telefone="5511999999999",
                text="oi",
                nome_cliente="Cliente",
                cliente_id=1,
            )

        self.assertEqual(fake_bus.dispatch.await_count, 2)
        self.assertEqual(reply, "ok")

    async def test_http_gateway_posts_to_internal_endpoints(self):
        fake_client = _FakeAsyncClient(
            [
                _FakeResponse(),
                _FakeResponse({"status": "ok", "reply": "Resposta remota"}),
            ]
        )

        with patch("app.infrastructure.gateways.http_conversation_gateway.httpx.AsyncClient", return_value=fake_client):
            gateway = HttpConversationGateway("http://conversation.test")
            await gateway.handle_inbound_message({"message": "oi"})
            reply = await gateway.generate_reply(
                telefone="5511999999999",
                text="oi",
                nome_cliente="Cliente",
                cliente_id=1,
            )

        self.assertEqual(reply, "Resposta remota")
        self.assertEqual(fake_client.calls[0][0], "http://conversation.test/internal/messages/handle")
        self.assertEqual(fake_client.calls[1][0], "http://conversation.test/internal/messages/reply")

    async def test_service_registry_uses_http_gateway_when_url_is_configured(self):
        get_conversation_gateway.cache_clear()
        with patch.dict(os.environ, {"CONVERSATION_SERVICE_URL": "http://conversation.test"}, clear=False):
            gateway = get_conversation_gateway()

        self.assertIsInstance(gateway, HttpConversationGateway)

    async def test_service_registry_uses_local_gateway_without_remote_url(self):
        get_conversation_gateway.cache_clear()
        with patch.dict(os.environ, {"CONVERSATION_SERVICE_URL": ""}, clear=False):
            gateway = get_conversation_gateway()

        self.assertIsInstance(gateway, LocalConversationGateway)


if __name__ == "__main__":
    unittest.main()
