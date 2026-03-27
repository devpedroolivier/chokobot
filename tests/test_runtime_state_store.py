import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.infrastructure.state.conversation_state_store import (
    ConversationStateStore,
    InMemoryStateBackend,
    SQLiteStateBackend,
    build_conversation_state_store,
)
from app.services.estados import (
    ai_sessions,
    clear_runtime_state,
    get_recent_message,
    has_processed_message,
    mark_processed_message,
    mark_processed_message_if_new,
    set_recent_message,
)


class RuntimeStateStoreTests(unittest.TestCase):
    def setUp(self):
        clear_runtime_state()

    def test_processed_message_tracking_is_shared_in_store(self):
        now = datetime.now()
        self.assertFalse(has_processed_message("msg-1"))

        mark_processed_message("msg-1", now)

        self.assertTrue(has_processed_message("msg-1"))

    def test_mark_processed_message_if_new_respects_ttl_window(self):
        now = datetime.now()

        first = mark_processed_message_if_new("msg-ttl", now, ttl_seconds=60)
        second = mark_processed_message_if_new("msg-ttl", now, ttl_seconds=60)

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertTrue(has_processed_message("msg-ttl"))

        future = now.replace(microsecond=0) + timedelta(seconds=61)
        with patch("app.infrastructure.state.conversation_state_store.datetime") as mocked_datetime:
            mocked_datetime.fromisoformat.side_effect = datetime.fromisoformat
            mocked_datetime.now.return_value = future
            self.assertFalse(has_processed_message("msg-ttl"))

        third = mark_processed_message_if_new("msg-ttl", future, ttl_seconds=60)
        self.assertTrue(third)

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

    def test_state_store_falls_back_to_sqlite_when_redis_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_settings = type(
                "Settings",
                (),
                {
                    "redis_url": "redis://localhost:6379/0",
                    "state_backend_fallback_enabled": True,
                    "state_sqlite_path": os.path.join(tmpdir, "state_store.db"),
                },
            )()

            with patch(
                "app.infrastructure.state.conversation_state_store.get_settings",
                return_value=fake_settings,
            ):
                with patch(
                    "app.infrastructure.state.conversation_state_store.RedisStateBackend",
                    side_effect=RuntimeError("redis_down"),
                ):
                    store = build_conversation_state_store()

        self.assertIsInstance(store, ConversationStateStore)
        self.assertIsInstance(store.backend, SQLiteStateBackend)

    def test_state_store_raises_when_fallback_is_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_settings = type(
                "Settings",
                (),
                {
                    "redis_url": "redis://localhost:6379/0",
                    "state_backend_fallback_enabled": False,
                    "state_sqlite_path": os.path.join(tmpdir, "state_store.db"),
                },
            )()

            with patch(
                "app.infrastructure.state.conversation_state_store.get_settings",
                return_value=fake_settings,
            ):
                with patch(
                    "app.infrastructure.state.conversation_state_store.RedisStateBackend",
                    side_effect=RuntimeError("redis_down"),
                ):
                    with self.assertRaises(RuntimeError) as ctx:
                        build_conversation_state_store()

        self.assertIn("fallback is disabled", str(ctx.exception))

    def test_state_store_falls_back_to_memory_when_sqlite_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_settings = type(
                "Settings",
                (),
                {
                    "redis_url": "",
                    "state_backend_fallback_enabled": True,
                    "state_sqlite_path": os.path.join(tmpdir, "state_store.db"),
                },
            )()

            with patch(
                "app.infrastructure.state.conversation_state_store.get_settings",
                return_value=fake_settings,
            ):
                with patch(
                    "app.infrastructure.state.conversation_state_store.SQLiteStateBackend",
                    side_effect=RuntimeError("sqlite_down"),
                ):
                    store = build_conversation_state_store()

        self.assertIsInstance(store, ConversationStateStore)
        self.assertIsInstance(store.backend, InMemoryStateBackend)


if __name__ == "__main__":
    unittest.main()
