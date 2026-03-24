from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from app.application.service_registry import get_customer_process_repository
from app.observability import log_event
from app.services.estados import (
    estados_atendimento,
    estados_cafeteria,
    estados_cestas_box,
    estados_encomenda,
    estados_entrega,
)
from app.welcome_message import BOT_REACTIVATED_MESSAGE, HUMAN_HANDOFF_MESSAGE

_DUPLICATE_HANDOFF_AUDIT_WINDOW = timedelta(minutes=10)


def _handoff_audit_path() -> Path:
    return Path("dados/atendimentos.txt")


def register_handoff_audit(telefone: str, nome: str, motivo: str) -> None:
    path = _handoff_audit_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
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
        return datetime.fromisoformat(raw_value)
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


def activate_human_handoff(
    telefone: str,
    *,
    nome: str = "Cliente",
    motivo: str = "solicitado_pelo_cliente",
    audit_writer=register_handoff_audit,
    process_repository=None,
    now: datetime | None = None,
) -> str:
    handoff_started_at = now or datetime.now()
    is_duplicate_request = _is_duplicate_handoff_request(telefone, motivo, now=handoff_started_at)

    if audit_writer is not None and not is_duplicate_request:
        audit_writer(telefone, nome, motivo)

    clear_customer_active_flows(telefone)
    process_repository = process_repository or get_customer_process_repository()
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
        },
    )
    estados_atendimento[telefone] = {
        "humano": True,
        "inicio": handoff_started_at.isoformat(),
        "audit_at": handoff_started_at.isoformat(),
        "nome": nome,
        "motivo": motivo,
    }
    log_event(
        "human_handoff_activated",
        telefone=telefone,
        nome=nome,
        motivo=motivo,
        duplicate=is_duplicate_request,
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
                "encerrado_em": datetime.now().isoformat(),
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
