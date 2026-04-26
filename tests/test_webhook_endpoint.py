"""End-to-end tests for the /webhook endpoint.

Covers the inbound pipeline at the HTTP boundary: HMAC verification,
replay window, ignore rules (group / from_me / automated / test phone),
JSON parsing and the per-phone lock that serializes inbound bursts.

The conversation gateway and event bus are stubbed so the runner /
OpenAI / SQLite paths are not exercised — those layers have their own
test files.
"""
from __future__ import annotations

import asyncio
import os
import unittest
from typing import Any
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("MESSAGING_PROVIDER", "zapi")

from fastapi.testclient import TestClient

from app.api.routes import webhook as webhook_module
from app.main import app
from app.security import clear_replay_cache


def _zapi_payload(*, message: str = "oi", phone: str = "5511999999999",
                  message_id: str = "msg-1", from_me: bool = False,
                  is_group: bool = False) -> dict:
    return {
        "phone": phone,
        "messageId": message_id,
        "fromMe": from_me,
        "isGroup": is_group,
        "chatName": "Cliente Teste",
        "type": "ReceivedCallback",
        "text": {"message": message},
    }


class WebhookEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_replay_cache()
        webhook_module._inbound_phone_locks.clear()
        # Conversation gateway is stubbed: returns immediately without
        # touching the AI runner. Event bus is also stubbed so the
        # JSONL writer doesn't run.
        self._gateway_patch = patch.object(
            webhook_module,
            "get_conversation_gateway",
            return_value=type("G", (), {"handle_inbound_message": AsyncMock(return_value=None)})(),
        )
        self._event_bus_patch = patch.object(
            webhook_module,
            "get_event_bus",
            return_value=type("B", (), {"publish": lambda self, evt: None})(),
        )
        self._responder_patch = patch.object(webhook_module, "responder_usuario", AsyncMock())
        self._gateway_patch.start()
        self._event_bus_patch.start()
        self._responder_patch.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self._responder_patch.stop()
        self._event_bus_patch.stop()
        self._gateway_patch.stop()

    # ------------------------------------------------------------------
    #  Happy path
    # ------------------------------------------------------------------

    def test_valid_payload_returns_ok_and_dispatches(self):
        gateway = type(
            "G",
            (),
            {"handle_inbound_message": AsyncMock(return_value=None)},
        )()
        with patch.object(webhook_module, "get_conversation_gateway", return_value=gateway):
            response = self.client.post("/webhook", json=_zapi_payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        gateway.handle_inbound_message.assert_awaited_once()

    # ------------------------------------------------------------------
    #  Ignore rules
    # ------------------------------------------------------------------

    def test_from_me_payload_is_ignored(self):
        response = self.client.post("/webhook", json=_zapi_payload(from_me=True))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ignored"})

    def test_group_payload_is_ignored(self):
        response = self.client.post("/webhook", json=_zapi_payload(is_group=True))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ignored"})

    def test_test_phone_payload_is_ignored(self):
        with patch.dict(os.environ, {"TEST_PHONES": "5511999999999"}, clear=False):
            response = self.client.post("/webhook", json=_zapi_payload())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ignored")
        self.assertEqual(body["detail"], "test_phone")

    def test_delivery_callback_is_ignored(self):
        payload = _zapi_payload()
        payload["type"] = "DeliveryCallback"
        response = self.client.post("/webhook", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ignored"})

    # ------------------------------------------------------------------
    #  Replay protection
    # ------------------------------------------------------------------

    def test_replay_of_same_message_id_is_ignored(self):
        first = self.client.post("/webhook", json=_zapi_payload(message_id="dup-1"))
        self.assertEqual(first.json(), {"status": "ok"})

        second = self.client.post("/webhook", json=_zapi_payload(message_id="dup-1"))
        self.assertEqual(second.status_code, 200)
        body = second.json()
        self.assertEqual(body["status"], "ignored")
        self.assertEqual(body["detail"], "replay_detected")

    def test_distinct_message_ids_are_both_processed(self):
        first = self.client.post("/webhook", json=_zapi_payload(message_id="a"))
        second = self.client.post("/webhook", json=_zapi_payload(message_id="b"))
        self.assertEqual(first.json(), {"status": "ok"})
        self.assertEqual(second.json(), {"status": "ok"})

    # ------------------------------------------------------------------
    #  HMAC verification
    # ------------------------------------------------------------------

    def test_invalid_secret_returns_401_when_verification_enabled(self):
        with patch.dict(
            os.environ,
            {
                "WEBHOOK_VERIFY_ENABLED": "1",
                "WEBHOOK_SECRET": "expected-secret",
                "WEBHOOK_SECRET_HEADER": "X-Webhook-Secret",
            },
            clear=False,
        ):
            response = self.client.post(
                "/webhook",
                json=_zapi_payload(),
                headers={"X-Webhook-Secret": "wrong"},
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "invalid_webhook_secret"})

    def test_correct_secret_passes_verification(self):
        with patch.dict(
            os.environ,
            {
                "WEBHOOK_VERIFY_ENABLED": "1",
                "WEBHOOK_SECRET": "expected-secret",
                "WEBHOOK_SECRET_HEADER": "X-Webhook-Secret",
            },
            clear=False,
        ):
            response = self.client.post(
                "/webhook",
                json=_zapi_payload(message_id="hmac-ok"),
                headers={"X-Webhook-Secret": "expected-secret"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_missing_secret_returns_401_when_required(self):
        with patch.dict(
            os.environ,
            {
                "WEBHOOK_VERIFY_ENABLED": "1",
                "WEBHOOK_SECRET": "expected-secret",
                "WEBHOOK_SECRET_HEADER": "X-Webhook-Secret",
            },
            clear=False,
        ):
            response = self.client.post("/webhook", json=_zapi_payload())
        self.assertEqual(response.status_code, 401)

    def test_disabled_verification_accepts_request_without_header(self):
        with patch.dict(
            os.environ,
            {"WEBHOOK_VERIFY_ENABLED": "0"},
            clear=False,
        ):
            response = self.client.post("/webhook", json=_zapi_payload(message_id="no-hmac"))
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------
    #  Malformed payloads
    # ------------------------------------------------------------------

    def test_malformed_json_returns_400(self):
        response = self.client.post(
            "/webhook",
            data="this is not json",
            headers={"content-type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "invalid_json"})

    # ------------------------------------------------------------------
    #  Lock per phone — concurrent inbound for the same number serializes
    # ------------------------------------------------------------------


class WebhookPhoneLockTests(unittest.IsolatedAsyncioTestCase):
    """Tests the per-phone serialization primitive used by the webhook
    handler. Drives the lock directly so the test is deterministic."""

    async def asyncSetUp(self) -> None:
        webhook_module._inbound_phone_locks.clear()

    async def test_concurrent_workers_for_same_phone_are_serialized(self):
        execution_order: list[str] = []
        release_first = asyncio.Event()

        async def worker(label: str, hold: asyncio.Event | None) -> None:
            lock = await webhook_module._acquire_inbound_phone_lock("5511999999999")
            try:
                execution_order.append(f"start:{label}")
                if hold is not None:
                    await hold.wait()
                execution_order.append(f"end:{label}")
            finally:
                await webhook_module._release_inbound_phone_lock("5511999999999", lock)

        first = asyncio.create_task(worker("a", release_first))
        # Yield so the first task acquires the lock before the second one queues.
        await asyncio.sleep(0)
        second = asyncio.create_task(worker("b", None))
        # Give the second task a chance to attempt acquiring (it must wait).
        await asyncio.sleep(0.01)
        self.assertEqual(execution_order, ["start:a"])
        release_first.set()
        await asyncio.gather(first, second)

        self.assertEqual(execution_order, ["start:a", "end:a", "start:b", "end:b"])

    async def test_lock_is_released_even_when_worker_raises(self):
        async def failing_worker() -> None:
            lock = await webhook_module._acquire_inbound_phone_lock("5511777777777")
            try:
                raise RuntimeError("boom")
            finally:
                await webhook_module._release_inbound_phone_lock("5511777777777", lock)

        with self.assertRaises(RuntimeError):
            await failing_worker()

        # Subsequent acquire must not block: lock is free.
        lock = await asyncio.wait_for(
            webhook_module._acquire_inbound_phone_lock("5511777777777"), timeout=0.5
        )
        await webhook_module._release_inbound_phone_lock("5511777777777", lock)


if __name__ == "__main__":
    unittest.main()
