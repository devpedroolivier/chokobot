import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.config import get_store_closed_notice
from app.handler import processar_mensagem
from app.infrastructure.gateways.local_catalog_gateway import LocalCatalogGateway
from app.services.estados import clear_runtime_state


class StoreClosureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        clear_runtime_state()

    async def test_handler_replies_with_closure_notice_and_stops_flow(self):
        payload = {
            "id": "msg-closed-1",
            "phone": "5511999999999",
            "message": "Oi, quero fazer um pedido",
            "chatName": "Cliente Teste",
        }

        with patch.dict(os.environ, {"STORE_CLOSED": "1"}, clear=False):
            with patch("app.handler.responder_usuario", AsyncMock()) as mocked_reply:
                with patch("app.handler.gerar_resposta_ia", AsyncMock()) as mocked_ai:
                    with patch("app.models.clientes.salvar_cliente", return_value=1):
                        await processar_mensagem(payload)

        mocked_reply.assert_awaited_once()
        sent_notice = mocked_reply.await_args.args[1]
        self.assertIn("Aviso Importante", sent_notice)
        self.assertIn("FECHADA", sent_notice)
        mocked_ai.assert_not_awaited()

    def test_menu_includes_closure_notice_when_store_is_closed(self):
        gateway = LocalCatalogGateway()

        with patch.dict(os.environ, {"STORE_CLOSED": "1"}, clear=False):
            menu = gateway.get_menu("pronta_entrega")

        self.assertIn("Aviso Importante", menu)
        self.assertIn("Loja *FECHADA*", menu)

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
