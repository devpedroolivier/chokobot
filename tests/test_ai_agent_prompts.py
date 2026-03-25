import unittest

from app.ai.agents import CAFETERIA_PROMPT, CAKE_ORDER_PROMPT, KNOWLEDGE_PROMPT, SWEET_ORDER_PROMPT, TRIAGE_PROMPT


class AIAgentPromptsTests(unittest.TestCase):
    def test_triage_prompt_uses_1730_cutoff_for_same_day_orders(self):
        self.assertIn("DEPOIS das 17:30", TRIAGE_PROMPT)
        self.assertIn("ATÉ as 17:30", TRIAGE_PROMPT)
        self.assertNotIn("DEPOIS das 11:00", TRIAGE_PROMPT)

    def test_cake_order_prompt_uses_1730_cutoff_for_same_day_orders(self):
        self.assertIn('já passou das 17:30', CAKE_ORDER_PROMPT)
        self.assertNotIn('já passou das 11:00', CAKE_ORDER_PROMPT)

    def test_order_prompts_require_explicit_last_message_confirmation(self):
        self.assertIn("ULTIMA mensagem do cliente", CAKE_ORDER_PROMPT)
        self.assertIn('"pode fechar"', CAKE_ORDER_PROMPT)
        self.assertIn("ULTIMA mensagem do cliente", SWEET_ORDER_PROMPT)
        self.assertIn('"confirmo"', SWEET_ORDER_PROMPT)

    def test_prompts_cover_sunday_rule_and_ready_delivery_disambiguation(self):
        self.assertIn("Nao fazemos pedidos, retiradas ou encomendas para domingo.", TRIAGE_PROMPT)
        self.assertIn("caixinha de chocolate", TRIAGE_PROMPT)
        self.assertIn("bolo pronta entrega, Kit Festou, ovos pronta entrega ou cafeteria", CAFETERIA_PROMPT)
        self.assertIn("Nao fazemos pedidos, retiradas ou encomendas para domingo.", CAFETERIA_PROMPT)

    def test_prompts_differentiate_menu_from_specific_options(self):
        self.assertIn("Se o cliente pedir CARDAPIO", KNOWLEDGE_PROMPT)
        self.assertIn("use `lookup_catalog_items`", KNOWLEDGE_PROMPT)
        self.assertIn("use `get_cake_pricing`", KNOWLEDGE_PROMPT)
        self.assertIn("Se o cliente perguntar por um item especifico", CAFETERIA_PROMPT)
        self.assertIn("use `lookup_catalog_items`", CAFETERIA_PROMPT)

    def test_prompts_cover_cash_change_rule_and_croissant_prep_time(self):
        self.assertIn("troco so existe para Dinheiro", KNOWLEDGE_PROMPT)
        self.assertIn("troco so existe para Dinheiro", CAFETERIA_PROMPT)
        self.assertIn("tempo de preparo do croissant, informe 20 minutos", CAFETERIA_PROMPT)

    def test_cake_prompt_requires_canonical_pricing_tool(self):
        self.assertIn("chame `get_cake_pricing`", CAKE_ORDER_PROMPT)
        self.assertIn("NUNCA escreva preco de bolo de memoria", CAKE_ORDER_PROMPT)

    def test_cake_order_prompt_lists_valid_fillings_and_separates_categories(self):
        self.assertIn("Recheios validos: Beijinho, Brigadeiro, Brigadeiro de Nutella", CAKE_ORDER_PROMPT)
        self.assertIn("Adicionais validos: Morango, Ameixa, Nozes, Cereja, Abacaxi.", CAKE_ORDER_PROMPT)
        self.assertIn("NUNCA liste mousse como se fosse recheio.", CAKE_ORDER_PROMPT)
        self.assertIn('Se o cliente perguntar "quais recheios temos?", responda listando apenas recheios.', CAKE_ORDER_PROMPT)
        self.assertIn("Temos estes recheios:", CAKE_ORDER_PROMPT)
        self.assertIn("chame `get_cake_options`", CAKE_ORDER_PROMPT)
        self.assertIn("sem resumir, sem omitir itens e sem misturar categorias", CAKE_ORDER_PROMPT)



if __name__ == "__main__":
    unittest.main()
