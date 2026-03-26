import os
import unittest
from datetime import datetime

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.application.use_cases.panel_dashboard import build_process_cards
from app.domain.repositories.customer_process_repository import CustomerProcessRecord
from app.domain.repositories.customer_repository import CustomerRecord


class PanelProcessCardsTests(unittest.TestCase):
    def test_build_process_cards_formats_and_prioritizes_active_processes_for_panel(self):
        class _ProcessRepository:
            def list_active_processes(self):
                return [
                    CustomerProcessRecord(
                        id=11,
                        phone="5511666666666",
                        customer_id=8,
                        process_type="delivery_order",
                        stage="coletando_endereco",
                        status="active",
                        source="legacy_delivery",
                        draft_payload={
                            "categoria": "tradicional",
                            "descricao": "Bolo branco",
                            "data_entrega": "2026-03-26",
                            "horario_retirada": "15:00",
                            "pagamento": {"forma": "Pendente"},
                        },
                        order_id=None,
                        created_at="2026-03-23 16:10:00",
                        updated_at="2026-03-23 16:40:00",
                    ),
                    CustomerProcessRecord(
                        id=10,
                        phone="5511999999999",
                        customer_id=7,
                        process_type="delivery_order",
                        stage="aguardando_confirmacao",
                        status="active",
                        source="legacy_delivery",
                        draft_payload={
                            "categoria": "tradicional",
                            "descricao": "Bolo de chocolate",
                            "data_entrega": "2026-03-25",
                            "horario_retirada": "14:00",
                            "endereco": "Rua Teste, 123",
                            "pagamento": {"forma": "PIX"},
                        },
                        order_id=321,
                        created_at="2026-03-23 16:00:00",
                        updated_at="2026-03-23 16:30:00",
                    ),
                    CustomerProcessRecord(
                        id=12,
                        phone="5511777777777",
                        customer_id=9,
                        process_type="ai_sweet_order",
                        stage="aguardando_confirmacao",
                        status="active",
                        source="ai_sweet_order",
                        draft_payload={
                            "itens": ["Brigadeiro Escama x10"],
                            "data_entrega": "2026-03-24",
                            "horario_retirada": "11:00",
                            "modo_recebimento": "retirada",
                            "pagamento": {"forma": "PIX"},
                        },
                        order_id=None,
                        created_at="2026-03-23 16:20:00",
                        updated_at="2026-03-23 16:50:00",
                    ),
                ]

        class _CustomerRepository:
            def get_customer_by_phone(self, phone: str):
                if phone == "5511666666666":
                    return CustomerRecord(
                        id=8,
                        nome="Bia",
                        telefone=phone,
                        criado_em="2026-03-20 10:00:00",
                    )
                if phone == "5511777777777":
                    return CustomerRecord(
                        id=9,
                        nome="Clara",
                        telefone=phone,
                        criado_em="2026-03-20 10:00:00",
                    )
                return CustomerRecord(
                    id=7,
                    nome="Ana",
                    telefone=phone,
                    criado_em="2026-03-20 10:00:00",
                )

        cards = build_process_cards(
            _ProcessRepository(),
            _CustomerRepository(),
            now=datetime(2026, 3, 23, 17, 0, 0),
        )

        self.assertEqual(len(cards), 3)
        self.assertEqual(cards[0]["cliente_nome"], "Ana")
        self.assertEqual(cards[0]["process_label"], "Entrega em montagem")
        self.assertEqual(cards[0]["stage_label"], "Aguardando confirmacao")
        self.assertEqual(cards[0]["origin_label"], "Atendimento")
        self.assertEqual(cards[0]["owner_label"], "Ação do cliente")
        self.assertEqual(cards[0]["order_id"], 321)
        self.assertIn("confirmacao", cards[0]["owner_hint"].casefold())
        self.assertEqual(cards[0]["action_label"], "Pronto para fechar")
        self.assertEqual(cards[0]["missing_items"], ["Confirmacao final"])
        self.assertIn("25/03/2026", cards[0]["summary"])
        self.assertIn("14:00", cards[0]["summary"])
        self.assertEqual(cards[1]["cliente_nome"], "Clara")
        self.assertEqual(cards[1]["process_label"], "Doces IA aguardando confirmacao")
        self.assertEqual(cards[1]["origin_label"], "Rascunho IA")
        self.assertEqual(cards[1]["owner_label"], "Ação do cliente")
        self.assertEqual(cards[1]["missing_items"], ["Confirmacao final"])
        self.assertEqual(cards[2]["cliente_nome"], "Bia")
        self.assertEqual(cards[2]["action_label"], "Completar dados")
        self.assertEqual(cards[2]["owner_label"], "Ação humana")
        self.assertIn("Pagamento", cards[2]["missing_items"])
        self.assertIn("Endereco", cards[2]["missing_items"])

    def test_build_process_cards_surfaces_handoff_context_and_business_state(self):
        class _ProcessRepository:
            def list_active_processes(self):
                return [
                    CustomerProcessRecord(
                        id=13,
                        phone="5511666666666",
                        customer_id=6,
                        process_type="human_handoff",
                        stage="handoff_humano",
                        status="active",
                        source="human_handoff",
                        draft_payload={
                            "motivo": "cliente pediu ajuda",
                            "contexto": {
                                "resumo": "Bolo branco • 26/03/2026 • 15:00",
                                "faltando": ["Confirmacao final", "Endereco"],
                                "proximo_passo": "Confirmar resumo final e validar endereco",
                                "risk_flags": ["nao_confirmado", "dados_incompletos"],
                            },
                        },
                        order_id=None,
                        created_at="2026-03-23 15:00:00",
                        updated_at="2026-03-23 15:30:00",
                    )
                ]

        class _CustomerRepository:
            def get_customer_by_phone(self, phone: str):
                return CustomerRecord(
                    id=6,
                    nome="Debora",
                    telefone=phone,
                    criado_em="2026-03-20 10:00:00",
                )

        cards = build_process_cards(
            _ProcessRepository(),
            _CustomerRepository(),
            now=datetime(2026, 3, 23, 17, 0, 0),
        )

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["cliente_nome"], "Debora")
        self.assertEqual(cards[0]["summary"], "Bolo branco • 26/03/2026 • 15:00")
        self.assertEqual(cards[0]["missing_items"], ["Confirmacao final", "Endereco"])
        self.assertEqual(cards[0]["owner_hint"], "Confirmar resumo final e validar endereco")
        self.assertEqual(cards[0]["next_step_hint"], "Confirmar resumo final e validar endereco")
        self.assertEqual(cards[0]["business_state_slug"], "handoff")
        self.assertEqual(cards[0]["business_state_label"], "Handoff humano")
        self.assertIn("nao_confirmado", cards[0]["risk_flags"])

    def test_build_process_cards_prefers_bulk_customer_lookup_when_repository_supports_it(self):
        class _ProcessRepository:
            def list_active_processes(self):
                return [
                    CustomerProcessRecord(
                        id=1,
                        phone="5511999999999",
                        customer_id=7,
                        process_type="delivery_order",
                        stage="aguardando_confirmacao",
                        status="active",
                        source="legacy_delivery",
                        draft_payload={"descricao": "Bolo", "data_entrega": "2026-03-25", "horario": "14:00"},
                        order_id=321,
                        created_at="2026-03-23 16:00:00",
                        updated_at="2026-03-23 16:30:00",
                    )
                ]

        class _CustomerRepository:
            def __init__(self):
                self.bulk_calls = 0
                self.single_calls = 0

            def get_customers_by_phones(self, phones):
                self.bulk_calls += 1
                return {
                    "5511999999999": CustomerRecord(
                        id=7,
                        nome="Ana",
                        telefone="5511999999999",
                        criado_em="2026-03-20 10:00:00",
                    )
                }

            def get_customer_by_phone(self, phone: str):
                self.single_calls += 1
                return None

        customer_repository = _CustomerRepository()
        cards = build_process_cards(
            _ProcessRepository(),
            customer_repository,
            now=datetime(2026, 3, 23, 17, 0, 0),
        )

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["cliente_nome"], "Ana")
        self.assertEqual(customer_repository.bulk_calls, 1)
        self.assertEqual(customer_repository.single_calls, 0)

    def test_build_process_cards_filters_test_phone_processes(self):
        class _ProcessRepository:
            def list_active_processes(self):
                return [
                    CustomerProcessRecord(
                        id=99,
                        phone="5511888888888",
                        customer_id=99,
                        process_type="delivery_order",
                        stage="aguardando_confirmacao",
                        status="active",
                        source="legacy_delivery",
                        draft_payload={
                            "descricao": "Bolo teste",
                            "data_entrega": "2026-03-26",
                            "horario_retirada": "15:00",
                            "pagamento": {"forma": "PIX"},
                        },
                        order_id=999,
                        created_at="2026-03-23 16:00:00",
                        updated_at="2026-03-23 16:30:00",
                    )
                ]

        class _CustomerRepository:
            def get_customer_by_phone(self, phone: str):
                return CustomerRecord(
                    id=99,
                    nome="Teste",
                    telefone=phone,
                    criado_em="2026-03-20 10:00:00",
                )

        cards = build_process_cards(
            _ProcessRepository(),
            _CustomerRepository(),
            now=datetime(2026, 3, 23, 17, 0, 0),
        )

        self.assertEqual(len(cards), 0)
