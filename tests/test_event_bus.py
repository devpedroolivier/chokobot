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
from app.application.service_registry import get_event_bus
from app.application.use_cases.persist_order_payload import PersistOrderPayload


class _FakeOrderWriteRepository:
    def save_order_payload(self, *, phone: str, dados: dict, nome_cliente: str, cliente_id: int | None = None) -> int:
        return 123


class EventBusTests(unittest.TestCase):
    def test_persist_domain_event_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            outbox_path = os.path.join(tmpdir, "domain_events.jsonl")
            event = MessageReceivedEvent(payload={"phone": "5511999999999", "text": "oi"})

            with patch("app.application.handlers.persist_domain_event.OUTBOX_EVENTS_PATH", outbox_path):
                persist_domain_event(event)

            with open(outbox_path, "r", encoding="utf-8") as handle:
                payload = json.loads(handle.read().strip())

        self.assertEqual(payload["event_type"], "MessageReceivedEvent")
        self.assertEqual(payload["payload"]["text"], "oi")

    def test_service_registry_event_bus_dispatches_registered_handler(self):
        get_event_bus.cache_clear()
        with tempfile.TemporaryDirectory() as tmpdir:
            outbox_path = os.path.join(tmpdir, "domain_events.jsonl")
            with patch("app.application.handlers.persist_domain_event.OUTBOX_EVENTS_PATH", outbox_path):
                get_event_bus().publish(AiReplyGeneratedEvent(telefone="5511", nome_cliente="Teste", reply="Resposta"))

            with open(outbox_path, "r", encoding="utf-8") as handle:
                payload = json.loads(handle.read().strip())

        self.assertEqual(payload["event_type"], "AiReplyGeneratedEvent")
        self.assertEqual(payload["reply"], "Resposta")

    def test_service_registry_event_bus_persists_new_operational_events(self):
        get_event_bus.cache_clear()
        with tempfile.TemporaryDirectory() as tmpdir:
            outbox_path = os.path.join(tmpdir, "domain_events.jsonl")
            with patch("app.application.handlers.persist_domain_event.OUTBOX_EVENTS_PATH", outbox_path):
                get_event_bus().publish(
                    OrderClosedByBotEvent(
                        phone="5511",
                        agente="CakeOrderAgent",
                        ferramenta="create_cake_order",
                        order_id=77,
                        protocolo="CHK-000077",
                    )
                )
                get_event_bus().publish(
                    HumanHandoffEscalatedEvent(
                        phone="5511",
                        nome="Cliente",
                        motivo="Cliente pediu humano",
                        categoria="cliente_solicitou",
                        origem="ai",
                    )
                )

            with open(outbox_path, "r", encoding="utf-8") as handle:
                lines = [json.loads(line) for line in handle.read().splitlines() if line.strip()]

        self.assertEqual(lines[0]["event_type"], "OrderClosedByBotEvent")
        self.assertEqual(lines[0]["protocolo"], "CHK-000077")
        self.assertEqual(lines[1]["event_type"], "HumanHandoffEscalatedEvent")
        self.assertEqual(lines[1]["categoria"], "cliente_solicitou")

    def test_persist_order_payload_publishes_order_created_event(self):
        get_event_bus.cache_clear()
        with tempfile.TemporaryDirectory() as tmpdir:
            outbox_path = os.path.join(tmpdir, "domain_events.jsonl")
            use_case = PersistOrderPayload(repository=_FakeOrderWriteRepository())

            with patch("app.application.handlers.persist_domain_event.OUTBOX_EVENTS_PATH", outbox_path):
                order_id = use_case.execute(
                    phone="5511999999999",
                    nome_cliente="Cliente Teste",
                    cliente_id=1,
                    dados={"categoria": "tradicional"},
                )

            with open(outbox_path, "r", encoding="utf-8") as handle:
                payload = json.loads(handle.read().strip())

        self.assertEqual(order_id, 123)
        self.assertEqual(payload["event_type"], "OrderCreatedEvent")
        self.assertEqual(payload["order_id"], 123)
        self.assertEqual(payload["categoria"], "tradicional")


if __name__ == "__main__":
    unittest.main()
