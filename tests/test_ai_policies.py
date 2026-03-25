import unittest

from app.ai.policies import (
    build_cafeteria_specificity_retry_instruction,
    cafeteria_order_needs_specificity,
    requests_easter_catalog,
    requests_easter_ready_delivery_handoff,
    response_conflicts_with_cafeteria_specificity,
)


class AIPoliciesTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
