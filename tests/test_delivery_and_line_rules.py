import os
import unittest

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from unittest.mock import patch

from app.ai.tools import CakeOrderSchema, _normalizar_massa, _sanitize_escalation_reason, create_cake_order
from app.services.encomendas_utils import LIMITE_HORARIO_ENTREGA, _horario_entrega_permitido, _linha_canonica
from app.services.store_schedule import validate_service_schedule


class DeliveryAndLineRulesTests(unittest.TestCase):
    def test_massa_preta_synonyms_are_normalized_to_chocolate(self):
        self.assertEqual(_normalizar_massa("preta"), "Chocolate")
        self.assertEqual(_normalizar_massa("massa preta"), "Chocolate")
        self.assertEqual(_normalizar_massa("escura"), "Chocolate")

    def test_escalation_reason_is_enriched_when_too_generic(self):
        reason = _sanitize_escalation_reason("fora de contexto")
        self.assertIn("Escalacao para humano com contexto obrigatorio", reason)
        self.assertIn("fora de contexto", reason)

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

    def test_validate_service_schedule_blocks_sunday(self):
        self.assertIn("domingo", validate_service_schedule("29/03/2026", "10:00").lower())

    def test_validate_service_schedule_blocks_before_monday_opening(self):
        self.assertIn("segunda-feira", validate_service_schedule("30/03/2026", "10:00").lower())

    def test_create_cake_order_rejects_missing_required_fields_for_traditional(self):
        order = CakeOrderSchema(
            linha="tradicional",
            categoria="tradicional",
            descricao="Bolo tradicional",
            tamanho="B4",
            data_entrega="10/10/2030",
            horario_retirada="15:00",
            modo_recebimento="retirada",
            pagamento={"forma": "PIX"},
        )

        result = create_cake_order("5511999999999", "Cliente Teste", 1, order)
        self.assertIn("Erro de validacao", result)
        self.assertIn("Massa", result)
        self.assertIn("Recheio", result)

    def test_create_cake_order_rejects_delivery_without_address(self):
        order = CakeOrderSchema(
            linha="tradicional",
            categoria="tradicional",
            descricao="Bolo tradicional",
            tamanho="B4",
            massa="Chocolate",
            recheio="Brigadeiro",
            mousse="Ninho",
            data_entrega="10/10/2030",
            horario_retirada="15:00",
            modo_recebimento="entrega",
            pagamento={"forma": "PIX"},
        )

        result = create_cake_order("5511999999999", "Cliente Teste", 1, order)
        self.assertIn("Erro de validacao", result)
        self.assertIn("Endereco", result)

    def test_create_cake_order_rejects_zero_total(self):
        order = CakeOrderSchema(
            linha="tradicional",
            categoria="tradicional",
            descricao="Bolo tradicional",
            tamanho="B4",
            massa="Chocolate",
            recheio="Brigadeiro",
            mousse="Ninho",
            data_entrega="10/10/2030",
            horario_retirada="15:00",
            modo_recebimento="retirada",
            pagamento={"forma": "PIX"},
        )

        with patch("app.ai.tools._calcular_preco_pedido", return_value=(0.0, 0)):
            result = create_cake_order("5511999999999", "Cliente Teste", 1, order)
        self.assertIn("Valor total invalido", result)


if __name__ == "__main__":
    unittest.main()
