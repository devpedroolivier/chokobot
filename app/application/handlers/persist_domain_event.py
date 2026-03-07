from __future__ import annotations

import json
import os
from dataclasses import asdict

from app.observability import increment_counter, log_event


OUTBOX_EVENTS_PATH = os.getenv("OUTBOX_EVENTS_PATH", "dados/domain_events.jsonl")


def persist_domain_event(event) -> None:
    payload = asdict(event)
    payload["event_type"] = type(event).__name__

    os.makedirs(os.path.dirname(OUTBOX_EVENTS_PATH), exist_ok=True)
    with open(OUTBOX_EVENTS_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    increment_counter("domain_events_total", event_type=payload["event_type"])
    log_event("domain_event_persisted", event_type=payload["event_type"])
