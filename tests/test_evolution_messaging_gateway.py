import json
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")
os.environ.setdefault("EVOLUTION_SERVER_URL", "http://evolution.test")
os.environ.setdefault("EVOLUTION_API_KEY", "test-key")
os.environ.setdefault("EVOLUTION_INSTANCE", "test")

from app.infrastructure.gateways.evolution_messaging_gateway import EvolutionMessagingGateway


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _FakeAsyncClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return self._responses.pop(0)


class EvolutionMessagingGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_text_success_posts_number_and_text_with_apikey(self):
        gateway = EvolutionMessagingGateway()
        fake_client = _FakeAsyncClient([_FakeResponse(200)])

        with tempfile.TemporaryDirectory() as tmpdir:
            outbox_path = os.path.join(tmpdir, "outbox.jsonl")
            with patch(
                "app.infrastructure.gateways.evolution_messaging_gateway.OUTBOX_PATH",
                outbox_path,
            ):
                with patch(
                    "app.infrastructure.gateways.evolution_messaging_gateway.httpx.AsyncClient",
                    return_value=fake_client,
                ):
                    ok = await gateway.send_text("5511999999999", "oi")

        self.assertTrue(ok)
        self.assertEqual(len(fake_client.calls), 1)
        call = fake_client.calls[0]
        self.assertEqual(call["json"], {"number": "5511999999999", "text": "oi"})
        self.assertEqual(call["headers"]["apikey"], "test-key")
        self.assertIn("/message/sendText/test", call["url"])

    async def test_send_text_enqueues_on_non_retriable_http_error(self):
        gateway = EvolutionMessagingGateway()

        with tempfile.TemporaryDirectory() as tmpdir:
            outbox_path = os.path.join(tmpdir, "outbox.jsonl")
            fake_client = _FakeAsyncClient([_FakeResponse(400)])

            with patch(
                "app.infrastructure.gateways.evolution_messaging_gateway.OUTBOX_PATH",
                outbox_path,
            ):
                with patch(
                    "app.infrastructure.gateways.evolution_messaging_gateway.httpx.AsyncClient",
                    return_value=fake_client,
                ):
                    ok = await gateway.send_text("5511999999999", "mensagem")

            self.assertFalse(ok)
            with open(outbox_path, "r", encoding="utf-8") as handle:
                queued = [json.loads(line) for line in handle if line.strip()]

        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["phone"], "5511999999999")
        self.assertEqual(queued[0]["message"], "mensagem")


if __name__ == "__main__":
    unittest.main()
