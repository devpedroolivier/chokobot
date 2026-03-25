import unittest

from app.ai.policies import requests_easter_catalog


class AIPoliciesTests(unittest.TestCase):
    def test_requests_easter_catalog_treats_generic_ovo_as_easter(self):
        self.assertTrue(requests_easter_catalog("Eu gostaria de encomendar um ovo"))
        self.assertTrue(requests_easter_catalog("Quero encomendar ovos de Páscoa"))
        self.assertTrue(requests_easter_catalog("Tem ovo de Páscoa disponível?"))

    def test_requests_easter_catalog_ignores_ready_delivery_egg_context(self):
        self.assertFalse(requests_easter_catalog("Oi tem ovo pronta entrega?"))

    def test_requests_easter_catalog_ignores_savory_egg_context(self):
        self.assertFalse(requests_easter_catalog("Aquele misto que ela gosta sem orégano no ovo ok"))
        self.assertFalse(requests_easter_catalog("Quero um lanche com ovo"))
        self.assertFalse(requests_easter_catalog("Tem croissant com ovo?"))

    def test_requests_easter_catalog_does_not_short_circuit_specific_item_queries(self):
        self.assertFalse(requests_easter_catalog("Tem ovo de paçoca?"))
        self.assertFalse(requests_easter_catalog("Quais sabores do ovo trufado 400g?"))
        self.assertFalse(requests_easter_catalog("Tem trio 2?"))


if __name__ == "__main__":
    unittest.main()
