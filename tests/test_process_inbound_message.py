import unittest
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.application.use_cases.process_inbound_message import process_inbound_message
from app.services.estados import clear_runtime_state, estados_atendimento, set_bot_ativo


class ProcessInboundMessageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        clear_runtime_state()
        set_bot_ativo(True)

    async def test_reactivate_with_ativar_chat_while_handoff_is_active(self):
        phone = "5511999999999"
        started_at = (datetime.now() - timedelta(minutes=5)).isoformat()
        estados_atendimento[phone] = {"inicio": started_at, "humano": True}

        responder = AsyncMock(return_value=True)
        gerar_resposta = AsyncMock(return_value="ok")

        await process_inbound_message(
            {
                "phone": phone,
                "chatName": "Vania",
                "message": "Ativar chat",
                "id": "msg-ativar-chat",
                "type": "text",
            },
            responder_usuario_fn=responder,
            gerar_resposta_ia_fn=gerar_resposta,
            save_customer_fn=lambda telefone, nome: 1,
        )

        self.assertNotIn(phone, estados_atendimento)
        gerar_resposta.assert_not_awaited()
        self.assertEqual(responder.await_count, 1)
        resposta = responder.await_args.args[1]
        self.assertIn("A Trufinha voltou por aqui", resposta)

    async def test_ignore_message_when_phone_has_automation_disabled(self):
        responder = AsyncMock(return_value=True)
        gerar_resposta = AsyncMock(return_value="ok")

        with patch.dict(
            os.environ,
            {"AUTOMATION_DISABLED_PHONES": "16994665180,16997583311"},
            clear=False,
        ):
            await process_inbound_message(
                {
                    "phone": "5516994665180",
                    "chatName": "Cliente",
                    "message": "Oi",
                    "id": "msg-disabled-phone",
                    "type": "text",
                },
                responder_usuario_fn=responder,
                gerar_resposta_ia_fn=gerar_resposta,
                save_customer_fn=lambda telefone, nome: 1,
            )

        gerar_resposta.assert_not_awaited()
        self.assertEqual(responder.await_count, 0)


if __name__ == "__main__":
    unittest.main()
