import unittest

from app.ai.tools import get_cake_options


class AICakeOptionsTests(unittest.TestCase):
    def test_get_cake_options_returns_only_traditional_mousses(self):
        result = get_cake_options("tradicional", "mousse")

        self.assertEqual(
            result,
            "Temos estes mousses: Ninho, Trufa Branca, Chocolate e Trufa Preta.",
        )
        self.assertNotIn("Morango", result)
        self.assertNotIn("Brigadeiro", result)

    def test_get_cake_options_returns_mesversario_fillings(self):
        result = get_cake_options("mesversario", "recheio")

        self.assertIn("Temos estes recheios para mesversario:", result)
        self.assertIn("Brigadeiro com Ninho", result)
        self.assertIn("Doce de Leite com Ninho", result)


if __name__ == "__main__":
    unittest.main()
