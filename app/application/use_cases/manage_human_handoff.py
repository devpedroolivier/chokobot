from __future__ import annotations

import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock

from app.application.events import HumanHandoffEscalatedEvent
from app.application.service_registry import get_customer_process_repository, get_event_bus
from app.domain.repositories.customer_process_repository import CustomerProcessRecord
from app.observability import increment_counter, log_event
from app.services.commercial_rules import STORE_HOURS_SUMMARY
from app.services.estados import (
    estados_atendimento,
    estados_cafeteria,
    estados_cestas_box,
    estados_encomenda,
    estados_entrega,
    recent_messages,
)
from app.services.store_schedule import store_window_for_date
from app.settings import get_settings
from app.utils.datetime_utils import normalize_to_bot_timezone, now_in_bot_timezone
from app.welcome_message import BOT_REACTIVATED_MESSAGE, HUMAN_HANDOFF_MESSAGE

_DUPLICATE_HANDOFF_AUDIT_WINDOW = timedelta(minutes=10)
_KNOWLEDGE_FAILURE_WINDOW_STATE: dict[str, list[datetime]] = {}
_KNOWLEDGE_FAILURE_LAST_ALERT_AT: dict[str, datetime] = {}
_KNOWLEDGE_FAILURE_LOCK = RLock()
_ESCALATION_CATEGORIES = (
    "cliente_solicitou",
    "produto_fora_escopo",
    "falha_bot",
    "spam_fora_contexto",
    "assumido_painel",
)


def _handoff_audit_path() -> Path:
    return Path("dados/atendimentos.txt")


def register_handoff_audit(telefone: str, nome: str, motivo: str, categoria: str = "falha_bot") -> None:
    path = _handoff_audit_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        agora = now_in_bot_timezone().strftime("%d/%m/%Y %H:%M")
        linha = (
            f"{agora} - {nome} | {telefone} solicitou atendimento humano | "
            f"categoria={categoria} | motivo={motivo}\n"
        )
        with path.open("a", encoding="utf-8") as handle:
            handle.write(linha)
        log_event("human_handoff_audited", telefone=telefone, nome=nome, motivo=motivo, categoria=categoria)
    except OSError as exc:
        log_event(
            "human_handoff_audit_failed",
            telefone=telefone,
            nome=nome,
            motivo=motivo,
            error_type=type(exc).__name__,
        )


def _normalize_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    clean = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(clean.casefold().split())


def _resolve_escalation_source(motivo: str) -> str:
    normalized = _normalize_text(motivo)
    if "painel" in normalized:
        return "painel"
    if "cliente" in normalized or "humano" in normalized:
        return "ai"
    return "runtime"


def _classify_escalation_category(motivo: str) -> str:
    normalized = _normalize_text(motivo)
    if "assumido_pelo_painel" in normalized or "assumido pelo painel" in normalized:
        return "assumido_painel"
    if any(token in normalized for token in ("cliente pediu humano", "solicitado pelo cliente", "falar com humano")):
        return "cliente_solicitou"
    if any(token in normalized for token in ("spam", "teste", "flood", "ruido")):
        return "spam_fora_contexto"
    if any(token in normalized for token in ("fora de contexto", "fora de escopo", "produto fora", "nao encontrado")):
        return "produto_fora_escopo"
    if any(token in normalized for token in ("ovos pronta entrega", "pronta entrega exige atendimento humano")):
        return "produto_fora_escopo"
    return "falha_bot"


def _failure_topic_from_reason(motivo: str, categoria: str) -> str:
    normalized = _normalize_text(motivo)
    if categoria == "spam_fora_contexto":
        return "fora_contexto"
    if "pix" in normalized:
        return "pix"
    if "pascoa" in normalized:
        return "pascoa"
    if any(token in normalized for token in ("foto", "imagem", "catalogo")):
        return "catalogo_visual"
    if any(token in normalized for token in ("cesta", "presente", "flores", "caixinha")):
        return "presentes"
    if any(token in normalized for token in ("doces", "brigadeiro", "bombom")):
        return "doces"
    if any(token in normalized for token in ("combo", "cafeteria", "croissant", "capuccino", "cappuccino")):
        return "cafeteria"
    if "bolo" in normalized:
        return "bolos"
    return "geral"


