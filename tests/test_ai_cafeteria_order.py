import unittest
from unittest.mock import patch

from app.ai import tools as ai_tools


class AICafeteriaOrderTests(unittest.TestCase):
    def test_save_cafeteria_order_draft_requires_variant_for_croissant(self):
        order = ai_tools.CafeteriaOrderSchema(
            itens=[{"nome": "Croissant", "quantidade": 1}],
            modo_recebimento="retirada",
            pagamento={"forma": "PIX"},
        )

        message = ai_tools.save_cafeteria_order_draft_process(
            "5511999999999",
            "Cliente",
            1,
            order,
        )

        self.assertEqual(message, "Informe o sabor do croissant e a quantidade.")

    def test_create_cafeteria_order_validates_items_and_computes_total(self):
        order = ai_tools.CafeteriaOrderSchema(
            itens=[
                {"nome": "Croissant", "variante": "Chocolate", "quantidade": 2},
                {"nome": "Coca Cola KS", "quantidade": 1},
            ],
            modo_recebimento="retirada",
            pagamento={"forma": "PIX"},
        )

        saved_calls = []
        process_calls = []

        class _OrderGateway:
            def save_cafeteria_order(self, **kwargs):
                saved_calls.append(kwargs)

        class _ProcessRepository:
            def upsert_process(self, **kwargs):
                process_calls.append(kwargs)
                return 1

        with patch("app.ai.tools.get_order_gateway", return_value=_OrderGateway()):
            with patch("app.ai.tools.get_customer_process_repository", return_value=_ProcessRepository()):
                message = ai_tools.create_cafeteria_order(
                    "5511999999999",
                    "Cliente",
                    1,
                    order,
                )

        self.assertIn("Pedido cafeteria salvo com sucesso!", message)
        self.assertIn("2x Croissant (Chocolate)", message)
        self.assertIn("1x Coca Cola KS", message)
        self.assertIn("R$34,50", message)
        self.assertEqual(saved_calls[0]["phone"], "5511999999999")
        self.assertIn("2x Croissant (Chocolate)", saved_calls[0]["itens"][0])
        self.assertEqual(process_calls[-1]["process_type"], "ai_cafeteria_order")
        self.assertEqual(process_calls[-1]["status"], "converted")


if __name__ == "__main__":
    unittest.main()
