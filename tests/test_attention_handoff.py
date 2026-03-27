import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.application.use_cases import manage_human_handoff as handoff_module
from app.application.use_cases.manage_human_handoff import activate_human_handoff, deactivate_human_handoff
from app.domain.repositories.customer_process_repository import CustomerProcessRecord
from app.infrastructure.gateways.local_attention_gateway import LocalAttentionGateway
from app.observability import clear_metrics, snapshot_metrics
from app.services.estados import (
    estados_atendimento,
    estados_cafeteria,
    estados_cestas_box,
    estados_encomenda,
    estados_entrega,
    recent_messages,
)


class AttentionHandoffTests(unittest.TestCase):
    def setUp(self):
        clear_metrics()
        handoff_module._KNOWLEDGE_FAILURE_WINDOW_STATE.clear()
        handoff_module._KNOWLEDGE_FAILURE_LAST_ALERT_AT.clear()
        for state_map in (
            estados_atendimento,
            estados_encomenda,
            estados_cafeteria,
            estados_entrega,
            estados_cestas_box,
            recent_messages,
        ):
            state_map.clear()

    @staticmethod
    def _process_repository():
        class _ProcessRepository:
            def get_process(self, phone, process_type):
                return None

            def upsert_process(self, **kwargs):
                return 1

        return _ProcessRepository()

    def test_activate_human_handoff_clears_pending_legacy_states(self):
        telefone = "5511999999999"
        estados_encomenda[telefone] = {"etapa": "massa"}
        estados_cafeteria[telefone] = {"etapa": "pedido"}
        estados_entrega[telefone] = {"etapa": "endereco"}
        estados_cestas_box[telefone] = {"etapa": "selecao"}

        message = activate_human_handoff(
            telefone,
            nome="Cliente Teste",
            audit_writer=None,
            process_repository=self._process_repository(),
        )

        self.assertIn(telefone, estados_atendimento)
        self.assertIn("transferindo", message.casefold())
        self.assertNotIn(telefone, estados_encomenda)
        self.assertNotIn(telefone, estados_cafeteria)
        self.assertNotIn(telefone, estados_entrega)
        self.assertNotIn(telefone, estados_cestas_box)

    def test_local_attention_gateway_uses_shared_handoff_flow(self):
        gateway = LocalAttentionGateway()
        telefone = "5511888888888"
        estados_encomenda[telefone] = {"etapa": "massa"}

        with patch(
            "app.application.use_cases.manage_human_handoff.get_customer_process_repository",
            return_value=self._process_repository(),
        ):
            result = gateway.activate_human_handoff(telefone=telefone, motivo="cliente pediu ajuda")

        self.assertIn(telefone, estados_atendimento)
        self.assertEqual(estados_atendimento[telefone]["motivo"], "cliente pediu ajuda")
        self.assertIn("transferindo", result.casefold())
        self.assertNotIn(telefone, estados_encomenda)

    def test_deactivate_human_handoff_reports_previous_state(self):
        telefone = "5511777777777"
        estados_atendimento[telefone] = {"humano": True}

        process_repository = self._process_repository()
        self.assertTrue(deactivate_human_handoff(telefone, process_repository=process_repository))
        self.assertFalse(deactivate_human_handoff(telefone, process_repository=process_repository))

    def test_activate_human_handoff_persists_process_and_skips_duplicate_audit(self):
        telefone = "5511666666666"
        audit_calls = []
        process_calls = []

        class _ProcessRepository:
            def upsert_process(self, **kwargs):
                process_calls.append(kwargs)
                return 1

        first_at = datetime(2026, 3, 24, 15, 0, 0)
        second_at = first_at + timedelta(minutes=5)

        activate_human_handoff(
            telefone,
            nome="Cliente Teste",
            motivo="cliente pediu ajuda",
            audit_writer=lambda *args: audit_calls.append(args),
            process_repository=_ProcessRepository(),
            now=first_at,
        )
        activate_human_handoff(
            telefone,
            nome="Cliente Teste",
            motivo="cliente pediu ajuda",
            audit_writer=lambda *args: audit_calls.append(args),
            process_repository=_ProcessRepository(),
            now=second_at,
        )

        self.assertEqual(len(audit_calls), 1)
        self.assertEqual(len(process_calls), 2)
        self.assertEqual(process_calls[0]["process_type"], "human_handoff")
        self.assertEqual(process_calls[0]["stage"], "handoff_humano")
        self.assertFalse(process_calls[0]["draft_payload"]["duplicated_request"])
        self.assertTrue(process_calls[1]["draft_payload"]["duplicated_request"])

    def test_deactivate_human_handoff_marks_process_as_resolved(self):
        telefone = "5511555555555"
        estados_atendimento[telefone] = {"humano": True}
        process_calls = []

        class _ProcessRepository:
            def get_process(self, phone, process_type):
                return CustomerProcessRecord(
                    id=1,
                    phone=phone,
                    customer_id=7,
                    process_type=process_type,
                    stage="handoff_humano",
                    status="active",
                    source="human_handoff",
                    draft_payload={"motivo": "cliente pediu ajuda"},
                    order_id=None,
                    created_at="2026-03-24 15:00:00",
                    updated_at="2026-03-24 15:01:00",
                )

            def upsert_process(self, **kwargs):
                process_calls.append(kwargs)
                return 1

        self.assertTrue(deactivate_human_handoff(telefone, process_repository=_ProcessRepository()))
        self.assertEqual(process_calls[0]["process_type"], "human_handoff")
        self.assertEqual(process_calls[0]["status"], "resolved")
        self.assertEqual(process_calls[0]["stage"], "bot_reativado")

    def test_activate_human_handoff_normalizes_injected_time_to_brasilia(self):
        telefone = "5511444444444"

        activate_human_handoff(
            telefone,
            nome="Cliente Teste",
            motivo="cliente pediu ajuda",
            audit_writer=None,
            process_repository=self._process_repository(),
            now=datetime(2026, 3, 25, 18, 0, tzinfo=ZoneInfo("UTC")),
        )

        self.assertEqual(
            estados_atendimento[telefone]["inicio"],
            "2026-03-25T15:00:00-03:00",
        )

    def test_activate_human_handoff_persists_structured_context_from_active_process(self):
        telefone = "5511333333333"
        process_calls = []
        recent_messages[telefone] = {"texto": "Quero fechar para amanha", "hora": "2026-03-24T16:55:00"}

        class _ProcessRepository:
            def list_active_processes(self):
                return [
                    CustomerProcessRecord(
                        id=7,
                        phone=telefone,
                        customer_id=10,
                        process_type="ai_cake_order",
                        stage="aguardando_confirmacao",
                        status="active",
                        source="ai_cake_order",
                        draft_payload={
                            "descricao": "Bolo de chocolate",
                            "data_entrega": "2026-03-26",
                            "horario_retirada": "15:00",
                            "pagamento": {"forma": "PIX"},
                            "modo_recebimento": "entrega",
                        },
                        order_id=None,
                        created_at="2026-03-24 16:30:00",
                        updated_at="2026-03-24 16:50:00",
                    )
                ]

            def upsert_process(self, **kwargs):
                process_calls.append(kwargs)
                return 1

        activate_human_handoff(
            telefone,
            nome="Cliente Teste",
            motivo="cliente pediu ajuda",
            audit_writer=None,
            process_repository=_ProcessRepository(),
            now=datetime(2026, 3, 24, 17, 0, 0),
        )

        payload = process_calls[0]["draft_payload"]
        self.assertEqual(payload["contexto"]["resumo"], "Bolo de chocolate • 26/03/2026 • 15:00")
        self.assertEqual(payload["contexto"]["ultima_mensagem_cliente"], "Quero fechar para amanha")
        self.assertEqual(payload["contexto"]["source_process_type"], "ai_cake_order")
        self.assertEqual(payload["contexto"]["source_stage"], "aguardando_confirmacao")
        self.assertIn("Endereco", payload["contexto"]["faltando"])
        self.assertIn("rascunho_ia", payload["contexto"]["risk_flags"])
        self.assertIn("nao_confirmado", payload["contexto"]["risk_flags"])
        self.assertEqual(payload["contexto"]["proximo_passo"], "Confirmar resumo final com o cliente")

    def test_activate_human_handoff_records_escalation_category_metric(self):
        telefone = "5511222233333"

        class _ProcessRepository:
            def upsert_process(self, **kwargs):
                return 1

        class _EventBus:
            def __init__(self):
                self.events = []

            def publish(self, event):
                self.events.append(event)

        bus = _EventBus()
        with patch("app.application.use_cases.manage_human_handoff.get_event_bus", return_value=bus):
            activate_human_handoff(
                telefone,
                nome="Cliente Teste",
                motivo="Cliente pediu humano",
                audit_writer=None,
                process_repository=_ProcessRepository(),
                now=datetime(2026, 3, 24, 17, 0, 0),
            )

        counters, _ = snapshot_metrics()
        category_total = sum(
            value
            for (name, labels), value in counters.items()
            if name == "escalacao_total" and dict(labels).get("categoria") == "cliente_solicitou"
        )
        self.assertEqual(category_total, 1.0)
        escalated_total = sum(
            value
            for (name, _labels), value in counters.items()
            if name == "pedido_escalado_total"
        )
        self.assertEqual(escalated_total, 1.0)
        self.assertEqual(bus.events[0].categoria, "cliente_solicitou")

    def test_activate_human_handoff_emits_knowledge_failure_warning_after_threshold(self):
        telefone = "5511333344444"

        class _ProcessRepository:
            def upsert_process(self, **kwargs):
                return 1

        with patch.dict(
            "os.environ",
            {
                "KNOWLEDGE_FAILURE_ALERT_THRESHOLD": "2",
                "KNOWLEDGE_FAILURE_ALERT_WINDOW_MINUTES": "60",
            },
            clear=False,
        ):
            with patch("app.application.use_cases.manage_human_handoff.get_event_bus") as mocked_bus:
                mocked_bus.return_value.publish = lambda event: None
                with patch("app.application.use_cases.manage_human_handoff.log_event") as mocked_log_event:
                    activate_human_handoff(
                        telefone,
                        nome="Cliente Teste",
                        motivo="Produto fora de contexto da loja",
                        audit_writer=None,
                        process_repository=_ProcessRepository(),
                        now=datetime(2026, 3, 24, 10, 0, 0),
                    )
                    activate_human_handoff(
                        "5511333344445",
                        nome="Cliente Teste",
                        motivo="Produto fora de contexto da loja",
                        audit_writer=None,
                        process_repository=_ProcessRepository(),
                        now=datetime(2026, 3, 24, 10, 10, 0),
                    )

        warning_calls = [
            call for call in mocked_log_event.call_args_list if call.args and call.args[0] == "knowledge_failure_alert"
        ]
        self.assertTrue(warning_calls)


if __name__ == "__main__":
    unittest.main()
