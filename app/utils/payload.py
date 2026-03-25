from __future__ import annotations

import unicodedata
from typing import Any


def _get(obj: Any, *keys: str) -> Any:
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def extract_text(payload: dict) -> str:
    candidates = [
        _get(payload, "text", "message"),
        payload.get("message"),
        payload.get("body"),
        payload.get("caption"),
        _get(payload, "buttonReply", "title"),
        _get(payload, "listResponse", "title"),
        _get(payload, "buttonsResponseMessage", "selectedDisplayText"),
        _get(payload, "listResponseMessage", "title"),
        _get(payload, "interactive", "button_reply", "title"),
        _get(payload, "interactive", "list_reply", "title"),
        _get(payload, "message", "conversation"),
        _get(payload, "message", "extendedTextMessage", "text"),
        _get(payload, "message", "imageMessage", "caption"),
        _get(payload, "message", "videoMessage", "caption"),
        _get(payload, "message", "documentMessage", "caption"),
        _get(payload, "message", "buttonsResponseMessage", "selectedDisplayText"),
        _get(payload, "message", "listResponseMessage", "title"),
    ]
    for item in candidates:
        if isinstance(item, str) and item.strip():
            return item
    return ""


def extract_phone(payload: dict) -> str:
    phone = payload.get("phone") or payload.get("from") or ""
    if isinstance(phone, str):
        return phone.replace("+", "").strip()
    return ""


def extract_chat_name(payload: dict) -> str:
    name = payload.get("chatName") or payload.get("fromName") or payload.get("name") or "Desconhecido"
    return name if isinstance(name, str) else "Desconhecido"


def extract_message_id(payload: dict) -> str:
    msg_id = payload.get("id") or payload.get("messageId")
    if msg_id:
        return str(msg_id)
    nested = _get(payload, "message", "key", "id")
    return str(nested) if nested else ""


def extract_message_type(payload: dict) -> str:
    msg_type = payload.get("type") or _get(payload, "message", "type") or ""
    return str(msg_type) if msg_type else ""


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


def is_automated_order_message(payload: dict) -> bool:
    text = _normalize_text(extract_text(payload))
    if not text:
        return False

    strong_markers = (
        "pedido goomer delivery",
        "pedido gerado pelo goomer delivery",
        "utm_source=whatsapp",
    )
    if any(marker in text for marker in strong_markers):
        return True

    supporting_markers = (
        "nao precisa baixar nada",
        "gostou de pedir no nosso app",
        "confira o pedido abaixo",
        "retirada agendada:",
        "pagamento:",
        "total:",
    )
    support_hits = sum(1 for marker in supporting_markers if marker in text)
    return "goomer" in text and support_hits >= 2


def is_group_message(payload: dict) -> bool:
    # Common indicators across providers
    if payload.get("isGroup") is True:
        return True
    if payload.get("chat", {}).get("isGroup") is True:
        return True
    phone = extract_phone(payload)
    if phone.endswith("-group"):
        return True
    if "@g.us" in phone:
        return True
    return False


def normalize_incoming(payload: dict) -> dict:
    return {
        "text": extract_text(payload),
        "phone": extract_phone(payload),
        "chat_name": extract_chat_name(payload),
        "message_id": extract_message_id(payload),
        "message_type": extract_message_type(payload),
    }
