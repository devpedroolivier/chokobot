"""Tenant_id propagation contract (Phase B.5).

Verifies that a tenant_id resolved at the edge (webhook) flows
through HandleInboundMessageCommand → handle_inbound_message →
process_inbound_message and through GenerateAiReplyCommand →
generate_ai_reply → process_message_with_ai. A regression here would
let messages cross tenants downstream of the command bus.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.application.commands import GenerateAiReplyCommand, HandleInboundMessageCommand
from app.application.handlers.generate_ai_reply import generate_ai_reply
from app.application.handlers.handle_inbound_message import handle_inbound_message
from app.utils.payload import resolve_tenant_id


class TenantIdPropagationTests(unittest.IsolatedAsyncioTestCase):
    def test_resolve_tenant_id_extracts_evolution_instance(self):
        payload = {
            "instance": "tenant-piloto",
            "data": {"key": {"remoteJid": "5511999999999@s.whatsapp.net"}},
        }
        self.assertEqual(resolve_tenant_id(payload), "tenant-piloto")

    def test_resolve_tenant_id_returns_none_for_zapi_payload(self):
        payload = {
            "phone": "5511999999999",
            "messageId": "msg-1",
            "text": {"message": "oi"},
        }
        self.assertIsNone(resolve_tenant_id(payload))

    async def test_handle_inbound_message_propagates_tenant_id(self):
        command = HandleInboundMessageCommand(
            payload={"phone": "5511999999999"},
            tenant_id="tenant-piloto",
        )
        with patch(
            "app.application.handlers.handle_inbound_message.process_inbound_message",
            AsyncMock(),
        ) as mocked:
            await handle_inbound_message(command)

        mocked.assert_awaited_once_with(
            {"phone": "5511999999999"}, tenant_id="tenant-piloto"
        )

    async def test_generate_ai_reply_propagates_tenant_id(self):
        command = GenerateAiReplyCommand(
            telefone="5511999999999",
            text="oi",
            nome_cliente="Cliente",
            cliente_id=42,
            tenant_id="tenant-piloto",
        )
        with patch(
            "app.ai.runner.process_message_with_ai",
            AsyncMock(return_value="resposta"),
        ) as mocked:
            reply = await generate_ai_reply(command)

        self.assertEqual(reply, "resposta")
        mocked.assert_awaited_once()
        _, kwargs = mocked.call_args
        self.assertEqual(kwargs["tenant_id"], "tenant-piloto")
        self.assertEqual(kwargs["telefone"], "5511999999999")

    async def test_default_tenant_id_is_none(self):
        command = GenerateAiReplyCommand(
            telefone="5511999999999",
            text="oi",
            nome_cliente="Cliente",
            cliente_id=42,
        )
        with patch(
            "app.ai.runner.process_message_with_ai",
            AsyncMock(return_value="resposta"),
        ) as mocked:
            await generate_ai_reply(command)

        _, kwargs = mocked.call_args
        self.assertIsNone(kwargs["tenant_id"])


if __name__ == "__main__":
    unittest.main()
