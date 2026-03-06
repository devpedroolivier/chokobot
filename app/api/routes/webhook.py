import json
import traceback
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from app.handler import processar_mensagem
from app.observability import increment_counter, log_event
from app.security import (
    hash_phone,
    is_replay_event,
    preview_text,
    security_audit,
    verify_webhook_secret,
    webhook_secret_header,
)
from app.utils.mensagens import responder_usuario
from app.utils.payload import is_group_message, normalize_incoming

router = APIRouter()


def print_painel(body: dict):
    norm = normalize_incoming(body)
    nome = norm["chat_name"]
    numero = hash_phone(norm["phone"])
    texto = norm["text"]
    hora = datetime.now().strftime("%d/%m/%Y %H:%M")

    log_event(
        "webhook_inbound",
        chat_name=preview_text(nome, 40),
        phone_hash=numero,
        text=preview_text(texto, 120),
        at=hora,
    )


@router.post("/webhook")
async def receber_webhook(request: Request):
    raw_body = await request.body()
    verify_webhook_secret(request.headers.get(webhook_secret_header()))

    try:
        body = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        security_audit("webhook_invalid_json", error=type(exc).__name__)
        raise HTTPException(status_code=400, detail="invalid_json") from exc

    if body.get("fromMe") or body.get("type") == "DeliveryCallback":
        increment_counter("webhook_events_total", status="ignored", reason="self_or_callback")
        log_event("webhook_ignored", reason="self_or_callback")
        return {"status": "ignored"}
    if is_group_message(body):
        increment_counter("webhook_events_total", status="ignored", reason="group_message")
        log_event("webhook_ignored", reason="group_message")
        return {"status": "ignored"}

    norm = normalize_incoming(body)
    if is_replay_event(norm.get("message_id")):
        security_audit("webhook_replay_detected", message_id=norm.get("message_id", ""))
        increment_counter("webhook_events_total", status="ignored", reason="replay")
        return {"status": "ignored", "detail": "replay_detected"}

    print_painel(body)

    try:
        await processar_mensagem(body)
        increment_counter("webhook_events_total", status="ok", reason="processed")
        return {"status": "ok"}
    except Exception as exc:
        increment_counter("webhook_events_total", status="error", reason=type(exc).__name__)
        log_event("webhook_processing_error", error_type=type(exc).__name__)
        traceback.print_exc()
        phone = norm.get("phone")
        if phone:
            await responder_usuario(
                phone,
                "⚠️ Tive um problema interno ao processar sua mensagem. Pode repetir em instantes?"
            )
        return {"status": "error"}
