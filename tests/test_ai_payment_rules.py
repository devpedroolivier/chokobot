import os
import unittest

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.ai.tools import CakeOrderSchema, SweetOrderSchema, _prepare_cake_order_data, _prepare_sweet_order_data


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


if __name__ == "__main__":
    unittest.main()
