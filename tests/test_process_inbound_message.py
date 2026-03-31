import unittest
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.application.use_cases.process_inbound_message import process_inbound_message
from app.services.estados import (
    clear_runtime_state,
    estados_atendimento,
    is_phone_opted_out,
    set_bot_ativo,
    set_phone_opted_out,
)


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

    async def test_customer_opt_out_command_pauses_phone_automation(self):
        phone = "5511999999999"
        responder = AsyncMock(return_value=True)
        gerar_resposta = AsyncMock(return_value="ok")

        await process_inbound_message(
            {
                "phone": phone,
                "chatName": "Cliente",
                "message": "desativar bot",
                "id": "msg-opt-out-1",
                "type": "text",
            },
            responder_usuario_fn=responder,
            gerar_resposta_ia_fn=gerar_resposta,
            save_customer_fn=lambda telefone, nome: 1,
        )

        self.assertTrue(is_phone_opted_out(phone))
        gerar_resposta.assert_not_awaited()
        self.assertEqual(responder.await_count, 1)
        self.assertIn("chat foi pausado", responder.await_args.args[1].lower())

    async def test_paused_phone_ignores_messages_until_menu_reactivates(self):
        phone = "5511999999999"
        set_phone_opted_out(phone, True)
        responder = AsyncMock(return_value=True)
        gerar_resposta = AsyncMock(return_value="ok")

        await process_inbound_message(
            {
                "phone": phone,
                "chatName": "Cliente",
                "message": "quero um bolo",
                "id": "msg-opt-out-blocked",
                "type": "text",
            },
            responder_usuario_fn=responder,
            gerar_resposta_ia_fn=gerar_resposta,
            save_customer_fn=lambda telefone, nome: 1,
        )

        self.assertTrue(is_phone_opted_out(phone))
        gerar_resposta.assert_not_awaited()
        self.assertEqual(responder.await_count, 0)

        await process_inbound_message(
            {
                "phone": phone,
                "chatName": "Cliente",
                "message": "menu",
                "id": "msg-opt-out-reactivate",
                "type": "text",
            },
            responder_usuario_fn=responder,
            gerar_resposta_ia_fn=gerar_resposta,
            save_customer_fn=lambda telefone, nome: 1,
        )

        self.assertFalse(is_phone_opted_out(phone))
        gerar_resposta.assert_not_awaited()
        self.assertEqual(responder.await_count, 1)
        self.assertIn("trufinha voltou", responder.await_args.args[1].lower())

    async def test_paused_phone_reactivation_honors_configured_delay(self):
        phone = "5511999999999"
        set_phone_opted_out(phone, True)
        responder = AsyncMock(return_value=True)
        gerar_resposta = AsyncMock(return_value="ok")

        with patch.dict(
            os.environ,
            {"PHONE_OPT_OUT_REACTIVATION_DELAY_SECONDS": "0.35"},
            clear=False,
        ):
            with patch(
                "app.application.use_cases.process_inbound_message.asyncio.sleep",
                new_callable=AsyncMock,
            ) as sleep_mock:
                await process_inbound_message(
                    {
                        "phone": phone,
                        "chatName": "Cliente",
                        "message": "menu",
                        "id": "msg-opt-out-reactivate-delay",
                        "type": "text",
                    },
                    responder_usuario_fn=responder,
                    gerar_resposta_ia_fn=gerar_resposta,
                    save_customer_fn=lambda telefone, nome: 1,
                )

        sleep_mock.assert_awaited_once_with(0.35)
        self.assertFalse(is_phone_opted_out(phone))
        gerar_resposta.assert_not_awaited()
        self.assertEqual(responder.await_count, 1)

    async def test_phone_opt_out_auto_reactivates_after_timeout(self):
        phone = "5511999999999"
        set_phone_opted_out(phone, True)
        responder = AsyncMock(return_value=True)
        gerar_resposta = AsyncMock(return_value="ok")

        with patch.dict(
            os.environ,
            {"PHONE_OPT_OUT_AUTO_RESUME_MINUTES": "30"},
            clear=False,
        ):
            with patch(
                "app.application.use_cases.process_inbound_message.get_phone_opted_out_updated_at",
                return_value=datetime.now(timezone.utc) - timedelta(minutes=31),
            ):
                await process_inbound_message(
                    {
                        "phone": phone,
                        "chatName": "Cliente",
                        "message": "quero um bolo",
                        "id": "msg-opt-out-auto-reactivate",
                        "type": "text",
                    },
                    responder_usuario_fn=responder,
                    gerar_resposta_ia_fn=gerar_resposta,
                    save_customer_fn=lambda telefone, nome: 1,
                )

        self.assertFalse(is_phone_opted_out(phone))
        gerar_resposta.assert_awaited_once_with(phone, "quero um bolo", "Cliente", 1)
        self.assertEqual(responder.await_count, 1)
        self.assertEqual(responder.await_args.args[1], "ok")


if __name__ == "__main__":
    unittest.main()
