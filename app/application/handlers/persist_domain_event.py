from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any

from app.observability import increment_counter, log_event
from app.settings import get_settings


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


def _persist_to_postgres_events_table(safe_payload: dict, tenant_id: str | None) -> bool:
    """Best-effort write to the Postgres ``events`` table (Phase B.8a sink).

    Returns True on success, False if anything fails — the caller falls
    back to the JSONL outbox so a Postgres outage never silences
    telemetry.
    """
    from app.db.database import open_postgres_connection, resolve_tenant_pk

    try:
        tenant_pk = resolve_tenant_pk(tenant_id)
        event_type = safe_payload.get("event_type", "Unknown")
        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO events (tenant_id, event_type, payload) "
                    "VALUES (%s, %s, %s::jsonb)",
                    (
                        tenant_pk,
                        event_type,
                        json.dumps(safe_payload, ensure_ascii=False),
                    ),
                )
        return True
    except Exception as exc:
        log_event(
            "domain_event_pg_persist_failed",
            event_type=safe_payload.get("event_type", "Unknown"),
            error_type=type(exc).__name__,
        )
        return False


def persist_domain_event(event) -> None:
    from app.db.database import is_postgres

    payload = asdict(event)
    payload["event_type"] = type(event).__name__
    safe_payload = _sanitize_event_payload(payload)

    written_to_pg = False
    if is_postgres():
        written_to_pg = _persist_to_postgres_events_table(
            safe_payload, getattr(event, "tenant_id", None),
        )

    if not written_to_pg:
        outbox_events_path = get_settings().outbox_events_path
        os.makedirs(os.path.dirname(outbox_events_path), exist_ok=True)
        with open(outbox_events_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe_payload, ensure_ascii=False) + "\n")

    increment_counter("domain_events_total", event_type=payload["event_type"])
    log_event(
        "domain_event_persisted",
        event_type=payload["event_type"],
        sink="postgres" if written_to_pg else "jsonl",
    )
