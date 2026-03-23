import os
import unittest
from unittest.mock import patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.ai.tools import (
    CakeOrderSchema,
    SweetOrderSchema,
    create_cake_order,
    save_sweet_order_draft_process,
)


class AIOrderProcessSyncTests(unittest.TestCase):
    def test_create_cake_order_marks_ai_process_as_converted(self):
        process_calls = []
        delivery_calls = []

        class _OrderGateway:
            def create_order(self, *, phone, dados, nome_cliente, cliente_id):
                self.last_payload = {
                    "phone": phone,
                    "dados": dados,
                    "nome_cliente": nome_cliente,
                    "cliente_id": cliente_id,
                }
                return 321

        class _DeliveryGateway:
            def create_delivery(self, **kwargs):
                delivery_calls.append(kwargs)

        class _ProcessRepository:
            def upsert_process(self, **kwargs):
                process_calls.append(kwargs)
                return 1

        order = CakeOrderSchema(
            linha="tradicional",
            categoria="tradicional",
            tamanho="B3",
            massa="Chocolate",
            recheio="Brigadeiro",
            mousse="Ninho",
            descricao="Bolo tradicional de chocolate",
            data_entrega="10/10/2030",
            horario_retirada="15:00",
            modo_recebimento="entrega",
            endereco="Rua Teste, 123",
            pagamento={"forma": "PIX"},
        )

        with patch("app.ai.tools.get_order_gateway", return_value=_OrderGateway()):
            with patch("app.ai.tools.get_delivery_gateway", return_value=_DeliveryGateway()):
                with patch("app.ai.tools.get_customer_process_repository", return_value=_ProcessRepository()):
                    result = create_cake_order("5511999999999", "Cliente", 7, order)

        self.assertIn("Pedido salvo com sucesso", result)
        self.assertEqual(delivery_calls[0]["tipo"], "entrega")
        self.assertEqual(process_calls[-1]["process_type"], "ai_cake_order")
        self.assertEqual(process_calls[-1]["stage"], "pedido_confirmado")
        self.assertEqual(process_calls[-1]["status"], "converted")
        self.assertEqual(process_calls[-1]["order_id"], 321)

    def test_save_sweet_order_draft_process_marks_ai_process_as_active(self):
        process_calls = []

        class _ProcessRepository:
            def upsert_process(self, **kwargs):
                process_calls.append(kwargs)
                return 9

        order = SweetOrderSchema(
            itens=[{"nome": "Brigadeiro Escama", "quantidade": 10}],
            data_entrega="10/10/2030",
            horario_retirada="15:00",
            modo_recebimento="retirada",
            pagamento={"forma": "PIX"},
        )

        with patch("app.ai.tools.get_customer_process_repository", return_value=_ProcessRepository()):
            result = save_sweet_order_draft_process("5511999999999", "Cliente", 7, order)

        self.assertIn("rascunho", result.casefold())
        self.assertEqual(process_calls[-1]["process_type"], "ai_sweet_order")
        self.assertEqual(process_calls[-1]["stage"], "aguardando_confirmacao")
        self.assertEqual(process_calls[-1]["status"], "active")
        self.assertEqual(process_calls[-1]["draft_payload"]["itens"], ["Brigadeiro Escama x10"])


if __name__ == "__main__":
    unittest.main()
