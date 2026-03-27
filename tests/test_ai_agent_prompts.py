import unittest

from app.ai.agents import (
    CAFETERIA_PROMPT,
    CAKE_ORDER_PROMPT,
    GIFT_ORDER_PROMPT,
    KNOWLEDGE_PROMPT,
    SWEET_ORDER_PROMPT,
    TRIAGE_PROMPT,
)


class AIAgentPromptsTests(unittest.TestCase):
    def test_triage_prompt_uses_1100_cutoff_for_same_day_orders(self):
        self.assertIn("DEPOIS das 11:00", TRIAGE_PROMPT)
        self.assertIn("ATÉ as 11:00", TRIAGE_PROMPT)

    def test_cake_order_prompt_uses_1100_cutoff_for_same_day_orders(self):
        self.assertIn('já passou das 11:00', CAKE_ORDER_PROMPT)
        self.assertIn("MEMORIA DE DATA DA CONVERSA", CAKE_ORDER_PROMPT)
        self.assertIn("MEMORIA DE CORRECOES DA CONVERSA", CAKE_ORDER_PROMPT)

    def test_order_prompts_require_explicit_last_message_confirmation(self):
        self.assertIn("ÚLTIMA mensagem do cliente", CAKE_ORDER_PROMPT)
        self.assertIn('"pode fechar"', CAKE_ORDER_PROMPT)
        self.assertIn("ÚLTIMA mensagem", SWEET_ORDER_PROMPT)
        self.assertIn('"confirmo"', SWEET_ORDER_PROMPT)
        self.assertIn("MEMORIA DE CORRECOES DA CONVERSA", SWEET_ORDER_PROMPT)

    def test_prompts_cover_sunday_rule_and_ready_delivery_disambiguation(self):
        self.assertIn("Nao fazemos pedidos, retiradas ou encomendas para domingo.", TRIAGE_PROMPT)
        self.assertIn("domingo de Pascoa (05/04/2026)", TRIAGE_PROMPT)
        self.assertIn("GiftOrderAgent", TRIAGE_PROMPT)
        self.assertIn("bolo pronta entrega ou cafeteria", CAFETERIA_PROMPT)
        self.assertIn("OVO DE PÁSCOA PRONTA ENTREGA", CAFETERIA_PROMPT)
        self.assertIn("Nao fazemos pedidos, retiradas ou encomendas para domingo.", CAFETERIA_PROMPT)
        self.assertIn("domingo de Pascoa (05/04/2026)", CAFETERIA_PROMPT)

    def test_prompts_differentiate_menu_from_specific_options(self):
        self.assertIn("DIFERENCIE INTENÇÃO", KNOWLEDGE_PROMPT)
        self.assertIn("lookup_catalog_items", KNOWLEDGE_PROMPT)
        self.assertIn("get_cake_pricing", KNOWLEDGE_PROMPT)
        self.assertIn('"presentes"', KNOWLEDGE_PROMPT)
        self.assertIn("lookup_catalog_items", CAFETERIA_PROMPT)
        self.assertIn("Item específico, sabor, preço, opções → `lookup_catalog_items`", CAFETERIA_PROMPT)
        self.assertIn("Pedido e reserva podem ser feitos pelo WhatsApp", KNOWLEDGE_PROMPT)
        self.assertIn("Chave PIX oficial:", KNOWLEDGE_PROMPT)
        self.assertIn("Responda SOMENTE com o link oficial", KNOWLEDGE_PROMPT)

    def test_prompts_cover_cash_change_rule_and_croissant_prep_time(self):
        self.assertIn("Troco: somente para Dinheiro", KNOWLEDGE_PROMPT)
        self.assertIn("troco so existe para Dinheiro", CAFETERIA_PROMPT)
        self.assertIn("pergunte se o cliente precisa de troco", CAFETERIA_PROMPT)
        self.assertIn("Parcelamento: somente no Cartão", KNOWLEDGE_PROMPT)
        self.assertIn("Parcelamento so no Cartao", CAFETERIA_PROMPT)
        self.assertIn("Parcelamento so no Cartao", CAKE_ORDER_PROMPT)
        self.assertIn("tempo de preparo do croissant, informe 20 minutos", CAFETERIA_PROMPT)

    def test_cafeteria_prompt_declares_fixed_delivery_fee(self):
        self.assertIn("taxa de entrega fixa: R$5,00", CAFETERIA_PROMPT)

    def test_cake_prompt_requires_canonical_pricing_tool(self):
        self.assertIn("chame `get_cake_pricing`", CAKE_ORDER_PROMPT)
        self.assertIn("NUNCA escreva preço de bolo de memória", CAKE_ORDER_PROMPT)

    def test_cake_order_prompt_lists_valid_fillings_and_separates_categories(self):
        self.assertIn("Recheios válidos (lista completa): Beijinho, Brigadeiro, Brigadeiro de Nutella", CAKE_ORDER_PROMPT)
        self.assertIn("Adicionais: Morango, Ameixa, Nozes, Cereja, Abacaxi.", CAKE_ORDER_PROMPT)
        self.assertIn("MOUSSE NÃO É RECHEIO", CAKE_ORDER_PROMPT)
        self.assertIn("pedir lista de recheios", CAKE_ORDER_PROMPT)
        self.assertIn("Use `get_cake_options`", CAKE_ORDER_PROMPT)
        self.assertIn("Reproduza a lista retornada integralmente", CAKE_ORDER_PROMPT)

    def test_prompts_treat_caseiro_and_caseirinho_as_linea_simples_aliases(self):
        self.assertIn("bolo caseiro", TRIAGE_PROMPT)
        self.assertIn("caseirinho", TRIAGE_PROMPT)
        self.assertIn("bolo simples, bolo caseiro, caseirinho", CAKE_ORDER_PROMPT)
        self.assertIn("produto (Chocolate ou Cenoura)", CAKE_ORDER_PROMPT)
        self.assertIn("cobertura (Vulcão R$35 ou Simples R$25)", CAKE_ORDER_PROMPT)

    def test_cafeteria_prompt_limits_kit_festou_offer_to_bolo_context(self):
        self.assertIn("Só mencione ou ofereça Kit Festou quando o contexto incluir BOLO", CAFETERIA_PROMPT)
        self.assertIn("Não ofereça Kit Festou para café, croissant", CAFETERIA_PROMPT)

    def test_cafeteria_prompt_requires_specificity_before_ordering(self):
        self.assertIn("ESPECIFICAÇÃO MÍNIMA ANTES DE AVANÇAR", CAFETERIA_PROMPT)
        self.assertIn("Item exato + sabor/tipo/versão", CAFETERIA_PROMPT)
        self.assertIn('NÃO diga "vou anotar"', CAFETERIA_PROMPT)
        self.assertIn("use `create_cafeteria_order`", CAFETERIA_PROMPT)
        self.assertIn("MEMORIA DE DATA DA CONVERSA", CAFETERIA_PROMPT)
        self.assertIn("MEMORIA DE CORRECOES DA CONVERSA", CAFETERIA_PROMPT)
        self.assertIn("Choko Combo (Combo do Dia)", CAFETERIA_PROMPT)
        self.assertIn("R$23,99", CAFETERIA_PROMPT)
        self.assertIn("Suco natural ou Refri 220ml", CAFETERIA_PROMPT)

    def test_sprint4_prompt_rules_cover_product_first_routing_upsell_and_structured_confirmation(self):
        self.assertIn('NUNCA comece com a pergunta binaria "pronta entrega ou encomenda?"', TRIAGE_PROMPT)
        self.assertIn("oferta de upsell no maximo 1 vez por pedido", CAKE_ORDER_PROMPT.casefold())
        self.assertIn("Upsell opcional (uma vez por pedido)", SWEET_ORDER_PROMPT)
        self.assertIn("UPSELL CAFETERIA (UMA VEZ)", CAFETERIA_PROMPT)
        self.assertIn("Confirma seu pedido?", CAKE_ORDER_PROMPT)
        self.assertIn("💳 Pagamento: [PIX/dinheiro/cartao]", SWEET_ORDER_PROMPT)
        self.assertIn("💳 Pagamento: [PIX/dinheiro/cartao]", GIFT_ORDER_PROMPT)

    def test_gift_prompt_separates_regular_gifts_from_easter_and_uses_structured_tool(self):
        self.assertIn("cestas box, caixinha de chocolate", TRIAGE_PROMPT)
        self.assertIn("PÁSCOA (OVOS/TRIOS/TABLETES/MIMOS)", GIFT_ORDER_PROMPT)
        self.assertIn('get_menu` com category="presentes"', GIFT_ORDER_PROMPT)
        self.assertIn('lookup_catalog_items` com catalog="presentes"', GIFT_ORDER_PROMPT)
        self.assertIn("responda SOMENTE com https://pascoachoko.goomer.app", GIFT_ORDER_PROMPT)
        self.assertIn("create_gift_order", GIFT_ORDER_PROMPT)
        self.assertIn("caixinha de chocolate", TRIAGE_PROMPT)


if __name__ == "__main__":
    unittest.main()
