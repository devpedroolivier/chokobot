import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.services import store_schedule


class OperationalCalendarTests(unittest.TestCase):
    def test_validate_service_date_blocks_configured_date(self):
        calendar = {
            "blocked_dates": [{"date": "28/03/2026", "reason": "feriado municipal"}],
            "date_overrides": [],
            "slot_capacities": [],
        }
        with patch.object(store_schedule, "load_operational_calendar", return_value=calendar):
            message = store_schedule.validate_service_date("28/03/2026")

        self.assertIn("28/03/2026 (Sabado)", message)
        self.assertIn("feriado municipal", message)

    def test_store_window_for_date_uses_special_override(self):
        calendar = {
            "blocked_dates": [],
            "date_overrides": [{"date": "31/03/2026", "open": "10:00", "close": "16:00", "label": "semana santa"}],
            "slot_capacities": [],
        }
        with patch.object(store_schedule, "load_operational_calendar", return_value=calendar):
            window = store_schedule.store_window_for_date("31/03/2026")

        self.assertEqual(window, ("10:00", "16:00"))

    def test_validate_service_schedule_blocks_slot_when_capacity_is_full(self):
        calendar = {
            "blocked_dates": [],
            "date_overrides": [],
            "slot_capacities": [
                {
                    "date": "28/03/2026",
                    "time_from": "14:00",
                    "time_to": "18:00",
                    "max_orders": 2,
                    "label": "tarde de sabado",
                }
            ],
        }
        with patch.object(store_schedule, "load_operational_calendar", return_value=calendar):
            with patch.object(store_schedule, "_count_scheduled_orders_for_capacity", return_value=2):
                message = store_schedule.validate_service_schedule("28/03/2026", "15:00")

        self.assertIn("Nao temos mais vaga", message)
        self.assertIn("tarde de sabado", message)
        self.assertIn("14:00 as 18:00", message)

    def test_validate_service_date_blocks_full_day_capacity_without_hour(self):
        calendar = {
            "blocked_dates": [],
            "date_overrides": [],
            "slot_capacities": [{"date": "30/03/2026", "max_orders": 3, "label": "capacidade diaria"}],
        }
        with patch.object(store_schedule, "load_operational_calendar", return_value=calendar):
            with patch.object(store_schedule, "_count_scheduled_orders_for_capacity", return_value=3):
                message = store_schedule.validate_service_date("30/03/2026")

        self.assertIn("Nao temos mais vaga", message)
        self.assertIn("capacidade diaria", message)

    def test_operational_calendar_context_lists_next_exceptions(self):
        calendar = {
            "blocked_dates": [{"date": "26/03/2026", "reason": "manutencao"}],
            "date_overrides": [{"date": "27/03/2026", "open": "10:00", "close": "15:00", "label": "horario especial"}],
            "slot_capacities": [],
        }
        reference = datetime(2026, 3, 25, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
        with patch.object(store_schedule, "load_operational_calendar", return_value=calendar):
            context = store_schedule.build_operational_calendar_context(reference)

        self.assertIn("26/03/2026 bloqueado (manutencao)", context)
        self.assertIn("27/03/2026 horario especial 10:00-15:00 (horario especial)", context)

    def test_easter_date_message_reads_seasonal_date_from_calendar(self):
        calendar = {
            "blocked_dates": [],
            "date_overrides": [],
            "slot_capacities": [],
            "seasonal_dates": [
                {"name": "pascoa", "date": "05/04/2026", "label": "Páscoa 2026"}
            ],
        }

        with patch.object(store_schedule, "load_operational_calendar", return_value=calendar):
            message = store_schedule.easter_date_message(datetime(2026, 3, 25, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo")))

        self.assertIn("Páscoa 2026", message)
        self.assertIn("05/04/2026 (Domingo)", message)

    def test_validate_service_date_allows_easter_sunday_with_open_override(self):
        calendar = {
            "blocked_dates": [],
            "date_overrides": [
                {
                    "date": "05/04/2026",
                    "open": "09:00",
                    "close": "18:00",
                    "label": "Domingo de Pascoa - abertura excepcional",
                }
            ],
            "slot_capacities": [],
        }

        with patch.object(store_schedule, "load_operational_calendar", return_value=calendar):
            message = store_schedule.validate_service_date("05/04/2026")

        self.assertIsNone(message)


if __name__ == "__main__":
    unittest.main()
