from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Awaitable, Callable

REPLY_DEDUPE_WINDOW_SECONDS = 10

from app.application.commands import GenerateAiReplyCommand
from app.application.events import AiReplyGeneratedEvent, AiReplySkippedEvent
from app.application.service_registry import get_command_bus, get_customer_repository, get_event_bus
from app.application.use_cases.manage_human_handoff import build_reactivation_message, deactivate_human_handoff
from app.config import get_store_closed_notice, is_store_closed
from app.observability import log_event, should_track_phone
from app.security import get_admin_phones, hash_phone, is_phone_automation_disabled, preview_text
from app.settings import get_settings
from app.services.estados import (
    append_conversation_message,
    estados_atendimento,
    get_phone_opted_out_updated_at,
    get_recent_bot_reply,
    get_recent_message,
    is_bot_ativo,
    is_phone_opted_out,
    mark_processed_message_if_new,
    set_phone_opted_out,
    set_bot_ativo,
    set_recent_bot_reply,
    set_recent_message,
)
from app.services.store_schedule import ai_auto_schedule_state
from app.utils.mensagens import responder_usuario, responder_usuario_com_contexto
from app.utils.datetime_utils import normalize_to_bot_timezone, now_in_bot_timezone
from app.utils.payload import normalize_incoming
from app.welcome_message import HANDOFF_PENDING_ACK_MESSAGE, OPT_OUT_MESSAGE


REATIVAR_BOT_OPCOES = ["voltar", "menu", "bot", "reativar", "voltar ao bot", "ativar chat", "ativar bot"]
MESSAGE_IDEMPOTENCY_TTL_SECONDS = 60


def _publish_skip(telefone: str, motivo: str, *, tenant_id: str | None = None) -> None:
    if not telefone:
        return
    try:
        get_event_bus().publish(
            AiReplySkippedEvent(phone=telefone, motivo=motivo, tenant_id=tenant_id)
        )
    except Exception:
        log_event("ai_reply_skip_publish_failed", motivo=motivo)


async def generate_ai_reply(
    telefone: str,
    texto: str,
    nome_cliente: str,
    cliente_id: int,
    *,
    tenant_id: str | None = None,
) -> str:
    return await get_command_bus().dispatch(
        GenerateAiReplyCommand(
            telefone=telefone,
            text=texto,
            nome_cliente=nome_cliente,
            cliente_id=cliente_id,
            tenant_id=tenant_id,
        )
    )


