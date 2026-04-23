import os
import unittest
from datetime import datetime
from unittest.mock import patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.services.store_schedule import ai_auto_schedule_state, is_ai_within_schedule


class AiAutoScheduleTests(unittest.TestCase):
    """Valida a janela automática da Trufinha com defaults sex 19h → seg 06h."""

    def _apply_defaults(self) -> dict:
        return {
            "AI_AUTO_SCHEDULE_ENABLED": "1",
            "AI_AUTO_OFF_WEEKDAY": "4",
            "AI_AUTO_OFF_HOUR": "19",
            "AI_AUTO_OFF_MINUTE": "0",
            "AI_AUTO_ON_WEEKDAY": "0",
            "AI_AUTO_ON_HOUR": "6",
            "AI_AUTO_ON_MINUTE": "0",
        }

    def test_thursday_mid_day_is_active(self):
        with patch.dict(os.environ, self._apply_defaults(), clear=False):
            # 2026-04-23 is a Thursday (weekday=3).
            state = ai_auto_schedule_state(datetime(2026, 4, 23, 14, 30))
            self.assertTrue(state["active"])
            self.assertTrue(is_ai_within_schedule(datetime(2026, 4, 23, 14, 30)))

    def test_friday_just_before_cutoff_is_active(self):
        with patch.dict(os.environ, self._apply_defaults(), clear=False):
            state = ai_auto_schedule_state(datetime(2026, 4, 24, 18, 59))
            self.assertTrue(state["active"])

    def test_friday_at_cutoff_is_inactive(self):
        with patch.dict(os.environ, self._apply_defaults(), clear=False):
            state = ai_auto_schedule_state(datetime(2026, 4, 24, 19, 0))
            self.assertFalse(state["active"])
            self.assertFalse(is_ai_within_schedule(datetime(2026, 4, 24, 19, 0)))

    def test_saturday_midday_is_inactive(self):
        with patch.dict(os.environ, self._apply_defaults(), clear=False):
            state = ai_auto_schedule_state(datetime(2026, 4, 25, 12, 0))
            self.assertFalse(state["active"])

    def test_sunday_evening_is_inactive(self):
        with patch.dict(os.environ, self._apply_defaults(), clear=False):
            state = ai_auto_schedule_state(datetime(2026, 4, 26, 23, 30))
            self.assertFalse(state["active"])

    def test_monday_five_fifty_nine_is_inactive(self):
        with patch.dict(os.environ, self._apply_defaults(), clear=False):
            state = ai_auto_schedule_state(datetime(2026, 4, 27, 5, 59))
            self.assertFalse(state["active"])

    def test_monday_six_is_active(self):
        with patch.dict(os.environ, self._apply_defaults(), clear=False):
            state = ai_auto_schedule_state(datetime(2026, 4, 27, 6, 0))
            self.assertTrue(state["active"])

    def test_schedule_disabled_flag_keeps_ai_always_active(self):
        with patch.dict(
            os.environ,
            {**self._apply_defaults(), "AI_AUTO_SCHEDULE_ENABLED": "0"},
            clear=False,
        ):
            # Sábado à tarde — com flag desligada, AI segue ativa.
            state = ai_auto_schedule_state(datetime(2026, 4, 25, 14, 0))
            self.assertTrue(state["active"])
            self.assertFalse(state["enabled"])


if __name__ == "__main__":
    unittest.main()
