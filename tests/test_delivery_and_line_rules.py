import os
import unittest

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.ai.tools import CakeOrderSchema, create_cake_order
from app.services.encomendas_utils import LIMITE_HORARIO_ENTREGA, _horario_entrega_permitido, _linha_canonica


class DeliveryAndLineRulesTests(unittest.TestCase):
    def test_delivery_cutoff_rule(self):
        self.assertTrue(_horario_entrega_permitido(LIMITE_HORARIO_ENTREGA))
        self.assertFalse(_horario_entrega_permitido("17:31"))

    def test_normal_line_is_canonicalized_to_tradicional(self):
        self.assertEqual(_linha_canonica("normal"), "tradicional")
        self.assertEqual(_linha_canonica("tradicional"), "tradicional")

    def test_ai_order_blocks_delivery_after_cutoff(self):
        order = CakeOrderSchema(
            linha="tradicional",
            categoria="tradicional",
            descricao="Bolo tradicional de chocolate",
            data_entrega="10/03/2026",
            horario_retirada="18:00",
            modo_recebimento="entrega",
            pagamento={"forma": "PIX"},
        )

        result = create_cake_order("5511999999999", "Cliente Teste", 1, order)
        self.assertIn("17:30", result)


if __name__ == "__main__":
    unittest.main()
