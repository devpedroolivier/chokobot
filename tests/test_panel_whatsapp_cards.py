import os
import unittest
from datetime import datetime

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.application.use_cases.panel_dashboard import build_whatsapp_cards
from app.domain.repositories.customer_process_repository import CustomerProcessRecord
from app.domain.repositories.customer_repository import CustomerRecord
from app.services.estados import (
    ai_sessions,
    append_conversation_message,
    conversation_threads,
    estados_atendimento,
    estados_cafeteria,
    estados_cestas_box,
    estados_encomenda,
    estados_entrega,
    recent_messages,
)


class PanelWhatsAppCardsTests(unittest.TestCase):
    def setUp(self):
        for state_map in (
            ai_sessions,
            estados_atendimento,
            estados_encomenda,
            estados_cafeteria,
            estados_entrega,
            estados_cestas_box,
            conversation_threads,
            recent_messages,
        ):
            state_map.clear()

    def test_build_whatsapp_cards_prefers_customer_processes_over_runtime(self):
        telefone = "5511999999999"
        estados_cafeteria[telefone] = {"etapa": "pedido"}

        class _ProcessRepository:
            def list_active_processes(self):
                return [
                    CustomerProcessRecord(
                        id=1,
                        phone=telefone,
                        customer_id=7,
                        process_type="human_handoff",
                        stage="handoff_humano",
                        status="active",
                        source="human_handoff",
                        draft_payload={
                            "motivo": "cliente pediu ajuda",
                            "contexto": {
                                "resumo": "Bolo branco • 26/03/2026 • 15:00",
                                "ultima_mensagem_cliente": "Quero confirmar o bolo branco",
                                "faltando": ["Confirmacao final"],
                                "proximo_passo": "Confirmar resumo final com o cliente",
                                "risk_flags": ["nao_confirmado"],
                            },
                        },
                        order_id=None,
                        created_at="2026-03-24 15:00:00",
                        updated_at="2026-03-24 15:01:00",
                    )
                ]

        class _CustomerRepository:
            def get_customers_by_phones(self, phones):
                return {
                    telefone: CustomerRecord(
                        id=7,
                        nome="Ana",
                        telefone=telefone,
                        criado_em="2026-03-20 10:00:00",
                    )
                }

            def get_customer_by_phone(self, phone: str):
                return None

        cards = build_whatsapp_cards(
            _ProcessRepository(),
            _CustomerRepository(),
            now=datetime(2026, 3, 24, 17, 0, 0),
        )

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["cliente_nome"], "Ana")
        self.assertEqual(cards[0]["stage_label"], "Aguardando humano")
        self.assertTrue(cards[0]["is_human_handoff"])
        self.assertEqual(cards[0]["owner_label"], "Ação humana")
        self.assertEqual(cards[0]["business_state_label"], "Handoff humano")
        self.assertEqual(cards[0]["context_summary"], "Bolo branco • 26/03/2026 • 15:00")
        self.assertEqual(cards[0]["next_step_hint"], "Confirmar resumo final com o cliente")
        self.assertIn("Bolo branco", cards[0]["last_message"])
        self.assertEqual(cards[0]["messages"][0]["content"], "Bolo branco • 26/03/2026 • 15:00")
        self.assertEqual(cards[0]["messages"][1]["content"], "Quero confirmar o bolo branco")
        self.assertEqual(cards[0]["messages"][0]["role"], "contexto")

    def test_build_whatsapp_cards_keeps_active_process_without_runtime_message(self):
        telefone = "5511622222222"

        class _ProcessRepository:
            def list_active_processes(self):
                return [
                    CustomerProcessRecord(
                        id=2,
                        phone=telefone,
                        customer_id=8,
                        process_type="delivery_order",
                        stage="aguardando_confirmacao",
                        status="active",
                        source="legacy_delivery",
                        draft_payload={
                            "descricao": "Bolo branco",
                            "data_entrega": "2026-03-26",
                            "horario_retirada": "15:00",
                            "pagamento": {"forma": "PIX"},
                            "endereco": "Rua Teste, 123",
                        },
                        order_id=321,
                        created_at="2026-03-24 14:00:00",
                        updated_at="2026-03-24 14:30:00",
                    )
                ]

        class _CustomerRepository:
            def get_customers_by_phones(self, phones):
                return {
                    telefone: CustomerRecord(
                        id=8,
                        nome="Bia",
                        telefone=telefone,
                        criado_em="2026-03-20 10:00:00",
                    )
                }

            def get_customer_by_phone(self, phone: str):
                return None

        cards = build_whatsapp_cards(
            _ProcessRepository(),
            _CustomerRepository(),
            now=datetime(2026, 3, 24, 17, 0, 0),
        )

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["cliente_nome"], "Bia")
        self.assertEqual(cards[0]["stage_label"], "Entrega / endereço")
        self.assertEqual(cards[0]["owner_label"], "Ação do cliente")
        self.assertIn("26/03/2026", cards[0]["last_message"])
        self.assertEqual(cards[0]["messages"][0]["role"], "contexto")

    def test_build_whatsapp_cards_surfaces_full_conversation_thread(self):
        telefone = "5511777777777"
        for index in range(8):
            append_conversation_message(
                telefone,
                role="cliente" if index % 2 == 0 else "ia",
                actor_label="Cliente" if index % 2 == 0 else "IA",
                content=f"Mensagem {index}",
                seen_at=datetime(2026, 3, 24, 16, index, 0),
            )
        ai_sessions[telefone] = {"current_agent": "CakeOrderAgent", "messages": []}

        class _ProcessRepository:
            def list_active_processes(self):
                return []

        class _CustomerRepository:
            def get_customers_by_phones(self, phones):
                return {
                    telefone: CustomerRecord(
                        id=9,
                        nome="Carol",
                        telefone=telefone,
                        criado_em="2026-03-20 10:00:00",
                    )
                }

            def get_customer_by_phone(self, phone: str):
                return None

        recent_messages[telefone] = {"texto": "Mensagem 7", "hora": "2026-03-24T16:07:00"}

        cards = build_whatsapp_cards(
            _ProcessRepository(),
            _CustomerRepository(),
            now=datetime(2026, 3, 24, 17, 0, 0),
        )

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["cliente_nome"], "Carol")
        self.assertEqual(len(cards[0]["messages"]), 8)
        self.assertEqual(cards[0]["messages"][0]["content"], "Mensagem 0")
        self.assertEqual(cards[0]["messages"][-1]["content"], "Mensagem 7")

    def test_conversation_only_card_appears_for_fresh_phone(self):
        """Phone sem process/estados mas com mensagem no thread deve aparecer."""
        telefone = "5511444444444"
        append_conversation_message(
            telefone,
            role="cliente",
            actor_label="Desconhecido",
            content="Oi, vi o perfil",
            seen_at=datetime(2026, 3, 24, 16, 45, 0),
        )

        class _ProcessRepository:
            def list_active_processes(self):
                return []

        class _CustomerRepository:
            def get_customers_by_phones(self, phones):
                return {}

            def get_customer_by_phone(self, phone: str):
                return None

        cards = build_whatsapp_cards(
            _ProcessRepository(),
            _CustomerRepository(),
            now=datetime(2026, 3, 24, 17, 0, 0),
        )

        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(card["phone"], telefone)
        self.assertEqual(card["stage_label"], "Conversa aberta")
        self.assertEqual(card["cliente_nome"], telefone)
        self.assertIn("Oi, vi o perfil", card["last_message"])
        self.assertFalse(card["is_human_handoff"])


if __name__ == "__main__":
    unittest.main()
