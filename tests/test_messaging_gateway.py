import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.infrastructure.gateways.zapi_messaging_gateway import ZapiMessagingGateway
from app.utils.mensagens import responder_usuario


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _FakeAsyncClient:
    def __init__(self, responses):
        self._responses = list(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        return self._responses.pop(0)


class MessagingGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_gateway_enqueues_and_returns_false_on_non_retriable_http_error(self):
        gateway = ZapiMessagingGateway()

        with tempfile.TemporaryDirectory() as tmpdir:
            outbox_path = os.path.join(tmpdir, "outbox.jsonl")
            fake_client = _FakeAsyncClient([_FakeResponse(400)])

            with patch("app.infrastructure.gateways.zapi_messaging_gateway.OUTBOX_PATH", outbox_path):
                with patch(
                    "app.infrastructure.gateways.zapi_messaging_gateway.httpx.AsyncClient",
                    return_value=fake_client,
                ):
                    ok = await gateway.send_text("5511999999999", "mensagem")

            self.assertFalse(ok)
            with open(outbox_path, "r", encoding="utf-8") as handle:
                queued = [json.loads(line) for line in handle if line.strip()]

        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["phone"], "5511999999999")
        self.assertEqual(queued[0]["message"], "mensagem")

    async def test_responder_usuario_delegates_formatted_message_to_gateway(self):
        fake_gateway = AsyncMock()
        fake_gateway.send_text.return_value = True

        with patch("app.utils.mensagens.get_messaging_gateway", return_value=fake_gateway):
            ok = await responder_usuario("5511999999999", "### Kit Festou")

        self.assertTrue(ok)
        fake_gateway.send_text.assert_awaited_once_with("5511999999999", "🎉 Kit Festou")


if __name__ == "__main__":
    unittest.main()
