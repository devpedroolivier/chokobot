import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.config import get_store_closed_notice, is_store_closed
from app.handler import processar_mensagem
from app.infrastructure.gateways.local_catalog_gateway import LocalCatalogGateway
from app.services.estados import clear_runtime_state


class StoreClosureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        clear_runtime_state()

    async def test_handler_ignores_store_closed_flag_and_keeps_flow_running(self):
        payload = {
            "id": "msg-closed-1",
            "phone": "5511999999999",
            "message": "Oi, quero fazer um pedido",
            "chatName": "Cliente Teste",
        }

        with patch.dict(os.environ, {"STORE_CLOSED": "1"}, clear=False):
            with patch("app.handler.responder_usuario", AsyncMock()) as mocked_reply:
                with patch("app.handler.gerar_resposta_ia", AsyncMock(return_value="fluxo normal")) as mocked_ai:
                    with patch("app.handler.save_customer_contact", return_value=1):
                        await processar_mensagem(payload)

        mocked_reply.assert_awaited_once()
        sent_message = mocked_reply.await_args.args[1]
        self.assertEqual(sent_message, "fluxo normal")
        mocked_ai.assert_awaited_once()

    def test_menu_does_not_include_closure_notice_even_when_flag_is_set(self):
        gateway = LocalCatalogGateway()

        with patch.dict(os.environ, {"STORE_CLOSED": "1"}, clear=False):
            menu = gateway.get_menu("pronta_entrega")

        self.assertNotIn("Aviso Importante", menu)
        self.assertNotIn("Loja *FECHADA*", menu)

    def test_store_closed_flag_is_disabled(self):
        with patch.dict(os.environ, {"STORE_CLOSED": "1"}, clear=False):
            self.assertFalse(is_store_closed())

    def test_notice_converts_escaped_newlines_from_env(self):
        with patch.dict(
            os.environ,
            {
                "STORE_CLOSED_NOTICE": "Linha 1\\n\\nLinha 2\\nLinha 3",
            },
            clear=False,
        ):
            notice = get_store_closed_notice()

        self.assertEqual(notice, "Linha 1\n\nLinha 2\nLinha 3")


if __name__ == "__main__":
    unittest.main()
