from __future__ import annotations

from datetime import datetime, timedelta
from typing import Awaitable, Callable

from app.application.commands import GenerateAiReplyCommand
from app.application.events import AiReplyGeneratedEvent
from app.application.service_registry import get_command_bus, get_customer_repository, get_event_bus
from app.application.use_cases.manage_human_handoff import build_reactivation_message, deactivate_human_handoff
from app.config import get_store_closed_notice, is_store_closed
from app.observability import log_event
from app.security import get_admin_phones, hash_phone, preview_text
from app.services.estados import (
    append_conversation_message,
    estados_atendimento,
    get_recent_message,
    has_processed_message,
    is_bot_ativo,
    mark_processed_message,
    set_bot_ativo,
    set_recent_message,
)
from app.utils.mensagens import responder_usuario, responder_usuario_com_contexto
from app.utils.datetime_utils import normalize_to_bot_timezone, now_in_bot_timezone
from app.utils.payload import normalize_incoming


REATIVAR_BOT_OPCOES = ["voltar", "menu", "bot", "reativar", "voltar ao bot"]


async def generate_ai_reply(telefone: str, texto: str, nome_cliente: str, cliente_id: int) -> str:
    return await get_command_bus().dispatch(
        GenerateAiReplyCommand(
            telefone=telefone,
            text=texto,
            nome_cliente=nome_cliente,
            cliente_id=cliente_id,
        )
    )


def save_customer_contact(telefone: str, nome_cliente: str) -> int:
    return get_customer_repository().upsert_customer(nome_cliente, telefone)


async def _send_message(
    responder_usuario_fn: Callable[[str, str], Awaitable[bool]],
    telefone: str,
    mensagem: str,
    *,
    role: str,
    actor_label: str,
) -> bool:
    if responder_usuario_fn in {responder_usuario, responder_usuario_com_contexto}:
        return await responder_usuario_com_contexto(
            telefone,
            mensagem,
            role=role,
            actor_label=actor_label,
        )
    return await responder_usuario_fn(telefone, mensagem)


async def process_inbound_message(
    mensagem: dict,
    *,
    responder_usuario_fn: Callable[[str, str], Awaitable[bool]] = responder_usuario_com_contexto,
    gerar_resposta_ia_fn: Callable[[str, str, str, int], Awaitable[str]] = generate_ai_reply,
    save_customer_fn: Callable[[str, str], int] = save_customer_contact,
) -> None:
    norm = normalize_incoming(mensagem)
    texto = norm["text"]
    if texto:
        texto = texto.lower().strip()
    telefone = norm["phone"]
    nome_cliente = norm["chat_name"] or "Nome não informado"
    msg_id = norm["message_id"]

    if telefone in get_admin_phones():
        cmd = texto.lower()
        if cmd in ["desativar bot", "desligar bot", "pausar bot"]:
            set_bot_ativo(False)
            await _send_message(
                responder_usuario_fn,
                telefone,
                "🚫 Bot desativado temporariamente.",
                role="bot",
                actor_label="Bot",
            )
            log_event("admin_bot_disabled", phone_hash=hash_phone(telefone))
            return

        if cmd in ["ativar bot", "ligar bot", "reativar bot"]:
            set_bot_ativo(True)
            await _send_message(
                responder_usuario_fn,
                telefone,
                "✅ Bot reativado e pronto para atender!",
                role="bot",
                actor_label="Bot",
            )
            log_event("admin_bot_enabled", phone_hash=hash_phone(telefone))
            return

    if not is_bot_ativo():
        log_event("handler_bot_disabled", phone_hash=hash_phone(telefone), text=preview_text(texto))
        return

    if not telefone or not texto:
        log_event(
            "handler_incomplete_message",
            phone_hash=hash_phone(telefone),
            text=preview_text(texto),
            message_type=norm["message_type"],
        )
        return

    agora = now_in_bot_timezone()

    if msg_id and has_processed_message(msg_id):
        log_event("handler_duplicate_webhook", message_id=msg_id, phone_hash=hash_phone(telefone))
        return
    if msg_id:
        mark_processed_message(msg_id, agora)

    ultima = get_recent_message(telefone)
    ultima_hora = None
    if ultima and ultima.get("hora"):
        try:
            ultima_hora = normalize_to_bot_timezone(datetime.fromisoformat(ultima["hora"]))
        except Exception:
            ultima_hora = None
    if ultima and ultima.get("texto") == texto and ultima_hora and (agora - ultima_hora) < timedelta(seconds=2):
        log_event("handler_duplicate_content", phone_hash=hash_phone(telefone), text=preview_text(texto))
        return
    set_recent_message(telefone, texto, agora)
    append_conversation_message(
        telefone,
        role="cliente",
        actor_label=nome_cliente or "Cliente",
        content=texto,
        seen_at=agora,
    )

    cliente_id = save_customer_fn(telefone, nome_cliente)

    if is_store_closed():
        notice = get_store_closed_notice()
        log_event("handler_store_closed_notice_sent", phone_hash=hash_phone(telefone))
        await _send_message(
            responder_usuario_fn,
            telefone,
            notice,
            role="bot",
            actor_label="Bot",
        )
        return

    if telefone in estados_atendimento:
        estado = estados_atendimento[telefone]
        if "inicio" not in estado:
            estado["inicio"] = agora.isoformat()

        ultimo_contato = normalize_to_bot_timezone(datetime.fromisoformat(estado["inicio"]))
        if (agora - ultimo_contato) > timedelta(minutes=30):
            deactivate_human_handoff(telefone)
            await _send_message(
                responder_usuario_fn,
                telefone,
                build_reactivation_message(),
                role="bot",
                actor_label="Bot",
            )
        else:
            if texto in REATIVAR_BOT_OPCOES:
                deactivate_human_handoff(telefone)
                await _send_message(
                    responder_usuario_fn,
                    telefone,
                    build_reactivation_message(),
                    role="bot",
                    actor_label="Bot",
                )
                return

            estados_atendimento[telefone]["inicio"] = agora.isoformat()
            log_event("handler_human_attention_active", phone_hash=hash_phone(telefone))
            return

    resposta_ia = await gerar_resposta_ia_fn(telefone, texto, nome_cliente, cliente_id)
    get_event_bus().publish(
        AiReplyGeneratedEvent(
            telefone=telefone,
            nome_cliente=nome_cliente,
            reply=resposta_ia,
        )
    )
    await _send_message(
        responder_usuario_fn,
        telefone,
        resposta_ia,
        role="ia",
        actor_label="IA",
    )
