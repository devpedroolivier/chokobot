from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from app.application.service_registry import get_customer_process_repository
from app.domain.repositories.customer_process_repository import CustomerProcessRecord
from app.observability import log_event
from app.services.estados import (
    estados_atendimento,
    estados_cafeteria,
    estados_cestas_box,
    estados_encomenda,
    estados_entrega,
    recent_messages,
)
from app.utils.datetime_utils import normalize_to_bot_timezone, now_in_bot_timezone
from app.welcome_message import BOT_REACTIVATED_MESSAGE, HUMAN_HANDOFF_MESSAGE

_DUPLICATE_HANDOFF_AUDIT_WINDOW = timedelta(minutes=10)


def _handoff_audit_path() -> Path:
    return Path("dados/atendimentos.txt")


def register_handoff_audit(telefone: str, nome: str, motivo: str) -> None:
    path = _handoff_audit_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        agora = now_in_bot_timezone().strftime("%d/%m/%Y %H:%M")
        linha = f"{agora} - {nome} | {telefone} solicitou atendimento humano | motivo={motivo}\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(linha)
        log_event("human_handoff_audited", telefone=telefone, nome=nome, motivo=motivo)
    except OSError as exc:
        log_event(
            "human_handoff_audit_failed",
            telefone=telefone,
            nome=nome,
            motivo=motivo,
            error_type=type(exc).__name__,
        )


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

    if process_type in {"delivery_order", "cesta_box_order", "ai_cake_order", "ai_sweet_order"} and (
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
    is_duplicate_request = _is_duplicate_handoff_request(telefone, motivo, now=handoff_started_at)

    if audit_writer is not None and not is_duplicate_request:
        audit_writer(telefone, nome, motivo)

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
        "contexto_resumo": handoff_context.get("resumo") or "",
        "proximo_passo": handoff_context.get("proximo_passo") or "",
    }
    log_event(
        "human_handoff_activated",
        telefone=telefone,
        nome=nome,
        motivo=motivo,
        duplicate=is_duplicate_request,
        contexto_resumo=handoff_context.get("resumo") or "",
        risk_flags=handoff_context.get("risk_flags") or [],
    )
    return HUMAN_HANDOFF_MESSAGE


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
