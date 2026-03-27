import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

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

    def test_save_cafeteria_order_draft_requires_beverage_variant_for_combo_relampago(self):
        order = ai_tools.CafeteriaOrderSchema(
            itens=[{"nome": "Combo Relampago", "quantidade": 1}],
            modo_recebimento="retirada",
            pagamento={"forma": "PIX"},
        )

        message = ai_tools.save_cafeteria_order_draft_process(
            "5511999999999",
            "Cliente",
            1,
            order,
        )

        self.assertEqual(message, "No Choko Combo (Combo do Dia), escolha a bebida: Suco natural ou Refri 220ml.")

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
        self.assertIn("Subtotal: R$34,50", message)
        self.assertIn("R$34,50", message)
        self.assertEqual(saved_calls[0]["phone"], "5511999999999")
        self.assertIn("2x Croissant (Chocolate)", saved_calls[0]["itens"][0])
        self.assertEqual(process_calls[-1]["process_type"], "ai_cafeteria_order")
        self.assertEqual(process_calls[-1]["status"], "converted")

    def test_create_cafeteria_order_computes_total_with_combo_relampago(self):
        order = ai_tools.CafeteriaOrderSchema(
            itens=[
                {"nome": "Combo Relampago", "variante": "Suco natural", "quantidade": 2},
                {"nome": "Coca Cola KS", "quantidade": 1},
            ],
            data_entrega="24/03/2026",
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
        self.assertIn("2x Choko Combo (Combo do Dia) (Suco natural)", message)
        self.assertIn("1x Coca Cola KS", message)
        self.assertIn("Subtotal: R$53,48", message)
        self.assertIn("Total final: R$53,48", message)
        self.assertIn("2x Choko Combo (Combo do Dia) (Suco natural)", saved_calls[0]["itens"][0])
        self.assertEqual(process_calls[-1]["process_type"], "ai_cafeteria_order")
        self.assertEqual(process_calls[-1]["status"], "converted")

    def test_save_cafeteria_order_draft_defaults_to_today_and_merges_duplicate_items(self):
        order = ai_tools.CafeteriaOrderSchema(
            itens=[
                {"nome": "Croissant", "variante": "Chocolate", "quantidade": 1},
                {"nome": "Croissant", "variante": "Chocolate", "quantidade": 2},
            ],
            modo_recebimento="retirada",
            pagamento={"forma": "PIX"},
        )

        with patch("app.ai.tools.now_in_bot_timezone", return_value=datetime(2026, 3, 25, 9, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))):
            with patch("app.ai.tools._sync_ai_process", return_value=None):
                message = ai_tools.save_cafeteria_order_draft_process(
                    "5511999999999",
                    "Cliente",
                    1,
                    order,
                )

        self.assertIn("Pedido cafeteria", message)
        self.assertIn("- 3x Croissant (Chocolate): R$43,50", message)
        self.assertIn("🚗 Retirada na loja", message)
        self.assertIn("Subtotal: R$43,50", message)
        self.assertIn("Valor: R$43,50", message)

    def test_create_cafeteria_order_requires_delivery_time_for_entrega(self):
        order = ai_tools.CafeteriaOrderSchema(
            itens=[{"nome": "Croissant", "variante": "Chocolate", "quantidade": 1}],
            modo_recebimento="entrega",
            endereco="Rua Teste, 123",
            pagamento={"forma": "PIX"},
        )

        message = ai_tools.create_cafeteria_order("5511999999999", "Cliente", 1, order)

        self.assertEqual(message, "Informe o horario da entrega.")

    def test_create_cafeteria_order_applies_5_reais_delivery_fee(self):
        order = ai_tools.CafeteriaOrderSchema(
            itens=[{"nome": "Croissant", "variante": "Chocolate", "quantidade": 1}],
            data_entrega="10/10/2030",
            horario_retirada="15:00",
            modo_recebimento="entrega",
            endereco="Rua Teste, 123",
            pagamento={"forma": "PIX"},
        )

        with patch("app.ai.tools._sync_ai_process", return_value=None):
            with patch.object(ai_tools, "get_order_gateway") as mocked_gateway:
                mocked_gateway.return_value.save_cafeteria_order.return_value = None
                message = ai_tools.create_cafeteria_order("5511999999999", "Cliente", 1, order)

        self.assertIn("Taxa entrega: R$5,00", message)
        self.assertIn("Total final: R$19,50", message)

    def test_create_cafeteria_order_blocks_combo_relampago_outside_tuesday(self):
        order = ai_tools.CafeteriaOrderSchema(
            itens=[{"nome": "Combo Relampago", "variante": "Suco natural", "quantidade": 1}],
            data_entrega="28/03/2026",
            modo_recebimento="retirada",
            pagamento={"forma": "PIX"},
        )

        message = ai_tools.create_cafeteria_order("5511999999999", "Cliente", 1, order)

        self.assertIn("somente as tercas-feiras", message.casefold())
        self.assertIn("28/03/2026", message)

    def test_create_cafeteria_order_infers_combo_relampago_beverage_alias_from_name(self):
        order = ai_tools.CafeteriaOrderSchema(
            itens=[{"nome": "Combo Suco", "quantidade": 1}],
            data_entrega="24/03/2026",
            modo_recebimento="retirada",
            pagamento={"forma": "PIX"},
        )

        saved_calls = []

        class _OrderGateway:
            def save_cafeteria_order(self, **kwargs):
                saved_calls.append(kwargs)

        class _ProcessRepository:
            def upsert_process(self, **kwargs):
                return 1

        with patch("app.ai.tools.get_order_gateway", return_value=_OrderGateway()):
            with patch("app.ai.tools.get_customer_process_repository", return_value=_ProcessRepository()):
                message = ai_tools.create_cafeteria_order("5511999999999", "Cliente", 1, order)

        self.assertIn("1x Choko Combo (Combo do Dia) (Suco natural)", message)
        self.assertIn("Subtotal: R$23,99", message)
        self.assertIn("1x Choko Combo (Combo do Dia) (Suco natural)", saved_calls[0]["itens"][0])


if __name__ == "__main__":
    unittest.main()
