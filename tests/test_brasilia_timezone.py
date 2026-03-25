import os
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.ai import policies
from app.settings import get_settings
from app.utils.datetime_utils import get_bot_timezone, normalize_to_bot_timezone


class BrasiliaTimezoneTests(unittest.TestCase):
    def test_bot_timezone_defaults_to_brasilia_even_when_tz_env_is_utc(self):
        with patch.dict(os.environ, {"TZ": "Etc/UTC", "BOT_TIMEZONE": ""}, clear=False):
            settings = get_settings()

        self.assertEqual(settings.tz, "Etc/UTC")
        self.assertEqual(settings.bot_timezone, "America/Sao_Paulo")

    def test_policy_timezone_uses_brasilia_fallback(self):
        with patch.dict(os.environ, {"TZ": "Etc/UTC", "BOT_TIMEZONE": ""}, clear=False):
            timezone = policies.current_timezone()

        self.assertEqual(str(timezone), "America/Sao_Paulo")
        self.assertEqual(str(get_bot_timezone()), "America/Sao_Paulo")

    def test_normalize_to_bot_timezone_converts_utc_timestamp(self):
        with patch.dict(os.environ, {"TZ": "Etc/UTC", "BOT_TIMEZONE": ""}, clear=False):
            normalized = normalize_to_bot_timezone(datetime(2026, 3, 25, 18, 0, tzinfo=ZoneInfo("UTC")))

        self.assertEqual(str(normalized.tzinfo), "America/Sao_Paulo")
        self.assertEqual(normalized.strftime("%H:%M"), "15:00")


if __name__ == "__main__":
    unittest.main()
