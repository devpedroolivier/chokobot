import os
import unittest

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.ai import tools as ai_tools
from app.utils.mensagens import formatar_mensagem_saida


class MessageFormattingTests(unittest.TestCase):
    def test_formatar_mensagem_saida_converte_headings_em_icones(self):
        mensagem = (
            "### 1. Bolos Pronta Entrega\n"
            "- B3\n"
            "### Kit Festou\n"
            "- Opcional\n"
            "#### Ingles (serve cerca de 10 pessoas)\n"
            "- Belga\n"
        )

        formatada = formatar_mensagem_saida(mensagem)

        self.assertNotIn("###", formatada)
        self.assertIn("🎂 Bolos Pronta Entrega", formatada)
        self.assertIn("🎉 Kit Festou", formatada)
        self.assertIn("🍰 Ingles (serve cerca de 10 pessoas)", formatada)

    def test_get_menu_pronta_entrega_nao_lista_doces_avulsos(self):
        menu = ai_tools.get_menu("pronta_entrega")

        self.assertIn("🎂 Bolos Pronta Entrega", menu)
        self.assertIn("🎉 Kit Festou opcional", menu)
        self.assertIn("☕ Cafeteria e Vitrine", menu)
        self.assertNotIn("DOCES AVULSOS", menu)
        self.assertNotIn("doceschoko", menu)


if __name__ == "__main__":
    unittest.main()
