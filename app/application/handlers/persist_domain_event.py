from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any

from app.observability import increment_counter, log_event
from app.settings import get_settings


OUTBOX_EVENTS_PATH = get_settings().outbox_events_path

_PHONE_KEYS = {"phone", "telefone"}
_NAME_KEYS = {"nome", "nome_cliente", "chat_name"}
_TEXT_KEYS = {"message", "mensagem", "text", "reply"}


def _mask_phone(value: Any) -> str:
    raw = "".join(ch for ch in str(value or "") if ch.isdigit())
    if not raw:
        return "anon"
    return f"***{raw[-4:]}"


def _mask_name(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "anon"
    return raw[0] + "***"


def _sanitize_event_payload(value: Any, *, key: str | None = None) -> Any:
    normalized_key = (key or "").strip().lower()

    if isinstance(value, dict):
        return {k: _sanitize_event_payload(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_event_payload(item, key=key) for item in value]

    if normalized_key in _PHONE_KEYS:
        return _mask_phone(value)
    if normalized_key in _NAME_KEYS:
        return _mask_name(value)
    if normalized_key in _TEXT_KEYS:
        raw = str(value or "").strip()
        return raw[:160] + ("..." if len(raw) > 160 else "")

    return value


def persist_domain_event(event) -> None:
    payload = asdict(event)
    payload["event_type"] = type(event).__name__
    safe_payload = _sanitize_event_payload(payload)

    os.makedirs(os.path.dirname(OUTBOX_EVENTS_PATH), exist_ok=True)
    with open(OUTBOX_EVENTS_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe_payload, ensure_ascii=False) + "\n")

    increment_counter("domain_events_total", event_type=payload["event_type"])
    log_event("domain_event_persisted", event_type=payload["event_type"])
