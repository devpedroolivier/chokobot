import json
import traceback
import asyncio
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Request

from app.application.events import MessageReceivedEvent
from app.application.service_registry import get_conversation_gateway, get_event_bus
from app.observability import increment_counter, log_event, normalize_reason_label, should_track_phone
from app.security import (
    hash_phone,
    is_replay_event,
    preview_text,
    security_audit,
    verify_webhook_secret,
    webhook_secret_header,
)
from app.utils.mensagens import responder_usuario
from app.utils.datetime_utils import now_in_bot_timezone
from app.utils.payload import is_automated_order_message, is_group_message, normalize_incoming

router = APIRouter()


@dataclass
class _InboundPhoneLockState:
    lock: asyncio.Lock
    queued_requests: int = 0


_inbound_phone_locks: dict[str, _InboundPhoneLockState] = {}
_inbound_phone_locks_guard = asyncio.Lock()


async def _acquire_inbound_phone_lock(phone_key: str) -> asyncio.Lock:
    async with _inbound_phone_locks_guard:
        state = _inbound_phone_locks.get(phone_key)
        if state is None:
            state = _InboundPhoneLockState(lock=asyncio.Lock())
            _inbound_phone_locks[phone_key] = state
        state.queued_requests += 1
        lock = state.lock
    await lock.acquire()
    return lock


async def _release_inbound_phone_lock(phone_key: str, lock: asyncio.Lock) -> None:
    async with _inbound_phone_locks_guard:
        state = _inbound_phone_locks.get(phone_key)
        if state is None:
            if lock.locked():
                lock.release()
            return

        if lock.locked():
            lock.release()
        state.queued_requests = max(0, state.queued_requests - 1)
        if state.queued_requests == 0 and not state.lock.locked():
            _inbound_phone_locks.pop(phone_key, None)


def _track_webhook_event(phone: str | None, *, status: str, reason: str) -> None:
    if not should_track_phone(phone):
        return
    normalized_reason = normalize_reason_label(reason)
    increment_counter("webhook_events_total", status=status, reason=normalized_reason)
    if status == "ignored":
        log_event("webhook_ignored", reason=normalized_reason)


def print_painel(body: dict):
    norm = normalize_incoming(body)
    nome = norm["chat_name"]
    numero = hash_phone(norm["phone"])
    texto = norm["text"]
    hora = now_in_bot_timezone().strftime("%d/%m/%Y %H:%M")

    log_event(
        "webhook_inbound",
        chat_name=preview_text(nome, 40),
        phone_hash=numero,
        text=preview_text(texto, 120),
        at=hora,
    )


async def dispatch_inbound_message(body: dict):
    return await get_conversation_gateway().handle_inbound_message(body)


@router.post("/webhook")
async def receber_webhook(request: Request):
    raw_body = await request.body()
    verify_webhook_secret(request.headers.get(webhook_secret_header()))

    try:
        body = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        security_audit("webhook_invalid_json", error=type(exc).__name__)
        raise HTTPException(status_code=400, detail="invalid_json") from exc

    norm = normalize_incoming(body)
    phone = norm.get("phone")
    track_phone = should_track_phone(phone)
    if not track_phone:
        log_event("webhook_test_phone_ignored", phone_hash=hash_phone(phone))
        return {"status": "ignored", "detail": "test_phone"}

    if body.get("fromMe") or body.get("type") == "DeliveryCallback":
        _track_webhook_event(phone, status="ignored", reason="self_or_callback")
        return {"status": "ignored"}
    if is_group_message(body):
        _track_webhook_event(phone, status="ignored", reason="group_message")
        return {"status": "ignored"}
    if is_automated_order_message(body):
        _track_webhook_event(phone, status="ignored", reason="automated_order_message")
        return {"status": "ignored"}

    if is_replay_event(norm.get("message_id")):
        security_audit("webhook_replay_detected", message_id=norm.get("message_id", ""))
        _track_webhook_event(phone, status="ignored", reason="replay")
        return {"status": "ignored", "detail": "replay_detected"}

    if track_phone:
        print_painel(body)
    get_event_bus().publish(MessageReceivedEvent(payload=norm))

    try:
        phone_key = phone or "anon"
        state = _inbound_phone_locks.get(phone_key)
        if state is not None and state.lock.locked():
            log_event("webhook_inbound_waiting_phone_lock", phone_hash=hash_phone(phone))
        phone_lock = await _acquire_inbound_phone_lock(phone_key)
        try:
            await dispatch_inbound_message(body)
        finally:
            await _release_inbound_phone_lock(phone_key, phone_lock)
        if track_phone:
            increment_counter("webhook_events_total", status="ok", reason="processed")
        return {"status": "ok"}
    except Exception as exc:
        if track_phone:
            increment_counter("webhook_events_total", status="error", reason=type(exc).__name__)
            log_event("webhook_processing_error", error_type=type(exc).__name__)
        traceback.print_exc()
        phone = norm.get("phone")
        if phone:
            try:
                await responder_usuario(
                    phone,
                    "⚠️ Tive um problema interno ao processar sua mensagem. Pode repetir em instantes?"
                )
            except Exception as notify_exc:
                log_event("webhook_error_notification_failed", error_type=type(notify_exc).__name__)
        raise HTTPException(status_code=500, detail="processing_error") from exc
