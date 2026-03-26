import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ai.policies import (
    caseirinho_clarification_message,
    build_cafeteria_specificity_retry_instruction,
    cafeteria_order_needs_specificity,
    requests_cake_order_topic,
    requests_easter_catalog,
    requests_easter_gift_topic,
    requests_easter_ready_delivery_handoff,
    requests_post_purchase_topic,
    requests_regular_gift_topic,
    response_conflicts_with_cafeteria_specificity,
    should_force_basic_context_switch,
    should_force_gift_context_handoff,
    should_force_same_day_cafeteria_handoff,
)


class AIPoliciesTests(unittest.TestCase):
    def test_caseirinho_clarification_message_requests_missing_fields(self):
        self.assertIn(
            "sabor",
            (caseirinho_clarification_message("quero caseirinho") or "").lower(),
        )
        self.assertIn(
            "cobertura",
            (caseirinho_clarification_message("quero caseirinho de cenoura") or "").lower(),
        )
        self.assertIn(
            "chocolate ou cenoura",
            (caseirinho_clarification_message("quero caseirinho cobertura vulcao") or "").lower(),
        )
        self.assertIsNone(caseirinho_clarification_message("quero caseirinho de cenoura com cobertura vulcao"))

    def test_requests_easter_catalog_treats_generic_ovo_as_easter(self):
        self.assertTrue(requests_easter_catalog("Eu gostaria de encomendar um ovo"))
        self.assertTrue(requests_easter_catalog("Quero encomendar ovos de Páscoa"))
        self.assertTrue(requests_easter_catalog("Tem ovo de Páscoa disponível?"))

    def test_requests_easter_catalog_ignores_ready_delivery_egg_context(self):
        self.assertFalse(requests_easter_catalog("Oi tem ovo pronta entrega?"))
        self.assertTrue(requests_easter_ready_delivery_handoff("Oi tem ovo pronta entrega?"))
        self.assertTrue(requests_easter_ready_delivery_handoff("Quero pronta entrega de ovo"))
        self.assertFalse(requests_easter_ready_delivery_handoff("Quero ver o cardapio de pascoa"))

    def test_requests_easter_catalog_ignores_savory_egg_context(self):
        self.assertFalse(requests_easter_catalog("Aquele misto que ela gosta sem orégano no ovo ok"))
        self.assertFalse(requests_easter_catalog("Quero um lanche com ovo"))
        self.assertFalse(requests_easter_catalog("Tem croissant com ovo?"))
        self.assertFalse(requests_easter_ready_delivery_handoff("Tem croissant com ovo?"))

    def test_requests_easter_catalog_does_not_short_circuit_specific_item_queries(self):
        self.assertFalse(requests_easter_catalog("Tem ovo de paçoca?"))
        self.assertFalse(requests_easter_catalog("Quais sabores do ovo trufado 400g?"))
        self.assertFalse(requests_easter_catalog("Tem trio 2?"))

    def test_cafeteria_order_specificity_detects_generic_ordering(self):
        self.assertTrue(cafeteria_order_needs_specificity("Queria croissant"))
        self.assertTrue(cafeteria_order_needs_specificity("Quero coca tbm"))
        self.assertTrue(cafeteria_order_needs_specificity("Me vê uma fatia"))

    def test_cafeteria_order_specificity_ignores_specific_or_information_requests(self):
        self.assertFalse(cafeteria_order_needs_specificity("Qual valor do croissant de chocolate?"))
        self.assertFalse(cafeteria_order_needs_specificity("1 croissant frango 1 croissant chocolate 2 coca lata"))

    def test_cafeteria_specificity_conflict_blocks_premature_reply(self):
        self.assertTrue(
            response_conflicts_with_cafeteria_specificity(
                "Temos croissants na cafeteria. Você gostaria de pedir um croissant agora?",
                user_text="Queria croissant",
                current_agent="CafeteriaAgent",
            )
        )
        self.assertFalse(
            response_conflicts_with_cafeteria_specificity(
                "Temos croissant por R$14,50. Qual sabor você quer e quantos croissants deseja?",
                user_text="Queria croissant",
                current_agent="CafeteriaAgent",
            )
        )
        self.assertIn(
            "cliente ainda nao especificou o suficiente",
            build_cafeteria_specificity_retry_instruction("Queria croissant"),
        )

    def test_gift_topic_detection_separates_regular_catalog_from_easter(self):
        self.assertTrue(requests_regular_gift_topic("Vocês têm cesta box e flores?"))
        self.assertTrue(requests_regular_gift_topic("Quero ver presentes"))
        self.assertFalse(requests_regular_gift_topic("Quero ver presentes de Páscoa"))
        self.assertTrue(requests_easter_gift_topic("Quero ver mimos de Páscoa"))
        self.assertFalse(requests_easter_gift_topic("Quero ver flores"))

    def test_gift_context_handoff_switches_agent_when_customer_changes_topic(self):
        self.assertEqual(
            should_force_gift_context_handoff({"current_agent": "CakeOrderAgent"}, "Vocês têm presentes?"),
            "GiftOrderAgent",
        )
        self.assertEqual(
            should_force_gift_context_handoff({"current_agent": "GiftOrderAgent"}, "Quero ver presentes de Páscoa"),
            "KnowledgeAgent",
        )

    def test_requests_post_purchase_topic_detects_each_flow(self):
        self.assertEqual(requests_post_purchase_topic("Qual o status do meu pedido?"), "status")
        self.assertEqual(requests_post_purchase_topic("Confirma o PIX do pedido?"), "pix")
        self.assertEqual(requests_post_purchase_topic("Quero cancelar a encomenda do sábado"), "cancel")
        self.assertEqual(requests_post_purchase_topic("Preciso da nota fiscal do bolo"), "invoice")

    def test_basic_context_switch_routes_between_supported_topics(self):
        self.assertEqual(
            should_force_basic_context_switch(
                {"current_agent": "CakeOrderAgent"},
                "Quero 50 brigadeiros para sábado",
            ),
            "SweetOrderAgent",
        )
        self.assertEqual(
            should_force_basic_context_switch(
                {"current_agent": "SweetOrderAgent"},
                "Quero um bolo B4 para sábado",
            ),
            "CakeOrderAgent",
        )
        self.assertEqual(
            should_force_basic_context_switch(
                {"current_agent": "KnowledgeAgent"},
                "Vocês têm cestas box?",
            ),
            "GiftOrderAgent",
        )

    def test_requests_cake_order_topic_ignores_cafeteria_and_easter_cases(self):
        self.assertTrue(requests_cake_order_topic("Quero encomendar um bolo B4 para sábado"))
        self.assertFalse(requests_cake_order_topic("Quero 50 brigadeiros para sábado"))
        self.assertFalse(requests_cake_order_topic("Quero um cappuccino"))
        self.assertFalse(requests_cake_order_topic("Quero ver o cardápio de Páscoa"))

    def test_same_day_cafeteria_handoff_applies_to_supported_agents_after_cutoff(self):
        now = datetime(2026, 3, 18, 11, 5, tzinfo=ZoneInfo("America/Sao_Paulo"))
        self.assertTrue(
            should_force_same_day_cafeteria_handoff(
                {"current_agent": "SweetOrderAgent"},
                "Quero um bolo para hoje",
                now,
            )
        )
        self.assertFalse(
            should_force_same_day_cafeteria_handoff(
                {"current_agent": "CafeteriaAgent"},
                "Quero um bolo para hoje",
                now,
            )
        )


if __name__ == "__main__":
    unittest.main()
