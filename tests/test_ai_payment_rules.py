import os
import unittest

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.ai.tools import (
    CakeOrderSchema,
    CafeteriaOrderSchema,
    SweetOrderSchema,
    _prepare_cafeteria_order_data,
    _prepare_cake_order_data,
    _prepare_sweet_order_data,
)


class AIPaymentRulesTests(unittest.TestCase):
    def test_prepare_cake_order_clears_change_for_pix(self):
        dados, error = _prepare_cake_order_data(
            CakeOrderSchema(
                linha="tradicional",
                categoria="tradicional",
                tamanho="B3",
                massa="Chocolate",
                recheio="Brigadeiro",
                mousse="Ninho",
                descricao="Bolo teste",
                data_entrega="10/10/2030",
                horario_retirada="15:00",
                modo_recebimento="retirada",
                pagamento={"forma": "PIX", "troco_para": 200},
            )
        )

        self.assertIsNone(error)
        assert dados is not None
        self.assertEqual(dados["pagamento"]["forma"], "PIX")
        self.assertIsNone(dados["pagamento"]["troco_para"])

    def test_prepare_sweet_order_clears_change_for_card(self):
        prepared, error = _prepare_sweet_order_data(
            SweetOrderSchema(
                itens=[{"nome": "Brigadeiro Escama", "quantidade": 10}],
                data_entrega="10/10/2030",
                horario_retirada="15:00",
                modo_recebimento="retirada",
                pagamento={"forma": "Cartão (débito/crédito)", "troco_para": 100},
            )
        )

        self.assertIsNone(error)
        assert prepared is not None
        self.assertEqual(prepared["dados"]["pagamento"]["forma"], "Cartão (débito/crédito)")
        self.assertIsNone(prepared["dados"]["pagamento"]["troco_para"])

    def test_prepare_cake_order_preserves_change_for_cash(self):
        dados, error = _prepare_cake_order_data(
            CakeOrderSchema(
                linha="tradicional",
                categoria="tradicional",
                tamanho="B3",
                massa="Chocolate",
                recheio="Brigadeiro",
                mousse="Ninho",
                descricao="Bolo teste",
                data_entrega="10/10/2030",
                horario_retirada="15:00",
                modo_recebimento="retirada",
                pagamento={"forma": "Dinheiro", "troco_para": 200},
            )
        )

        self.assertIsNone(error)
        assert dados is not None
        self.assertEqual(dados["pagamento"]["forma"], "Dinheiro")
        self.assertEqual(dados["pagamento"]["troco_para"], 200.0)

    def test_prepare_cake_order_allows_card_installments_above_100(self):
        dados, error = _prepare_cake_order_data(
            CakeOrderSchema(
                linha="tradicional",
                categoria="tradicional",
                tamanho="B3",
                massa="Chocolate",
                recheio="Brigadeiro",
                mousse="Ninho",
                descricao="Bolo teste",
                data_entrega="10/10/2030",
                horario_retirada="15:00",
                modo_recebimento="retirada",
                pagamento={"forma": "Cartão (débito/crédito)", "parcelas": 2},
            )
        )

        self.assertIsNone(error)
        assert dados is not None
        self.assertEqual(dados["pagamento"]["forma"], "Cartão (débito/crédito)")
        self.assertEqual(dados["pagamento"]["parcelas"], 2)

    def test_prepare_sweet_order_clears_card_installments_at_or_below_100(self):
        prepared, error = _prepare_sweet_order_data(
            SweetOrderSchema(
                itens=[{"nome": "Brigadeiro Escama", "quantidade": 10}],
                data_entrega="10/10/2030",
                horario_retirada="15:00",
                modo_recebimento="retirada",
                pagamento={"forma": "Cartão (débito/crédito)", "parcelas": 2},
            )
        )

        self.assertIsNone(error)
        assert prepared is not None
        self.assertIsNone(prepared["dados"]["pagamento"]["parcelas"])

    def test_prepare_cafeteria_order_caps_card_installments_to_two(self):
        prepared, error = _prepare_cafeteria_order_data(
            CafeteriaOrderSchema(
                itens=[{"nome": "Croissant", "variante": "Chocolate", "quantidade": 8}],
                horario_retirada="15:00",
                modo_recebimento="retirada",
                pagamento={"forma": "Cartão (débito/crédito)", "parcelas": 5},
            )
        )

        self.assertIsNone(error)
        assert prepared is not None
        self.assertEqual(prepared["pagamento"]["parcelas"], 2)


if __name__ == "__main__":
    unittest.main()
