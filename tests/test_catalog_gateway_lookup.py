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

    def test_lookup_catalog_items_returns_not_found_for_uncatalogued_item(self):
        result = self.gateway.lookup_catalog_items("saquinho pequeno", "cafeteria")

        self.assertIn("Nao encontrei", result)


if __name__ == "__main__":
    unittest.main()
