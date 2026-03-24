import unittest

from app.ai.policies import requests_easter_catalog


class AIPoliciesTests(unittest.TestCase):
    def test_requests_easter_catalog_treats_generic_ovo_as_easter(self):
        self.assertTrue(requests_easter_catalog("Eu gostaria de encomendar um ovo"))
        self.assertTrue(requests_easter_catalog("Quero encomendar um trio de ovos"))
        self.assertTrue(requests_easter_catalog("Oi tem ovo pronta entrega?"))
        self.assertTrue(requests_easter_catalog("Tem ovo de paçoca?"))

    def test_requests_easter_catalog_ignores_savory_egg_context(self):
        self.assertFalse(requests_easter_catalog("Aquele misto que ela gosta sem orégano no ovo ok"))
        self.assertFalse(requests_easter_catalog("Quero um lanche com ovo"))
        self.assertFalse(requests_easter_catalog("Tem croissant com ovo?"))


if __name__ == "__main__":
    unittest.main()
