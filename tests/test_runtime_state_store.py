import os
import unittest
from datetime import datetime

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.services.estados import (
    ai_sessions,
    clear_runtime_state,
    get_recent_message,
    has_processed_message,
    mark_processed_message,
    set_recent_message,
)


class RuntimeStateStoreTests(unittest.TestCase):
    def setUp(self):
        clear_runtime_state()

    def test_processed_message_tracking_is_shared_in_store(self):
        now = datetime(2026, 3, 7, 12, 0, 0)
        self.assertFalse(has_processed_message("msg-1"))

        mark_processed_message("msg-1", now)

        self.assertTrue(has_processed_message("msg-1"))

    def test_recent_message_roundtrip_persists_iso_timestamp(self):
        now = datetime(2026, 3, 7, 12, 1, 0)
        set_recent_message("5511999999999", "oi", now)

        recent = get_recent_message("5511999999999")

        self.assertEqual(recent["texto"], "oi")
        self.assertEqual(recent["hora"], now.isoformat())

    def test_ai_session_mapping_supports_clear_and_assignment(self):
        ai_sessions["5511999999999"] = {"messages": [{"role": "user", "content": "oi"}], "current_agent": "TriageAgent"}

        self.assertIn("5511999999999", ai_sessions)
        ai_sessions.clear()
        self.assertNotIn("5511999999999", ai_sessions)


if __name__ == "__main__":
    unittest.main()
