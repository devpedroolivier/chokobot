from __future__ import annotations

import hashlib
import hmac
import threading
import time
from collections.abc import Mapping

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.observability import increment_counter, log_event
from app.settings import get_settings


_panel_basic = HTTPBasic(auto_error=False)
_replay_lock = threading.Lock()
_replay_cache: dict[str, float] = {}

def panel_auth_enabled() -> bool:
    return get_settings().panel_auth_enabled


def webhook_verification_enabled() -> bool:
    settings = get_settings()
    if settings.webhook_secret:
        return True
    return settings.webhook_verify_enabled


def ai_learning_enabled() -> bool:
    return get_settings().ai_save_learning_enabled


def get_admin_phones() -> set[str]:
    return set(get_settings().admin_phones)


def _normalize_phone(phone: str | None) -> str:
    raw_value = str(phone or "").strip()
    if not raw_value:
        return ""
    return "".join(char for char in raw_value if char.isdigit())


def _phone_variants(phone: str | None) -> set[str]:
    normalized = _normalize_phone(phone)
    if not normalized:
        return set()
    variants = {normalized}
    if normalized.startswith("55") and len(normalized) > 11:
        variants.add(normalized[2:])
    if len(normalized) in {10, 11}:
        variants.add(f"55{normalized}")
    return variants


def is_phone_automation_disabled(phone: str | None) -> bool:
    blocked_phones = get_settings().automation_disabled_phones
    if not blocked_phones:
        return False

    blocked_variants: set[str] = set()
    for blocked in blocked_phones:
        blocked_variants.update(_phone_variants(blocked))

    return bool(_phone_variants(phone) & blocked_variants)


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

    settings = get_settings()
    username = settings.panel_auth_username
    password = settings.panel_auth_password
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

    expected = get_settings().webhook_secret
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
    return get_settings().webhook_replay_window_seconds


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
    return get_settings().webhook_secret_header
