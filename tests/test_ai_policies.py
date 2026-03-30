import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.ai.policies import (
    build_discount_guard_retry_instruction,
    build_cafeteria_total_guard_retry_instruction,
    build_truffle_availability_retry_instruction,
    caseirinho_clarification_message,
    build_cafeteria_specificity_retry_instruction,
    cafeteria_order_needs_specificity,
    is_generic_greeting,
    message_has_easter_context,
    requests_catalog_photo,
    requests_cake_order_topic,
    requests_easter_catalog,
    requests_easter_date_info,
    requests_easter_gift_topic,
    requests_easter_ready_delivery_handoff,
    requests_pix_key_info,
    requests_post_purchase_topic,
    requests_delivery_fee_info,
    requests_regular_gift_topic,
    requests_sweet_order_topic,
    response_conflicts_with_cafeteria_specificity,
    response_conflicts_with_cafeteria_total_claim,
    response_conflicts_with_discount_offer,
    response_conflicts_with_truffle_availability_denial,
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

    def test_requests_easter_catalog_only_for_link_or_menu_queries(self):
        self.assertTrue(requests_easter_catalog("Quero ver o cardápio de ovos de Páscoa"))
        self.assertTrue(requests_easter_catalog("Manda o link da Páscoa"))
        self.assertFalse(requests_easter_catalog("Eu gostaria de encomendar um ovo"))
        self.assertFalse(requests_easter_catalog("Tem ovo de Páscoa disponível?"))

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
        self.assertFalse(message_has_easter_context("Tem croissant com ovo?"))
        self.assertFalse(message_has_easter_context("Entao vou retirar as 17:30 e pagar no cartao sem cereja"))

    def test_requests_easter_catalog_does_not_short_circuit_specific_item_queries(self):
        self.assertFalse(requests_easter_catalog("Tem ovo de paçoca?"))
        self.assertFalse(requests_easter_catalog("Quais sabores do ovo trufado 400g?"))
        self.assertFalse(requests_easter_catalog("Tem trio 2?"))

    def test_cafeteria_order_specificity_detects_generic_ordering(self):
        self.assertTrue(cafeteria_order_needs_specificity("Queria croissant"))
        self.assertTrue(cafeteria_order_needs_specificity("Quero coca tbm"))
        self.assertTrue(cafeteria_order_needs_specificity("Me vê uma fatia"))
        self.assertTrue(cafeteria_order_needs_specificity("Quero 1 combo croissant de frango"))

    def test_cafeteria_order_specificity_ignores_specific_or_information_requests(self):
        self.assertFalse(cafeteria_order_needs_specificity("Qual valor do croissant de chocolate?"))
        self.assertFalse(cafeteria_order_needs_specificity("1 croissant frango 1 croissant chocolate 2 coca lata"))
        self.assertFalse(cafeteria_order_needs_specificity("2 combos croissant peito de peru com coca normal"))

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

    def test_cafeteria_total_claim_conflict_requires_tool_based_retry(self):
        self.assertTrue(
            response_conflicts_with_cafeteria_total_claim(
                (
                    "Aqui está o resumo do seu pedido:\n"
                    "1 Croissant de Quatro Queijos\n"
                    "1 Croissant de Chocolate\n"
                    "1 Coca Lata\n"
                    "Total: R$ 22,00"
                ),
                current_agent="CafeteriaAgent",
            )
        )
        self.assertFalse(
            response_conflicts_with_cafeteria_total_claim(
                (
                    "Resumo final do pedido (rascunho)\n"
                    "Itens:\n- 1x Croissant (Chocolate): R$14,50\n"
                    "Subtotal: R$14,50\nValor: R$14,50"
                ),
                current_agent="CafeteriaAgent",
            )
        )
        self.assertFalse(
            response_conflicts_with_cafeteria_total_claim(
                "Total: R$ 22,00",
                current_agent="SweetOrderAgent",
            )
        )
        self.assertIn(
            "nao pode calcular subtotal/total de memoria",
            build_cafeteria_total_guard_retry_instruction("Quero croissant e coca").lower(),
        )

    def test_gift_topic_detection_separates_regular_catalog_from_easter(self):
        self.assertTrue(requests_regular_gift_topic("Vocês têm cesta box e flores?"))
        self.assertTrue(requests_regular_gift_topic("Quero ver presentes"))
        self.assertTrue(requests_regular_gift_topic("Tem mimo para presente?"))
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
            None,
        )

    def test_requests_post_purchase_topic_detects_each_flow(self):
        self.assertEqual(requests_post_purchase_topic("Qual o status do meu pedido?"), "status")
        self.assertEqual(requests_post_purchase_topic("Confirma o PIX do pedido?"), "pix")
        self.assertEqual(requests_post_purchase_topic("Quero cancelar a encomenda do sábado"), "cancel")
        self.assertEqual(requests_post_purchase_topic("Preciso da nota fiscal do bolo"), "invoice")

    def test_requests_catalog_photo_and_easter_date_info(self):
        self.assertTrue(requests_catalog_photo("Tem foto?"))
        self.assertTrue(requests_catalog_photo("Me manda uma foto"))
        self.assertTrue(requests_catalog_photo("Posso ver como fica?"))
        self.assertFalse(requests_catalog_photo("Quero 10 brigadeiros"))

        self.assertTrue(requests_easter_date_info("Quando é a Páscoa?"))
        self.assertTrue(requests_easter_date_info("Qual a data da páscoa"))
        self.assertFalse(requests_easter_date_info("Quero ovos de páscoa"))

    def test_requests_pix_key_info_detects_key_request_without_post_purchase_confirmation(self):
        self.assertTrue(requests_pix_key_info("Me passa a chave PIX"))
        self.assertTrue(requests_pix_key_info("Qual o pix de vocês?"))
        self.assertTrue(requests_pix_key_info("PIX CNPJ, por favor"))
        self.assertFalse(requests_pix_key_info("Confirma o PIX do pedido?"))

    def test_requests_delivery_fee_info_detects_taxa_queries(self):
        self.assertTrue(requests_delivery_fee_info("Qual a taxa de entrega?"))
        self.assertTrue(requests_delivery_fee_info("Quanto fica o frete?"))
        self.assertTrue(requests_delivery_fee_info("Delivery tem taxa?"))
        self.assertFalse(requests_delivery_fee_info("Quero retirar na loja"))

    def test_is_generic_greeting_detects_only_short_salutations(self):
        self.assertTrue(is_generic_greeting("oi"))
        self.assertTrue(is_generic_greeting("olá"))
        self.assertTrue(is_generic_greeting("boa tarde"))
        self.assertFalse(is_generic_greeting("oi quero um bolo"))
        self.assertFalse(is_generic_greeting("quero cardápio"))

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
        self.assertEqual(
            should_force_basic_context_switch(
                {"current_agent": "TriageAgent"},
                "Quero um ovo de páscoa",
            ),
            None,
        )
        self.assertEqual(
            should_force_basic_context_switch(
                {"current_agent": "TriageAgent"},
                "Tem ovo trufado?",
            ),
            None,
        )
        self.assertEqual(
            should_force_basic_context_switch(
                {"current_agent": "TriageAgent"},
                "Quero brigadeiros",
            ),
            "SweetOrderAgent",
        )
        self.assertEqual(
            should_force_basic_context_switch(
                {"current_agent": "TriageAgent"},
                "Quanto custa bombom?",
            ),
            "SweetOrderAgent",
        )
        self.assertEqual(
            should_force_basic_context_switch(
                {"current_agent": "TriageAgent"},
                "Vcs trabalham com trufas?",
            ),
            "SweetOrderAgent",
        )

    def test_requests_sweet_order_topic_detects_truffles(self):
        self.assertTrue(requests_sweet_order_topic("Trufas"))
        self.assertTrue(requests_sweet_order_topic("Vcs trabalham com trufas tradicionais?"))
        self.assertTrue(requests_sweet_order_topic("Quero 20 trufas para sábado"))

    def test_discount_guard_blocks_offering_and_allows_denial(self):
        self.assertTrue(response_conflicts_with_discount_offer("Para esse pedido, podemos oferecer um desconto especial de 10%."))
        self.assertTrue(response_conflicts_with_discount_offer("Total com desconto: R$162,00."))
        self.assertFalse(response_conflicts_with_discount_offer("No bot nao consigo aplicar desconto; somente atendente humano pode avaliar."))
        self.assertIn(
            "nao pode oferecer, aplicar, prometer ou calcular desconto",
            build_discount_guard_retry_instruction("Tem como fazer desconto?").lower(),
        )

    def test_truffle_guard_blocks_catalog_denial_without_check(self):
        self.assertTrue(
            response_conflicts_with_truffle_availability_denial(
                "Nao temos trufas no cardapio atualmente.",
                user_text="Trufas tradicionais",
            )
        )
        self.assertFalse(
            response_conflicts_with_truffle_availability_denial(
                "Temos trufas sim! Posso te passar os sabores e valores.",
                user_text="Trufas tradicionais",
            )
        )
        self.assertFalse(
            response_conflicts_with_truffle_availability_denial(
                "Nao temos trufas no cardapio atualmente.",
                user_text="Quero bolo B4",
            )
        )
        self.assertIn(
            "nao negue trufas sem verificar catalogo canonico",
            build_truffle_availability_retry_instruction("Trufas tradicionais").lower(),
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
