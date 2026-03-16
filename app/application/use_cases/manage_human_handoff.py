from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.observability import log_event
from app.services.estados import (
    estados_atendimento,
    estados_cafeteria,
    estados_cestas_box,
    estados_encomenda,
    estados_entrega,
)
from app.welcome_message import BOT_REACTIVATED_MESSAGE, HUMAN_HANDOFF_MESSAGE


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


def activate_human_handoff(
    telefone: str,
    *,
    nome: str = "Cliente",
    motivo: str = "solicitado_pelo_cliente",
    audit_writer=register_handoff_audit,
) -> str:
    if audit_writer is not None:
        audit_writer(telefone, nome, motivo)

    clear_customer_active_flows(telefone)
    estados_atendimento[telefone] = {
        "humano": True,
        "inicio": datetime.now().isoformat(),
        "nome": nome,
        "motivo": motivo,
    }
    log_event("human_handoff_activated", telefone=telefone, nome=nome, motivo=motivo)
    return HUMAN_HANDOFF_MESSAGE


def deactivate_human_handoff(telefone: str) -> bool:
    existed = telefone in estados_atendimento
    estados_atendimento.pop(telefone, None)
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