def _record_failure_alert_if_needed(topic: str, *, now: datetime) -> None:
    settings = get_settings()
    threshold = max(1, settings.knowledge_failure_alert_threshold)
    window = timedelta(minutes=max(1, settings.knowledge_failure_alert_window_minutes))

    with _KNOWLEDGE_FAILURE_LOCK:
        samples = list(_KNOWLEDGE_FAILURE_WINDOW_STATE.get(topic, []))
        samples = [sample for sample in samples if (now - sample) <= window]
        samples.append(now)
        _KNOWLEDGE_FAILURE_WINDOW_STATE[topic] = samples

        if len(samples) < threshold:
            return

        last_alert = _KNOWLEDGE_FAILURE_LAST_ALERT_AT.get(topic)
        if last_alert is not None and (now - last_alert) <= window:
            return
        _KNOWLEDGE_FAILURE_LAST_ALERT_AT[topic] = now

    increment_counter("knowledge_failure_alert_total", topico=topic)
    log_event(
        "knowledge_failure_alert",
        level="WARNING",
        topico=topic,
        ocorrencias=len(samples),
        janela_minutos=int(window.total_seconds() // 60),
        threshold=threshold,
        webhook_configurado=bool(settings.knowledge_failure_alert_webhook),
    )
    if settings.knowledge_failure_alert_webhook:
        log_event(
            "knowledge_failure_alert_webhook_pending",
            level="WARNING",
            topico=topic,
            webhook_target="configured",
        )


def _record_escalation_metrics(
    *,
    handoff_started_at: datetime,
    categoria: str,
    origem: str,
    motivo: str,
) -> None:
    day = handoff_started_at.strftime("%Y-%m-%d")
    increment_counter("escalacao_total", categoria=categoria, dia=day, origem=origem)
    increment_counter("pedido_escalado_total", categoria=categoria, dia=day, origem=origem)

    if categoria in {"produto_fora_escopo", "falha_bot", "spam_fora_contexto"}:
        topic = _failure_topic_from_reason(motivo, categoria)
        increment_counter("falha_conhecimento_total", topico=topic, dia=day)
        _record_failure_alert_if_needed(topic, now=handoff_started_at)


def clear_customer_active_flows(telefone: str) -> None:
    for state_map in (estados_encomenda, estados_cafeteria, estados_entrega, estados_cestas_box):
        state_map.pop(telefone, None)


def _parse_state_timestamp(raw_value: str | None) -> datetime | None:
    if not raw_value:
        return None
    try:
        return normalize_to_bot_timezone(datetime.fromisoformat(raw_value))
    except ValueError:
        return None


def _is_duplicate_handoff_request(telefone: str, motivo: str, *, now: datetime) -> bool:
    current_state = estados_atendimento.get(telefone)
    if not current_state:
        return False
    if (current_state.get("motivo") or "").strip() != (motivo or "").strip():
        return False

    last_audit_at = _parse_state_timestamp(current_state.get("audit_at") or current_state.get("inicio"))
    if last_audit_at is None:
        return False
    return (now - last_audit_at) <= _DUPLICATE_HANDOFF_AUDIT_WINDOW


def _format_full_date(raw_value: str | None) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return value


def _build_process_summary(payload: dict) -> str:
    if payload.get("itens"):
        product = ", ".join(str(item) for item in payload.get("itens") if item)
    else:
        product = (
            payload.get("cesta_nome")
            or payload.get("produto")
            or payload.get("descricao")
            or payload.get("categoria")
            or ""
        ).strip()

    parts = [product]
    if payload.get("data_entrega") or payload.get("data"):
        parts.append(_format_full_date(payload.get("data_entrega") or payload.get("data")))
    if payload.get("horario_retirada") or payload.get("horario"):
        parts.append((payload.get("horario_retirada") or payload.get("horario") or "").strip())
    return " • ".join(part for part in parts if part)


def _process_missing_items(process_type: str, stage: str, payload: dict) -> list[str]:
    missing: list[str] = []

    if process_type == "cafeteria_order":
        if not payload.get("itens") and not payload.get("descricao"):
            missing.append("Itens")
        if stage == "montando_pedido":
            missing.append("Finalizacao do pedido")
        return missing

    if process_type == "cesta_box_order":
        if not payload.get("cesta_nome") and not payload.get("descricao"):
            missing.append("Cesta")
        if not (payload.get("modo_recebimento") or "").strip():
            missing.append("Modo de recebimento")

    if not (payload.get("data_entrega") or payload.get("data")):
        missing.append("Data")
    if not (payload.get("horario_retirada") or payload.get("horario")):
        missing.append("Horario")

    payment = payload.get("pagamento") or {}
    payment_method = (payment.get("forma") or payload.get("forma_pagamento") or "").strip()
    if not payment_method or payment_method.casefold() == "pendente":
        missing.append("Pagamento")

    if process_type in {"delivery_order", "cesta_box_order", "ai_cake_order", "ai_sweet_order", "ai_cafeteria_order"} and (
        (payload.get("modo_recebimento") or "entrega").strip().casefold() == "entrega"
        and not (payload.get("endereco") or "").strip()
    ):
        missing.append("Endereco")

    if stage == "aguardando_confirmacao" and not missing:
        missing.append("Confirmacao final")

    return missing


def _resolve_next_step_hint(process_type: str, stage: str, missing_items: list[str]) -> str:
    if stage == "pagamento_pendente":
        return "Cobrar pagamento e comprovante"
    if stage == "aguardando_confirmacao":
        return "Confirmar resumo final com o cliente"
    if missing_items:
        return "Completar dados faltantes antes de concluir o pedido"
    if process_type.startswith("ai_"):
        return "Revisar o rascunho da IA e concluir manualmente se necessario"
    return "Assumir atendimento e concluir o fluxo com o cliente"


def _infer_risk_flags(process: CustomerProcessRecord, missing_items: list[str]) -> list[str]:
    risk_flags: list[str] = []
    if process.process_type.startswith("ai_"):
        risk_flags.append("rascunho_ia")
    if process.order_id is None and process.stage != "pedido_confirmado":
        risk_flags.append("nao_confirmado")
    if process.stage == "aguardando_confirmacao":
        risk_flags.append("aguardando_confirmacao")
    if missing_items:
        risk_flags.append("dados_incompletos")
    return risk_flags


def _existing_active_process(
    telefone: str,
    *,
    process_repository,
) -> CustomerProcessRecord | None:
    lister = getattr(process_repository, "list_active_processes", None)
    if not callable(lister):
        return None
    for process in lister():
        if process.phone != telefone:
            continue
        if process.process_type == "human_handoff" or process.stage == "handoff_humano":
            continue
        return process
    return None


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        items.append(normalized)
    return items


def _truncate_summary(value: str, *, limit: int = 120) -> str:
    clean = " ".join(str(value or "").strip().split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _next_business_opening(reference: datetime) -> tuple[datetime, str] | None:
    for offset in range(0, 14):
        candidate = reference + timedelta(days=offset)
        window = store_window_for_date(candidate.date())
        if window is None:
            continue
        opening = datetime.combine(candidate.date(), datetime.strptime(window[0], "%H:%M").time())
        opening = opening.replace(tzinfo=reference.tzinfo)
        if offset == 0 and reference.time() <= opening.time():
            return opening, window[0]
        if offset > 0:
            return opening, window[0]
    return None


def _handoff_expectation_message(reference: datetime) -> str:
    window = store_window_for_date(reference.date())
    if window is not None and window[0] <= reference.strftime("%H:%M") <= window[1]:
        return (
            "Respondemos em ate 20 minutos no horario comercial "
            f"({STORE_HOURS_SUMMARY})"
        )

    next_open = _next_business_opening(reference)
    if next_open is None:
        return f"Estamos fora do horario comercial agora ({STORE_HOURS_SUMMARY})"

    opening_at, opening_hour = next_open
    weekday = opening_at.strftime("%d/%m/%Y")
    return (
        "Estamos fora do horario comercial agora. "
        f"Nosso proximo atendimento comeca em {weekday} as {opening_hour} "
        f"({STORE_HOURS_SUMMARY})"
    )


def _build_handoff_customer_message(handoff_context: dict, *, now: datetime) -> str:
    summary = _truncate_summary(str(handoff_context.get("resumo") or ""))
    if not summary:
        summary = _truncate_summary(str(handoff_context.get("ultima_mensagem_cliente") or ""))

    expected = _handoff_expectation_message(now)
    if summary:
        return (
            f"Entendi que voce quer: {summary}. "
            f"Estou transferindo voce para nossa equipe humana agora. {expected}."
        )
    return (
        "Estou transferindo voce para nossa equipe humana agora. "
        f"{expected}."
    )


def _build_handoff_context(
    telefone: str,
    *,
    process_repository,
    context: dict | None,
) -> dict:
    explicit_context = dict(context or {})
    active_process = _existing_active_process(telefone, process_repository=process_repository)
    last_customer_message = str((recent_messages.get(telefone) or {}).get("texto") or "").strip()

    if active_process is None:
        return {
            "resumo": str(explicit_context.get("resumo") or "").strip(),
            "ultima_mensagem_cliente": str(
                explicit_context.get("ultima_mensagem_cliente") or last_customer_message
            ).strip(),
            "faltando": _unique_strings([str(item) for item in explicit_context.get("faltando") or []]),
            "proximo_passo": str(explicit_context.get("proximo_passo") or "").strip(),
            "risk_flags": _unique_strings([str(item) for item in explicit_context.get("risk_flags") or []]),
        }

    missing_items = _process_missing_items(active_process.process_type, active_process.stage, active_process.draft_payload)
    source_summary = _build_process_summary(active_process.draft_payload)
    context_missing = _unique_strings(
        [*missing_items, *[str(item) for item in explicit_context.get("faltando") or []]]
    )
    context_risk_flags = _unique_strings(
        [*_infer_risk_flags(active_process, missing_items), *[str(item) for item in explicit_context.get("risk_flags") or []]]
    )

    return {
        "resumo": str(explicit_context.get("resumo") or source_summary).strip(),
        "ultima_mensagem_cliente": str(
            explicit_context.get("ultima_mensagem_cliente") or last_customer_message
        ).strip(),
        "faltando": context_missing,
        "proximo_passo": str(
            explicit_context.get("proximo_passo")
            or _resolve_next_step_hint(active_process.process_type, active_process.stage, missing_items)
        ).strip(),
        "risk_flags": context_risk_flags,
        "source_process_type": active_process.process_type,
        "source_stage": active_process.stage,
        "source_order_id": active_process.order_id,
    }


def activate_human_handoff(
    telefone: str,
    *,
    nome: str = "Cliente",
    motivo: str = "solicitado_pelo_cliente",
    context: dict | None = None,
    audit_writer=register_handoff_audit,
    process_repository=None,
    now: datetime | None = None,
) -> str:
    handoff_started_at = normalize_to_bot_timezone(now)
    categoria = _classify_escalation_category(motivo)
    origem = _resolve_escalation_source(motivo)
    if categoria not in _ESCALATION_CATEGORIES:
        categoria = "falha_bot"
    is_duplicate_request = _is_duplicate_handoff_request(telefone, motivo, now=handoff_started_at)

    if audit_writer is not None and not is_duplicate_request:
        audit_writer(telefone, nome, motivo, categoria)

    clear_customer_active_flows(telefone)
    process_repository = process_repository or get_customer_process_repository()
    handoff_context = _build_handoff_context(telefone, process_repository=process_repository, context=context)
    process_repository.upsert_process(
        phone=telefone,
        process_type="human_handoff",
        stage="handoff_humano",
        status="active",
        source="human_handoff",
        draft_payload={
            "nome": nome,
            "motivo": motivo,
            "categoria": categoria,
            "origem": origem,
            "duplicated_request": is_duplicate_request,
            "contexto": handoff_context,
        },
    )
    estados_atendimento[telefone] = {
        "humano": True,
        "inicio": handoff_started_at.isoformat(),
        "audit_at": handoff_started_at.isoformat(),
        "nome": nome,
        "motivo": motivo,
        "categoria": categoria,
        "origem": origem,
        "contexto_resumo": handoff_context.get("resumo") or "",
        "proximo_passo": handoff_context.get("proximo_passo") or "",
    }
    if not is_duplicate_request:
        _record_escalation_metrics(
            handoff_started_at=handoff_started_at,
            categoria=categoria,
            origem=origem,
            motivo=motivo,
        )
        get_event_bus().publish(
            HumanHandoffEscalatedEvent(
                phone=telefone,
                nome=nome,
                motivo=motivo,
                categoria=categoria,
                origem=origem,
            )
        )
    log_event(
        "human_handoff_activated",
        telefone=telefone,
        nome=nome,
        motivo=motivo,
        categoria=categoria,
        origem=origem,
        duplicate=is_duplicate_request,
        contexto_resumo=handoff_context.get("resumo") or "",
        risk_flags=handoff_context.get("risk_flags") or [],
    )
    message = _build_handoff_customer_message(handoff_context, now=handoff_started_at)
    return message or HUMAN_HANDOFF_MESSAGE


def deactivate_human_handoff(telefone: str, *, process_repository=None) -> bool:
    existed = telefone in estados_atendimento
    estados_atendimento.pop(telefone, None)
    process_repository = process_repository or get_customer_process_repository()
    existing_process = process_repository.get_process(telefone, "human_handoff")
    if existing_process is not None:
        process_repository.upsert_process(
            phone=telefone,
            customer_id=existing_process.customer_id,
            process_type="human_handoff",
            stage="bot_reativado",
            status="resolved",
            source=existing_process.source or "human_handoff",
            draft_payload={
                **existing_process.draft_payload,
                "encerrado_em": now_in_bot_timezone().isoformat(),
            },
            order_id=existing_process.order_id,
        )
    log_event("human_handoff_deactivated", telefone=telefone, existed=existed)
    return existed


def build_reactivation_message(*, include_menu: bool = False) -> str:
    if not include_menu:
        return BOT_REACTIVATED_MESSAGE
    return (
        f"{BOT_REACTIVATED_MESSAGE}\n"
        "Se quiser, podemos continuar por aqui:\n"
        "1️⃣ Ver cardápio\n2️⃣ Encomendar bolos\n3️⃣ Pedidos da cafeteria\n4️⃣ Entregas\n5️⃣ Falar com atendente"
    )
