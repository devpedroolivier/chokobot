import unittest

from app.ai.tools import get_cake_pricing


class AICakePricingTests(unittest.TestCase):
    def test_get_cake_pricing_returns_traditional_overview(self):
        result = get_cake_pricing("tradicional")

        self.assertIn("Precos canonicos da linha tradicional:", result)
        self.assertIn("B3 (ate 15 pessoas): R$120,00", result)
        self.assertIn("B4 (ate 30 pessoas): R$180,00", result)

    def test_get_cake_pricing_calculates_traditional_total_with_additional_and_kit(self):
        result = get_cake_pricing(
            category="tradicional",
            tamanho="B3",
            adicional="Cereja",
            kit_festou=True,
        )

        self.assertIn("Bolo tradicional B3 com adicional Cereja", result)
        self.assertIn("Valor unitario: R$170,00", result)
        self.assertIn("Kit Festou incluido: +R$35,00", result)

    def test_get_cake_pricing_returns_mesversario_price(self):
        result = get_cake_pricing(category="mesversario", tamanho="P6")

        self.assertIn("Bolo mesversario P6", result)
        self.assertIn("Valor unitario: R$165,00", result)

    def test_get_cake_pricing_matches_gourmet_and_torta_products(self):
        gourmet = get_cake_pricing(category="ingles", produto="red velvet")
        torta = get_cake_pricing(category="torta", produto="banoffee")

        self.assertIn("Gourmet ingles Red Velvet", gourmet)
        self.assertIn("Valor unitario: R$120,00", gourmet)
        self.assertIn("Torta Banoffee", torta)
        self.assertIn("Valor unitario: R$130,00", torta)

    def test_get_cake_pricing_requires_gourmet_subtype_when_ambiguous(self):
        result = get_cake_pricing(category="gourmet")

        self.assertIn("A linha gourmet tem dois formatos", result)
        self.assertIn("gourmet ingles", result.casefold())
        self.assertIn("redondo P6".casefold(), result.casefold())

    def test_get_cake_pricing_supports_caseirinho_alias_with_flavor_and_coverage(self):
        result = get_cake_pricing(category="caseirinho", produto="cenoura", cobertura="vulcao")

        self.assertIn("Bolo simples de cenoura com cobertura Vulcão", result)
        self.assertIn("Valor unitario: R$35,00", result)
        self.assertIn("Serve aproximadamente: 8 pessoas", result)


if __name__ == "__main__":
    unittest.main()
