from __future__ import annotations

import hashlib
import hmac
import os
import threading
import time
from collections.abc import Mapping

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.observability import increment_counter, log_event


_panel_basic = HTTPBasic(auto_error=False)
_replay_lock = threading.Lock()
_replay_cache: dict[str, float] = {}


def _env_flag(name: str, default: str = "0") -> bool:
    raw = os.getenv(name, default).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def panel_auth_enabled() -> bool:
    return _env_flag("PANEL_AUTH_ENABLED", "0")


def webhook_verification_enabled() -> bool:
    if os.getenv("WEBHOOK_SECRET", "").strip():
        return True
    return _env_flag("WEBHOOK_VERIFY_ENABLED", "0")


def ai_learning_enabled() -> bool:
    return _env_flag("AI_SAVE_LEARNING_ENABLED", "0")


def get_admin_phones() -> set[str]:
    raw = os.getenv("ADMIN_PHONES", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def hash_phone(phone: str | None) -> str:
    if not phone:
        return "anon"
    digest = hashlib.sha256(phone.encode("utf-8")).hexdigest()
    return digest[:12]


def preview_text(text: str | None, limit: int = 80) -> str:
    if not text:
        return ""
    compact = " ".join(str(text).split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def security_audit(event: str, **fields) -> None:
    increment_counter("security_events_total", event=event)
    log_event(f"security_{event}", **fields)


def require_panel_auth(
    credentials: HTTPBasicCredentials | None = Depends(_panel_basic),
) -> None:
    if not panel_auth_enabled():
        return

    username = os.getenv("PANEL_AUTH_USERNAME", "")
    password = os.getenv("PANEL_AUTH_PASSWORD", "")
    if not username or not password:
        security_audit("panel_auth_misconfigured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="panel_auth_not_configured",
        )

    if credentials is None:
        security_audit("panel_auth_missing_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="panel_auth_required",
            headers={"WWW-Authenticate": "Basic"},
        )

    valid_username = hmac.compare_digest(credentials.username, username)
    valid_password = hmac.compare_digest(credentials.password, password)
    if valid_username and valid_password:
        return

    security_audit("panel_auth_failed", username=preview_text(credentials.username, 24))
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid_panel_credentials",
        headers={"WWW-Authenticate": "Basic"},
    )


def verify_webhook_secret(secret_value: str | None) -> None:
    if not webhook_verification_enabled():
        return

    expected = os.getenv("WEBHOOK_SECRET", "").strip()
    if not expected:
        security_audit("webhook_secret_missing")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="webhook_not_configured",
        )

    provided = (secret_value or "").strip()
    if hmac.compare_digest(provided, expected):
        return

    security_audit("webhook_secret_invalid")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid_webhook_secret",
    )


def webhook_replay_window_seconds() -> int:
    try:
        return max(1, int(os.getenv("WEBHOOK_REPLAY_WINDOW_SECONDS", "300")))
    except ValueError:
        return 300


def is_replay_event(message_id: str | None) -> bool:
    if not message_id:
        return False

    now = time.time()
    window = webhook_replay_window_seconds()

    with _replay_lock:
        expired = [key for key, seen_at in _replay_cache.items() if now - seen_at > window]
        for key in expired:
            _replay_cache.pop(key, None)

        if message_id in _replay_cache:
            return True

        _replay_cache[message_id] = now
        return False


def clear_replay_cache() -> None:
    with _replay_lock:
        _replay_cache.clear()


def redact_payload(payload: Mapping | None) -> dict:
    data = dict(payload or {})
    for key in ("phone", "from", "sender", "chatId"):
        if key in data:
            data[key] = f"hash:{hash_phone(str(data[key]))}"
    for key in ("message", "body", "caption", "text"):
        if key in data and isinstance(data[key], str):
            data[key] = preview_text(data[key], 120)
    return data


def webhook_secret_header() -> str:
    return os.getenv("WEBHOOK_SECRET_HEADER", "X-Webhook-Secret")
