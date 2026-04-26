"""Tenant isolation contract for ConversationStateStore (Phase B.6).

Verifies that two ConversationStateStore instances pointing to the
same backend with distinct tenant_id values do not see each other's
state — a regression of this guarantee would leak conversations and
opt-out flags between tenants.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.infrastructure.state.conversation_state_store import (
    ConversationStateStore,
    InMemoryStateBackend,
)


class StateStoreTenantIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = InMemoryStateBackend()
        self.tenant_a = ConversationStateStore(self.backend, tenant_id="tenant-a")
        self.tenant_b = ConversationStateStore(self.backend, tenant_id="tenant-b")
        self.legacy = ConversationStateStore(self.backend)  # tenant_id = None

    def test_ai_sessions_do_not_leak_between_tenants(self):
        phone = "5511999999999"
        self.tenant_a.ai_sessions[phone] = {"messages": [{"role": "user", "content": "A"}]}
        self.tenant_b.ai_sessions[phone] = {"messages": [{"role": "user", "content": "B"}]}

        self.assertEqual(
            self.tenant_a.ai_sessions[phone]["messages"][0]["content"], "A"
        )
        self.assertEqual(
            self.tenant_b.ai_sessions[phone]["messages"][0]["content"], "B"
        )

    def test_phone_opt_out_is_scoped_per_tenant(self):
        phone = "5511888888888"
        self.tenant_a.set_phone_opted_out(phone, True)

        self.assertTrue(self.tenant_a.is_phone_opted_out(phone))
        self.assertFalse(self.tenant_b.is_phone_opted_out(phone))
        self.assertFalse(self.legacy.is_phone_opted_out(phone))

    def test_processed_message_dedup_does_not_cross_tenants(self):
        seen_at = datetime.now(tz=timezone.utc)
        self.assertTrue(
            self.tenant_a.mark_processed_message_if_new("msg-shared", seen_at)
        )
        # Same message_id but different tenant — must be considered new.
        self.assertTrue(
            self.tenant_b.mark_processed_message_if_new("msg-shared", seen_at)
        )

    def test_recent_messages_do_not_leak(self):
        seen_at = datetime.now(tz=timezone.utc)
        self.tenant_a.set_recent_message("5511777", "from A", seen_at)

        self.assertEqual(self.tenant_a.get_recent_message("5511777")["texto"], "from A")
        self.assertIsNone(self.tenant_b.get_recent_message("5511777"))

    def test_legacy_namespace_coexists_with_tenant_namespaces(self):
        # The legacy (tenant_id=None) store is what Chokodelícia uses
        # today. Its keys live in the un-prefixed namespace and must
        # not collide with new per-tenant keys.
        self.legacy.ai_sessions["legacy-phone"] = {"messages": []}
        self.tenant_a.ai_sessions["legacy-phone"] = {"messages": [{"role": "user", "content": "A"}]}

        self.assertEqual(self.legacy.ai_sessions["legacy-phone"]["messages"], [])
        self.assertEqual(
            self.tenant_a.ai_sessions["legacy-phone"]["messages"][0]["content"], "A"
        )


if __name__ == "__main__":
    unittest.main()
