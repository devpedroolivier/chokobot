"""Regressão: handoffs com mesmo motivo não devem multiplicar mesmo após bot reativar.

Origem: phone de teste 5511888888888 gerou 50+ escaladas 'cliente pediu ajuda'.
Causa raiz: dedupe in-memory era limpo ao reativar bot (timeout 30min).
Fix: dedupe agora consulta customer_processes (60min TTL).
"""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.application.use_cases import manage_human_handoff as handoff_module
from app.application.use_cases.manage_human_handoff import activate_human_handoff
from app.domain.repositories.customer_process_repository import CustomerProcessRecord
from app.observability import clear_metrics
from app.services.estados import estados_atendimento, recent_messages


class HandoffDedupePersistidoTests(unittest.TestCase):
    def setUp(self):
        clear_metrics()
        for m in (estados_atendimento, recent_messages):
            m.clear()

    def _repo_with_recent_handoff(self, *, phone, motivo, updated_minutes_ago):
        record_time = datetime.now(ZoneInfo("UTC")) - timedelta(minutes=updated_minutes_ago)

        class _ProcessRepository:
            audit_calls = []

            def get_process(self, p, t):
                if p == phone and t == "human_handoff":
                    return CustomerProcessRecord(
                        id=1,
                        phone=phone,
                        customer_id=None,
                        process_type="human_handoff",
                        stage="bot_reativado",
                        status="resolved",
                        source="human_handoff",
                        draft_payload={"motivo": motivo, "categoria": "falha_bot"},
                        order_id=None,
                        created_at=record_time.isoformat(),
                        updated_at=record_time.isoformat(),
                    )
                return None

            def upsert_process(self, **kwargs):
                return 1

        return _ProcessRepository

    def test_dedupe_quando_handoff_persistido_recente(self):
        phone = "5511888888888"
        motivo = "cliente pediu ajuda"
        repo_cls = self._repo_with_recent_handoff(
            phone=phone, motivo=motivo, updated_minutes_ago=5
        )

        audit_calls = []

        def fake_audit(t, n, m, c):
            audit_calls.append((t, n, m, c))

        activate_human_handoff(
            phone,
            motivo=motivo,
            audit_writer=fake_audit,
            process_repository=repo_cls(),
        )
        self.assertEqual(audit_calls, [], "Não deve auditar quando há handoff persistido recente com mesmo motivo")

    def test_audit_quando_motivo_diferente(self):
        phone = "5511888888888"
        repo_cls = self._repo_with_recent_handoff(
            phone=phone, motivo="motivo antigo", updated_minutes_ago=5
        )
        audit_calls = []

        def fake_audit(t, n, m, c):
            audit_calls.append(m)

        activate_human_handoff(
            phone,
            motivo="motivo novo",
            audit_writer=fake_audit,
            process_repository=repo_cls(),
        )
        self.assertEqual(len(audit_calls), 1)

    def test_audit_quando_handoff_antigo(self):
        """Handoff persistido > 60min: não bloqueia novo audit."""
        phone = "5511888888888"
        motivo = "cliente pediu ajuda"
        repo_cls = self._repo_with_recent_handoff(
            phone=phone, motivo=motivo, updated_minutes_ago=120
        )
        audit_calls = []

        def fake_audit(t, n, m, c):
            audit_calls.append(m)

        activate_human_handoff(
            phone,
            motivo=motivo,
            audit_writer=fake_audit,
            process_repository=repo_cls(),
        )
        self.assertEqual(len(audit_calls), 1)


if __name__ == "__main__":
    unittest.main()
