import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

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


if __name__ == "__main__":
    unittest.main()
