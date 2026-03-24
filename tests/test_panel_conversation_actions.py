import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.api.routes import painel as painel_module
from app.services.estados import conversation_threads, estados_atendimento


class PanelConversationActionsTests(unittest.TestCase):
    def setUp(self):
        conversation_threads.clear()
        estados_atendimento.clear()

    def test_manual_reply_route_sends_human_message_and_records_manual_mode(self):
        class _CustomerRepository:
            def get_customer_by_phone(self, telefone: str):
                return type("Customer", (), {"nome": "Ana"})()

        class _ProcessRepository:
            pass

        request = painel_module.ManualConversationReplyRequest(
            message="Vamos seguir por aqui.",
            disable_ai=True,
            notify_handoff=False,
        )

        with patch.object(painel_module, "activate_human_handoff", return_value="handoff") as mocked_handoff:
            with patch.object(
                painel_module,
                "responder_usuario_com_contexto",
                AsyncMock(return_value=True),
            ) as mocked_reply:
                response = asyncio.run(
                    painel_module.responder_conversa_manual(
                        "5511999999999",
                        request,
                        customer_repository=_CustomerRepository(),
                        process_repository=_ProcessRepository(),
                    )
                )

        payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["automation_mode"], "manual")
        mocked_handoff.assert_called_once()
        mocked_reply.assert_awaited_once()
        messages = conversation_threads["5511999999999"]["messages"]
        self.assertEqual(messages[0]["role"], "contexto")

    def test_automation_route_reactivates_ai_and_notifies_customer(self):
        telefone = "5511888888888"
        estados_atendimento[telefone] = {"humano": True, "inicio": "2026-03-24T12:00:00"}

        class _CustomerRepository:
            def get_customer_by_phone(self, telefone: str):
                return type("Customer", (), {"nome": "Bia"})()

        class _ProcessRepository:
            pass

        request = painel_module.ConversationAutomationRequest(enabled=True, notify_customer=True)

        with patch.object(painel_module, "deactivate_human_handoff", return_value=True) as mocked_deactivate:
            with patch.object(
                painel_module,
                "responder_usuario_com_contexto",
                AsyncMock(return_value=True),
            ) as mocked_reply:
                response = asyncio.run(
                    painel_module.atualizar_automacao_conversa(
                        telefone,
                        request,
                        customer_repository=_CustomerRepository(),
                        process_repository=_ProcessRepository(),
                    )
                )

        payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["automation_mode"], "ai")
        mocked_deactivate.assert_called_once()
        mocked_reply.assert_awaited_once()
        messages = conversation_threads[telefone]["messages"]
        self.assertEqual(messages[0]["content"], "IA reativada pelo painel.")


if __name__ == "__main__":
    unittest.main()
