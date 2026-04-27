"""tenant_id propagation through domain events (Phase B.7).

Each event type carries an explicit ``tenant_id`` field so the persisted
JSONL (and, after Phase B.8, the ``events`` Postgres table) can be
filtered per tenant. These tests pin the contract:

1. The dataclasses default ``tenant_id`` to ``None`` for backward
   compatibility with existing call sites.
2. ``persist_domain_event`` round-trips the field unchanged.
3. The wiring at ``persist_order_payload`` and
   ``persist_order_bundle`` actually forwards the kwarg into the
   emitted ``OrderCreatedEvent``.
4. ``activate_human_handoff`` forwards the kwarg into the
   ``HumanHandoffEscalatedEvent``.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.application.events import (
    AiReplyGeneratedEvent,
    HumanHandoffEscalatedEvent,
    MessageReceivedEvent,
    OrderClosedByBotEvent,
    OrderCreatedEvent,
)
from app.application.handlers.persist_domain_event import persist_domain_event
from app.application.service_registry import get_event_bus, reset_registry
from app.application.use_cases.persist_order_bundle import PersistOrderBundle
from app.application.use_cases.persist_order_payload import PersistOrderPayload


class _FakeOrderWriteRepository:
    """Minimal in-memory stub that is enough for both use cases."""

    def __init__(self):
        self.last_kwargs: dict | None = None

    def save_order_payload(self, **kwargs) -> int:
        self.last_kwargs = kwargs
        return 11

    def save_order_bundle(self, **kwargs) -> int:
        self.last_kwargs = kwargs
        return 22


class EventDataclassDefaultsTests(unittest.TestCase):
    """Lock the default and the keyword name."""

    def test_message_received_event_defaults_tenant_id_to_none(self):
        event = MessageReceivedEvent(payload={"text": "oi"})
        self.assertIsNone(event.tenant_id)

    def test_ai_reply_event_accepts_tenant_id(self):
        event = AiReplyGeneratedEvent(
            telefone="5511",
            nome_cliente="Ana",
            reply="oi",
            tenant_id="chokodelicia",
        )
        self.assertEqual(event.tenant_id, "chokodelicia")

    def test_order_created_event_accepts_tenant_id(self):
        event = OrderCreatedEvent(
            order_id=1, phone="5511", nome_cliente="Ana",
            categoria="tradicional", source="order_payload",
            tenant_id="tenant-piloto",
        )
        self.assertEqual(event.tenant_id, "tenant-piloto")

    def test_order_closed_event_accepts_tenant_id(self):
        event = OrderClosedByBotEvent(
            phone="5511", agente="CakeOrderAgent",
            ferramenta="create_cake_order", order_id=1, protocolo="CHK-1",
            tenant_id="chokodelicia",
        )
        self.assertEqual(event.tenant_id, "chokodelicia")

    def test_human_handoff_event_accepts_tenant_id(self):
        event = HumanHandoffEscalatedEvent(
            phone="5511", nome="Ana", motivo="curriculo",
            categoria="alheio", origem="cliente_solicitou",
            tenant_id="tenant-piloto",
        )
        self.assertEqual(event.tenant_id, "tenant-piloto")


class JsonlRoundTripTests(unittest.TestCase):
    """Whatever tenant_id is published with should land in the persisted JSONL.

    Sanitisation of phone/name/text fields strips data — but tenant_id
    is none of those, so it must round-trip verbatim.
    """

    def _publish_and_read(self, event) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            outbox = os.path.join(tmp, "events.jsonl")
            with patch.dict(os.environ, {"OUTBOX_EVENTS_PATH": outbox}, clear=False):
                persist_domain_event(event)
            with open(outbox, encoding="utf-8") as handle:
                return json.loads(handle.read().strip())

    def test_message_received_event_persists_tenant_id(self):
        payload = self._publish_and_read(
            MessageReceivedEvent(payload={"text": "oi"}, tenant_id="tenant-piloto"),
        )
        self.assertEqual(payload["tenant_id"], "tenant-piloto")

    def test_ai_reply_event_persists_tenant_id(self):
        payload = self._publish_and_read(
            AiReplyGeneratedEvent(
                telefone="5511", nome_cliente="Ana", reply="oi",
                tenant_id="chokodelicia",
            ),
        )
        self.assertEqual(payload["tenant_id"], "chokodelicia")

    def test_order_created_event_persists_tenant_id(self):
        payload = self._publish_and_read(
            OrderCreatedEvent(
                order_id=1, phone="5511", nome_cliente="Ana",
                categoria="tradicional", source="order_payload",
                tenant_id="chokodelicia",
            ),
        )
        self.assertEqual(payload["tenant_id"], "chokodelicia")

    def test_tenant_id_none_persists_explicitly(self):
        payload = self._publish_and_read(
            MessageReceivedEvent(payload={"text": "oi"}),
        )
        self.assertIsNone(payload["tenant_id"])


class UseCaseForwardingTests(unittest.TestCase):
    """The two order use cases now accept tenant_id and forward it into
    the emitted OrderCreatedEvent."""

    def _publish_and_read(self, fn) -> dict:
        reset_registry()
        with tempfile.TemporaryDirectory() as tmp:
            outbox = os.path.join(tmp, "events.jsonl")
            with patch.dict(os.environ, {"OUTBOX_EVENTS_PATH": outbox}, clear=False):
                fn()
            with open(outbox, encoding="utf-8") as handle:
                return json.loads(handle.read().strip())

    def test_persist_order_payload_forwards_tenant_id(self):
        repo = _FakeOrderWriteRepository()
        use_case = PersistOrderPayload(repository=repo)

        payload = self._publish_and_read(
            lambda: use_case.execute(
                phone="5511",
                nome_cliente="Ana",
                dados={"categoria": "tradicional"},
                cliente_id=1,
                tenant_id="tenant-piloto",
            ),
        )
        self.assertEqual(payload["event_type"], "OrderCreatedEvent")
        self.assertEqual(payload["tenant_id"], "tenant-piloto")

    def test_persist_order_bundle_forwards_tenant_id(self):
        repo = _FakeOrderWriteRepository()
        use_case = PersistOrderBundle(repository=repo)

        payload = self._publish_and_read(
            lambda: use_case.execute(
                phone="5511",
                nome_cliente="Ana",
                dados={"categoria": "tradicional"},
                cliente_id=1,
                tenant_id="chokodelicia",
            ),
        )
        self.assertEqual(payload["event_type"], "OrderCreatedEvent")
        self.assertEqual(payload["tenant_id"], "chokodelicia")


class HumanHandoffForwardingTests(unittest.TestCase):
    """activate_human_handoff threads tenant_id into HumanHandoffEscalatedEvent."""

    def test_activate_human_handoff_forwards_tenant_id(self):
        from app.application.use_cases.manage_human_handoff import (
            activate_human_handoff,
            clear_customer_active_flows,
        )

        class _StubRepo:
            def upsert_process(self, **_kwargs):
                return None

            def list_active_handoffs(self):  # pragma: no cover - not used here
                return []

        reset_registry()
        clear_customer_active_flows("5511")
        with tempfile.TemporaryDirectory() as tmp:
            outbox = os.path.join(tmp, "events.jsonl")
            with patch.dict(os.environ, {"OUTBOX_EVENTS_PATH": outbox}, clear=False):
                activate_human_handoff(
                    "5511",
                    nome="Ana",
                    motivo="curriculo",
                    audit_writer=None,
                    process_repository=_StubRepo(),
                    tenant_id="tenant-piloto",
                )
            with open(outbox, encoding="utf-8") as handle:
                lines = [
                    json.loads(line) for line in handle.read().splitlines() if line.strip()
                ]

        handoff_events = [e for e in lines if e["event_type"] == "HumanHandoffEscalatedEvent"]
        self.assertEqual(len(handoff_events), 1)
        self.assertEqual(handoff_events[0]["tenant_id"], "tenant-piloto")


if __name__ == "__main__":
    unittest.main()
