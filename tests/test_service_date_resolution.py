import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.store_schedule import (
    build_calendar_reference_context,
    resolve_service_date_context,
    resolve_service_date_reference,
)


class ServiceDateResolutionTests(unittest.TestCase):
    def test_resolves_plain_saturday_in_same_week(self):
        reference = datetime(2026, 3, 24, 17, 23, tzinfo=ZoneInfo("America/Sao_Paulo"))
        resolved = resolve_service_date_reference("Data de entrega: sábado", reference)
        self.assertEqual(resolved.strftime("%d/%m/%Y"), "28/03/2026")

    def test_resolves_saturday_of_next_week(self):
        reference = datetime(2026, 3, 25, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
        resolved = resolve_service_date_reference("Quero para sábado da semana que vem", reference)
        self.assertEqual(resolved.strftime("%d/%m/%Y"), "04/04/2026")

    def test_resolves_day_only_to_next_future_date(self):
        reference = datetime(2026, 3, 25, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
        resolved = resolve_service_date_reference("Sim.dia 4 né", reference)
        self.assertEqual(resolved.strftime("%d/%m/%Y"), "04/04/2026")

    def test_resolves_weekday_and_day_hint(self):
        reference = datetime(2026, 3, 19, 11, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
        resolved = resolve_service_date_reference("Pra quinta feira que vem...dia 26", reference)
        self.assertEqual(resolved.strftime("%d/%m/%Y"), "26/03/2026")

    def test_builds_context_payload_for_conversation_memory(self):
        reference = datetime(2026, 3, 24, 17, 23, tzinfo=ZoneInfo("America/Sao_Paulo"))
        context = resolve_service_date_context("Data de entrega: sábado", reference)
        self.assertEqual(context["date"], "28/03/2026")
        self.assertEqual(context["weekday"], "Sabado")
        self.assertIn("28/03/2026 (Sabado)", context["display"])

    def test_calendar_reference_context_lists_next_weekday_dates(self):
        reference = datetime(2026, 3, 25, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
        context = build_calendar_reference_context(reference)
        self.assertIn("sabado = 28/03/2026", context)
        self.assertIn("domingo = 29/03/2026", context)
        self.assertIn("sabado da semana que vem", context)
        self.assertIn("04/04/2026", context)


if __name__ == "__main__":
    unittest.main()
