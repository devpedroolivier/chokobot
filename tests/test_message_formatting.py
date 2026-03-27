import os
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.ai import tools as ai_tools
from app.ai.tools import CakeOrderSchema
from app.ai.agents import CAFETERIA_PROMPT, CAKE_ORDER_PROMPT, KNOWLEDGE_PROMPT, SWEET_ORDER_PROMPT, TRIAGE_PROMPT
from app.utils.mensagens import _sanitize_internal_agent_payload, formatar_mensagem_saida
from app.welcome_message import (
    BOT_REACTIVATED_MESSAGE,
    EASTER_CATALOG_MESSAGE,
    HUMAN_HANDOFF_MESSAGE,
    VOICE_GUIDELINES,
    WELCOME_MESSAGE,
)


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
        self.assertIn("🎉 Kit Festou", menu)
        self.assertIn("🥚 Ovos Pronta Entrega", menu)
        self.assertIn("☕ Cafeteria e Vitrine", menu)
        self.assertNotIn("DOCES AVULSOS", menu)
        self.assertNotIn("doceschoko", menu)

    def test_get_menu_cafeteria_expoe_cardapio_estruturado(self):
        menu = ai_tools.get_menu("cafeteria")

        self.assertIn("☕ Cardápio da Cafeteria", menu)
        self.assertIn("Salgados e Lanches", menu)
        self.assertIn("Croissant", menu)
        self.assertIn("Combos Promocionais", menu)
        self.assertIn("Combo Relampago", menu)

    def test_lookup_catalog_items_expoe_opcoes_de_item_especifico(self):
        result = ai_tools.lookup_catalog_items("croasant de chocolate", "cafeteria")

        self.assertIn("Croissant", result)
        self.assertIn("Chocolate", result)
        self.assertIn("20 minutos", result)

    def test_save_cake_order_draft_process_formata_resumo_final_claro(self):
        with patch("app.ai.tools._sync_ai_process", return_value=None):
            with patch.object(ai_tools, "_PIX_KEY", "Pix 16847366000130"):
                result = ai_tools.save_cake_order_draft_process(
                    telefone="5511999999999",
                    nome_cliente="Ana",
                    cliente_id=7,
                    order_details=CakeOrderSchema(
                        linha="tradicional",
                        categoria="tradicional",
                        tamanho="B4",
                        massa="Chocolate",
                        recheio="Doce de Leite",
                        mousse="Trufa Preta",
                        adicional="Nozes",
                        descricao="Bolo B4 de chocolate",
                        data_entrega="28/03/2026",
                        horario_retirada="17:00",
                        modo_recebimento="retirada",
                        pagamento={"forma": "PIX"},
                    ),
                )

        self.assertIn("Resumo final do pedido", result)
        self.assertIn("Bolo B4 de chocolate", result)
        self.assertIn("Recheio: Doce de Leite com Trufa Preta e adicional de nozes", result)
        self.assertIn("📅 Data: 28/3 Sabado | Horario: 17h", result)
        self.assertIn("🚗 Retirada na loja", result)
        self.assertIn("Valor: R$190,00", result)
        self.assertIn("💳 Pagamento: PIX | chave Pix 16847366000130", result)
        self.assertIn("Ainda nao foi salvo como pedido confirmado no sistema.", result)
        self.assertIn('ex.: "sim", "ok", "ta bom", "certo" ou "confirmado"', result)

    def test_save_cafeteria_order_draft_process_formata_resumo_com_subtotal(self):
        with patch("app.ai.tools.now_in_bot_timezone", return_value=datetime(2026, 3, 25, 14, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))):
            with patch("app.ai.tools._sync_ai_process", return_value=None):
                result = ai_tools.save_cafeteria_order_draft_process(
                    telefone="5511999999999",
                    nome_cliente="Ana",
                    cliente_id=7,
                    order_details=ai_tools.CafeteriaOrderSchema(
                        itens=[
                            {"nome": "Croissant", "variante": "Chocolate", "quantidade": 2},
                            {"nome": "Coca Cola KS", "quantidade": 1},
                        ],
                        horario_retirada="17:00",
                        modo_recebimento="retirada",
                        pagamento={"forma": "PIX"},
                    ),
                )

        self.assertIn("Pedido cafeteria", result)
        self.assertIn("- 2x Croissant (Chocolate): R$29,00", result)
        self.assertIn("- 1x Coca Cola KS: R$5,50", result)
        self.assertIn("📅 Data: 25/3 Quarta | Horario: 17h", result)
        self.assertIn("🚗 Retirada na loja", result)
        self.assertIn("Subtotal: R$34,50", result)
        self.assertIn("Valor: R$34,50", result)
        self.assertIn('ex.: "sim", "ok", "ta bom", "certo" ou "confirmado"', result)

    def test_triage_prompt_reutiliza_mensagem_de_boas_vindas(self):
        self.assertIn(WELCOME_MESSAGE, TRIAGE_PROMPT)
        self.assertIn("Me conta o que você está procurando", WELCOME_MESSAGE)
        self.assertIn("Páscoa Inesquecível", WELCOME_MESSAGE)
        self.assertIn("bolos e ovos", WELCOME_MESSAGE)
        self.assertNotIn("Kit Festou e ovos", WELCOME_MESSAGE)
        self.assertNotIn("combos", WELCOME_MESSAGE.casefold())
        self.assertIn("caixinha de chocolate e flores", WELCOME_MESSAGE)

    def test_mensagem_de_pascoa_expoe_link_direto(self):
        self.assertIn("pedido de Páscoa", EASTER_CATALOG_MESSAGE)
        self.assertIn("https://pascoachoko.goomer.app", EASTER_CATALOG_MESSAGE)

    def test_prompts_reutilizam_o_tom_da_trufinha(self):
        self.assertIn(VOICE_GUIDELINES.strip(), TRIAGE_PROMPT)
        self.assertIn(VOICE_GUIDELINES.strip(), CAKE_ORDER_PROMPT)
        self.assertIn(VOICE_GUIDELINES.strip(), SWEET_ORDER_PROMPT)
        self.assertIn(VOICE_GUIDELINES.strip(), KNOWLEDGE_PROMPT)
        self.assertIn(VOICE_GUIDELINES.strip(), CAFETERIA_PROMPT)

    def test_mensagens_fixas_seguem_nova_voz(self):
        self.assertIn("transferindo você", HUMAN_HANDOFF_MESSAGE)
        self.assertIn("atendentes humanos", HUMAN_HANDOFF_MESSAGE)
        self.assertIn("Trufinha voltou por aqui", BOT_REACTIVATED_MESSAGE)

    def test_sanitiza_payload_interno_de_transferencia(self):
        sanitized, removed = _sanitize_internal_agent_payload(
            'Perfeito! {"agent_name":"CakeOrderAgent"}\nMe diga o tamanho do bolo.'
        )

        self.assertTrue(removed)
        self.assertNotIn("agent_name", sanitized)
        self.assertIn("Me diga o tamanho do bolo.", sanitized)


if __name__ == "__main__":
    unittest.main()