def save_customer_contact(
    telefone: str, nome_cliente: str, *, tenant_id: str | None = None
) -> int:
    return get_customer_repository(tenant_id).upsert_customer(
        nome_cliente, telefone, tenant_id=tenant_id
    )


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
    tenant_id: str | None = None,
) -> None:
    norm = normalize_incoming(mensagem)
    texto = norm["text"]
    if texto:
        texto = texto.lower().strip()
    telefone = norm["phone"]
    nome_cliente = norm["chat_name"] or "Nome não informado"
    msg_id = norm["message_id"]
    if tenant_id is None:
        tenant_id = norm.get("tenant_id")

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

    if not get_settings().bot_auto_replies_enabled:
        if not telefone or not texto:
            return
        if not should_track_phone(telefone):
            log_event("handler_test_phone_ignored", phone_hash=hash_phone(telefone))
            return
        agora = now_in_bot_timezone()
        if msg_id and not mark_processed_message_if_new(
            msg_id, agora, ttl_seconds=MESSAGE_IDEMPOTENCY_TTL_SECONDS
        ):
            return
        append_conversation_message(
            telefone,
            role="cliente",
            actor_label=nome_cliente or "Cliente",
            content=texto,
            seen_at=agora,
        )
        save_customer_fn(telefone, nome_cliente)
        log_event(
            "handler_auto_replies_disabled",
            phone_hash=hash_phone(telefone),
            text=preview_text(texto),
        )
        return

    if not is_bot_ativo():
        log_event("handler_bot_disabled", phone_hash=hash_phone(telefone), text=preview_text(texto))
        _publish_skip(telefone, "bot_disabled", tenant_id=tenant_id)
        return

    ai_window = ai_auto_schedule_state()
    if not ai_window["active"]:
        if telefone and texto:
            agora_window = now_in_bot_timezone()
            if msg_id and not mark_processed_message_if_new(
                msg_id, agora_window, ttl_seconds=MESSAGE_IDEMPOTENCY_TTL_SECONDS
            ):
                return
            append_conversation_message(
                telefone,
                role="cliente",
                actor_label=nome_cliente or "Cliente",
                content=texto,
                seen_at=agora_window,
            )
            save_customer_fn(telefone, nome_cliente)
        log_event(
            "handler_ai_schedule_off",
            phone_hash=hash_phone(telefone),
            off_label=ai_window.get("off_label"),
            on_label=ai_window.get("on_label"),
        )
        _publish_skip(telefone, "ai_schedule_off", tenant_id=tenant_id)
        return

    if not telefone:
        log_event(
            "handler_incomplete_message",
            phone_hash=hash_phone(telefone),
            text=preview_text(texto),
            message_type=norm["message_type"],
        )
        _publish_skip(telefone, "incomplete_message", tenant_id=tenant_id)
        return

    if not texto:
        log_event(
            "handler_media_without_text",
            phone_hash=hash_phone(telefone),
            message_type=norm["message_type"],
        )
        await _send_message(
            responder_usuario_fn,
            telefone,
            (
                "Recebi sua mídia, mas ainda não consigo abrir áudios, fotos ou stickers "
                "por aqui 😊 Me conta em texto o que você está procurando?"
            ),
            role="bot",
            actor_label="Bot",
        )
        _publish_skip(telefone, "media_without_text_replied", tenant_id=tenant_id)
        return

    if is_phone_automation_disabled(telefone):
        log_event("handler_phone_automation_disabled", phone_hash=hash_phone(telefone), text=preview_text(texto))
        _publish_skip(telefone, "phone_automation_disabled", tenant_id=tenant_id)
        return

    if not should_track_phone(telefone):
        log_event("handler_test_phone_ignored", phone_hash=hash_phone(telefone))
        _publish_skip(telefone, "phone_not_tracked", tenant_id=tenant_id)
        return

    if is_phone_opted_out(telefone):
        now_for_opt_out = now_in_bot_timezone()
        opt_out_updated_at = get_phone_opted_out_updated_at(telefone)
        auto_resume_minutes = get_settings().phone_opt_out_auto_resume_minutes
        auto_reactivated = False
        if auto_resume_minutes > 0 and opt_out_updated_at is not None:
            elapsed_seconds = (now_for_opt_out - normalize_to_bot_timezone(opt_out_updated_at)).total_seconds()
            if elapsed_seconds >= auto_resume_minutes * 60:
                set_phone_opted_out(telefone, False)
                log_event(
                    "handler_phone_opt_out_auto_reactivated",
                    phone_hash=hash_phone(telefone),
                    threshold_minutes=auto_resume_minutes,
                    elapsed_minutes=round(elapsed_seconds / 60, 2),
                )
                auto_reactivated = True
        if not auto_reactivated:
            if texto in REATIVAR_BOT_OPCOES:
                set_phone_opted_out(telefone, False)
                reactivation_delay = get_settings().phone_opt_out_reactivation_delay_seconds
                if reactivation_delay > 0:
                    log_event(
                        "handler_phone_opt_out_reactivation_delay",
                        phone_hash=hash_phone(telefone),
                        delay_seconds=reactivation_delay,
                    )
                    await asyncio.sleep(reactivation_delay)
                await _send_message(
                    responder_usuario_fn,
                    telefone,
                    build_reactivation_message(),
                    role="bot",
                    actor_label="Bot",
                )
                log_event("handler_phone_opt_out_reactivated", phone_hash=hash_phone(telefone))
                return

            log_event("handler_phone_opt_out_active", phone_hash=hash_phone(telefone), text=preview_text(texto))
            _publish_skip(telefone, "phone_opt_out", tenant_id=tenant_id)
            return

    if texto in {"desativar chat", "desativar bot", "desligar chat", "desligar bot", "pausar chat", "pausar bot"}:
        set_phone_opted_out(telefone, True)
        await _send_message(
            responder_usuario_fn,
            telefone,
            OPT_OUT_MESSAGE,
            role="bot",
            actor_label="Bot",
        )
        log_event("handler_phone_opt_out_activated", phone_hash=hash_phone(telefone))
        return

    agora = now_in_bot_timezone()

    if msg_id and not mark_processed_message_if_new(msg_id, agora, ttl_seconds=MESSAGE_IDEMPOTENCY_TTL_SECONDS):
        log_event(
            "handler_duplicate_webhook",
            message_id=msg_id,
            phone_hash=hash_phone(telefone),
            duplicate_window_seconds=MESSAGE_IDEMPOTENCY_TTL_SECONDS,
        )
        log_event(
            "handler_duplicate_webhook_alert",
            message_id=msg_id,
            phone_hash=hash_phone(telefone),
            duplicate_window_seconds=MESSAGE_IDEMPOTENCY_TTL_SECONDS,
            severity="warning",
        )
        _publish_skip(telefone, "duplicate_webhook", tenant_id=tenant_id)
        return

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
        _publish_skip(telefone, "store_closed", tenant_id=tenant_id)
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
            ack_sent_at_raw = estado.get("pending_ack_at")
            ack_sent_at = None
            if ack_sent_at_raw:
                try:
                    ack_sent_at = normalize_to_bot_timezone(
                        datetime.fromisoformat(ack_sent_at_raw)
                    )
                except Exception:
                    ack_sent_at = None
            should_ack = ack_sent_at is None or (agora - ack_sent_at) > timedelta(minutes=15)
            if should_ack:
                estados_atendimento[telefone]["pending_ack_at"] = agora.isoformat()
                await _send_message(
                    responder_usuario_fn,
                    telefone,
                    HANDOFF_PENDING_ACK_MESSAGE,
                    role="bot",
                    actor_label="Bot",
                )
                log_event(
                    "handler_human_attention_ack_sent",
                    phone_hash=hash_phone(telefone),
                )
                _publish_skip(telefone, "handoff_active_acked", tenant_id=tenant_id)
                return
            log_event("handler_human_attention_active", phone_hash=hash_phone(telefone))
            _publish_skip(telefone, "handoff_active_silenced", tenant_id=tenant_id)
            return

    resposta_ia = await gerar_resposta_ia_fn(telefone, texto, nome_cliente, cliente_id)

    reply_hash = hashlib.sha1(
        (resposta_ia or "").strip().encode("utf-8"), usedforsecurity=False
    ).hexdigest()
    last_reply = get_recent_bot_reply(telefone)
    if last_reply and last_reply.get("hash") == reply_hash:
        try:
            last_at = normalize_to_bot_timezone(
                datetime.fromisoformat(last_reply.get("hora") or "")
            )
        except Exception:
            last_at = None
        if last_at and (agora - last_at).total_seconds() <= REPLY_DEDUPE_WINDOW_SECONDS:
            log_event(
                "handler_duplicate_ai_reply_skipped",
                phone_hash=hash_phone(telefone),
                window_seconds=REPLY_DEDUPE_WINDOW_SECONDS,
            )
            _publish_skip(telefone, "duplicate_ai_reply", tenant_id=tenant_id)
            return

    set_recent_bot_reply(telefone, reply_hash, agora)
    get_event_bus().publish(
        AiReplyGeneratedEvent(
            telefone=telefone,
            nome_cliente=nome_cliente,
            reply=resposta_ia,
            tenant_id=tenant_id,
        )
    )
    await _send_message(
        responder_usuario_fn,
        telefone,
        resposta_ia,
        role="ia",
        actor_label="IA",
    )
