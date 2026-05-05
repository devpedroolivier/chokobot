"""Regressão: prompt da cafeteria deve fixar R$5,00 e proibir R$10,00.

Origem: telefone 5516991326320 — 27/03/2026 — IA usou R$10 para cafeteria
e o cliente teve que corrigir 2x (Mais a taxa é $5 / Então não seria $26?).
"""
import unittest

from app.ai.agents import _build_module_state


class TaxaCafeteriaPromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = _build_module_state()

    def test_cafeteria_prompt_fixa_taxa_cinco(self):
        prompt = self.state["CAFETERIA_PROMPT"]
        self.assertIn("R$5,00", prompt)
        self.assertIn("TAXA DE ENTREGA NESTE FLUXO (cafeteria)", prompt)

    def test_cafeteria_prompt_proibe_dez(self):
        prompt = self.state["CAFETERIA_PROMPT"]
        idx_cinco = prompt.find("R$5,00")
        idx_dez = prompt.find("NUNCA use R$10,00 neste fluxo")
        self.assertNotEqual(idx_dez, -1, "regra absoluta de proibição precisa estar presente")
        self.assertLess(idx_cinco, prompt.find("DELIVERY_RULE_LINE") if "DELIVERY_RULE_LINE" in prompt else len(prompt))

    def test_cake_prompt_fixa_taxa_dez(self):
        prompt = self.state["CAKE_ORDER_PROMPT"]
        self.assertIn("TAXA DE ENTREGA NESTE FLUXO (bolos/encomendas/presentes)", prompt)
        self.assertIn("R$10,00", prompt)

    def test_gift_prompt_fixa_taxa_dez(self):
        prompt = self.state["GIFT_ORDER_PROMPT"]
        self.assertIn("TAXA DE ENTREGA NESTE FLUXO (bolos/encomendas/presentes)", prompt)
        self.assertIn("R$10,00", prompt)

    def test_sweet_prompt_fixa_taxa_dez(self):
        prompt = self.state["SWEET_ORDER_PROMPT"]
        self.assertIn("TAXA DE ENTREGA NESTE FLUXO (bolos/encomendas/presentes)", prompt)


if __name__ == "__main__":
    unittest.main()
