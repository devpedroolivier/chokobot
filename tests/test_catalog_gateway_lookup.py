import unittest

from app.infrastructure.gateways.local_catalog_gateway import LocalCatalogGateway


class CatalogGatewayLookupTests(unittest.TestCase):
    def setUp(self):
        self.gateway = LocalCatalogGateway()

    def test_lookup_catalog_items_matches_cafeteria_item_with_typo_and_option(self):
        result = self.gateway.lookup_catalog_items("croasant de chocolate", "cafeteria")

        self.assertIn("Croissant", result)
        self.assertIn("Chocolate", result)

    def test_lookup_catalog_items_matches_easter_variant_and_weight(self):
        result = self.gateway.lookup_catalog_items("trufado 400g", "pascoa")

        self.assertIn("Ovos Trufados", result)
        self.assertIn("400g", result)
        self.assertIn("Trufado Brigadeiro", result)

    def test_lookup_catalog_items_matches_caseirinho_alias_for_linea_simples(self):
        result = self.gateway.lookup_catalog_items("caseirinho de cenoura vulcao", "auto")

        self.assertIn("Linha Simples / Bolo Caseiro / Caseirinho", result)
        self.assertIn("Sabores: Cenoura", result)
        self.assertIn("Coberturas: Vulcão R$35,00", result)

    def test_lookup_catalog_items_matches_petit_alias_to_vulcaozinho_de_cenoura(self):
        result = self.gateway.lookup_catalog_items("bolo petit cenoura", "cafeteria")

        self.assertIn("Vulcaozinho de Cenoura com Calda de Chocolate", result)
        self.assertIn("R$16,50", result)

    def test_lookup_catalog_items_separates_regular_gifts_from_easter(self):
        result = self.gateway.lookup_catalog_items("box m cafe", "presentes")

        self.assertIn("BOX M CAFÉ", result)
        self.assertIn("Presentes Especiais", result)
        self.assertIn("R$179,90", result)

    def test_lookup_catalog_items_structures_caixinha_and_flores_in_regular_catalog(self):
        caixinha = self.gateway.lookup_catalog_items("caixinha de chocolate", "presentes")
        flores = self.gateway.lookup_catalog_items("flores", "presentes")

        self.assertIn("Caixinha de Chocolate", caixinha)
        self.assertIn("bit.ly/presenteschoko", caixinha)
        self.assertIn("Flores", flores)
        self.assertIn("modelos e montagem", flores.casefold())

    def test_lookup_catalog_items_returns_not_found_for_uncatalogued_item(self):
        result = self.gateway.lookup_catalog_items("saquinho pequeno", "cafeteria")

        self.assertIn("Nao encontrei", result)


if __name__ == "__main__":
    unittest.main()
