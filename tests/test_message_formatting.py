import os
import unittest

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.ai import tools as ai_tools
from app.ai.agents import CAFETERIA_PROMPT, CAKE_ORDER_PROMPT, KNOWLEDGE_PROMPT, SWEET_ORDER_PROMPT, TRIAGE_PROMPT
from app.utils.mensagens import formatar_mensagem_saida
from app.welcome_message import BOT_REACTIVATED_MESSAGE, HUMAN_HANDOFF_MESSAGE, VOICE_GUIDELINES, WELCOME_MESSAGE


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

    def test_triage_prompt_reutiliza_mensagem_de_boas_vindas(self):
        self.assertIn(WELCOME_MESSAGE, TRIAGE_PROMPT)
        self.assertIn("Me conta o que você está procurando", WELCOME_MESSAGE)

    def test_prompts_reutilizam_o_tom_da_trufinha(self):
        self.assertIn(VOICE_GUIDELINES.strip(), TRIAGE_PROMPT)
        self.assertIn(VOICE_GUIDELINES.strip(), CAKE_ORDER_PROMPT)
        self.assertIn(VOICE_GUIDELINES.strip(), SWEET_ORDER_PROMPT)
        self.assertIn(VOICE_GUIDELINES.strip(), KNOWLEDGE_PROMPT)
        self.assertIn(VOICE_GUIDELINES.strip(), CAFETERIA_PROMPT)

    def test_mensagens_fixas_seguem_nova_voz(self):
        self.assertIn("encaminhar para uma atendente", HUMAN_HANDOFF_MESSAGE)
        self.assertIn("Trufinha voltou por aqui", BOT_REACTIVATED_MESSAGE)


if __name__ == "__main__":
    unittest.main()
