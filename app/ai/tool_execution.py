from __future__ import annotations

from datetime import datetime
import re
import unicodedata

from app.ai.agents import AGENTS_MAP
from app.ai.tools import (
    CafeteriaOrderSchema,
    CakeOrderSchema,
    GiftOrderSchema,
    SweetOrderSchema,
    save_cafeteria_order_draft_process,
    save_cake_order_draft_process,
    save_gift_order_draft_process,
    save_sweet_order_draft_process,
)
from app.observability import increment_counter, log_event
from app.services.store_schedule import format_service_date, parse_service_date, resolve_service_date_reference
from app.welcome_message import HUMAN_HANDOFF_MESSAGE

_CONFIRMATION_MARKERS = (
    "sim",
    "ok",
    "ta",
    "ta bom",
    "certo",
    "confirmado",
    "confirma",
    "perfeito",
    "beleza",
    "isso",
    "confirmo",
    "sim confirma",
    "sim pode",
    "fechado",
)
_CONFIRMATION_PHRASE_MARKERS = (
    "pode fechar",
    "pode confirmar",
    "pedido confirmado",
    "pode salvar",
)
_SIM_POLITE_SUFFIXES = {
    "obrigada",
    "obrigado",
    "obg",
    "valeu",
    "brigada",
    "brigado",
}

_TRANSFER_MESSAGES = {
    "CakeOrderAgent": (
        "Transferencia interna concluida para CakeOrderAgent. "
        "Continue a partir da ultima mensagem do cliente e responda diretamente, "
        "sem avisar novamente que houve transferencia."
    ),
    "SweetOrderAgent": (
        "Transferencia interna concluida para SweetOrderAgent. "
        "Continue a partir da ultima mensagem do cliente e responda diretamente, "
        "sem avisar novamente que houve transferencia."
    ),
    "CafeteriaAgent": (
        "Transferencia interna concluida para CafeteriaAgent. "
        "Atenda a ultima mensagem do cliente agora, consultando pronta entrega/cafeteria quando necessario, "
        "e responda diretamente sem avisar novamente que houve transferencia."
    ),
    "GiftOrderAgent": (
        "Transferencia interna concluida para GiftOrderAgent. "
        "Continue a partir da ultima mensagem do cliente e atenda presentes regulares diretamente, "
        "sem avisar novamente que houve transferencia."
    ),
    "KnowledgeAgent": (
        "Transferencia interna concluida para KnowledgeAgent. "
        "Continue a partir da ultima mensagem do cliente e responda diretamente, "
        "sem avisar novamente que houve transferencia."
    ),
}


def _latest_user_message(session: dict) -> str:
    for message in reversed(session.get("messages", [])):
        if message.get("role") == "user" and message.get("content"):
            return str(message["content"]).strip()
    return ""


def _normalize_confirmation_content(content: str) -> str:
    normalized = unicodedata.normalize("NFKD", content or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char)).casefold()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _has_explicit_confirmation(session: dict) -> bool:
    content = _normalize_confirmation_content(_latest_user_message(session))
    if not content:
        return False

    if re.search(r"\bnao\b", content):
        return False

    if content in _CONFIRMATION_MARKERS:
        return True

    if any(marker in content for marker in _CONFIRMATION_PHRASE_MARKERS):
        return True

    if content.startswith("sim "):
        suffix = content[4:].strip()
        if suffix in _SIM_POLITE_SUFFIXES:
            return True

    return False


def _is_saved_order_result(tool_result: str) -> bool:
    return (
        tool_result.startswith("Pedido salvo com sucesso!")
        or tool_result.startswith("Pedido de doces salvo com sucesso!")
        or tool_result.startswith("Pedido cafeteria salvo com sucesso!")
        or tool_result.startswith("Pedido presente salvo com sucesso!")
    )


def _transfer_message_for_agent(agent_name: str | None) -> str:
    return _TRANSFER_MESSAGES.get(
        agent_name or "",
        (
            "Transferencia interna concluida para o agente correto. "
            "Continue a partir da ultima mensagem do cliente e responda diretamente."
        ),
    )


def _reset_session(session: dict) -> None:
    session["messages"] = []
    session.pop("seasonal_context", None)
    session.pop("service_date_context", None)
    session.pop("conversation_correction_context", None)


def _resolved_service_date_from_session(session: dict) -> str | None:
    context = session.get("service_date_context") or {}
    return str(context.get("date") or "").strip() or None


def _apply_service_date_resolution(arguments: dict, session: dict, now: datetime | None = None) -> None:
    if "data_entrega" not in arguments:
        return

    raw_argument = arguments.get("data_entrega")
    resolved_from_argument = resolve_service_date_reference(raw_argument, now)
    resolved_from_session = parse_service_date(_resolved_service_date_from_session(session))

    final_date = None
    if resolved_from_session is not None:
        final_date = resolved_from_session
    elif resolved_from_argument is not None:
        final_date = resolved_from_argument

    if final_date is not None:
        arguments["data_entrega"] = format_service_date(final_date)


def _strip_removed_additional_from_description(description: str, removed_additional: str) -> str:
    updated = description or ""
    escaped = re.escape(removed_additional)
    patterns = (
        rf"\s*\+\s*{escaped}\b",
        rf"\s*e\s+adicional\s+de\s+{escaped}\b",
        rf"\s*com\s+adicional\s+{escaped}\b",
        rf"\s*adicional\s*[:\-]?\s*{escaped}\b",
    )
    for pattern in patterns:
        updated = re.sub(pattern, "", updated, flags=re.IGNORECASE)
    updated = re.sub(r"\s{2,}", " ", updated).strip(" ,+-")
    return updated or description


def _apply_conversation_correction_resolution(arguments: dict, session: dict) -> None:
    correction_context = session.get("conversation_correction_context") or {}
    if not correction_context:
        return

    mode = (correction_context.get("modo_recebimento") or "").strip().lower()
    if mode in {"retirada", "entrega"}:
        arguments["modo_recebimento"] = mode
        if mode == "retirada":
            arguments["endereco"] = None
            if "taxa_entrega" in arguments:
                arguments["taxa_entrega"] = 0.0

    payment_form = (correction_context.get("pagamento_forma") or "").strip()
    if payment_form:
        payment_payload = dict(arguments.get("pagamento") or {})
        payment_payload["forma"] = payment_form
        if payment_form == "Dinheiro":
            payment_payload["troco_para"] = correction_context.get("troco_para")
            payment_payload["parcelas"] = None
        elif payment_form == "Cartão (débito/crédito)":
            payment_payload["troco_para"] = None
            payment_payload["parcelas"] = correction_context.get("parcelas")
        else:
            payment_payload["troco_para"] = None
            payment_payload["parcelas"] = None
        arguments["pagamento"] = payment_payload

    pickup_time = (correction_context.get("horario_retirada") or "").strip()
    if pickup_time:
        arguments["horario_retirada"] = pickup_time

    removed_additional = (correction_context.get("removed_adicional") or "").strip()
    if removed_additional and str(arguments.get("adicional") or "").casefold() == removed_additional.casefold():
        arguments["adicional"] = None
        description = arguments.get("descricao")
        if isinstance(description, str) and description.strip():
            arguments["descricao"] = _strip_removed_additional_from_description(description, removed_additional)


def handle_tool_call(
    *,
    runtime,
    function_name: str,
    arguments: dict,
    telefone: str,
    nome_cliente: str,
    cliente_id: int,
    session: dict,
    save_session_fn,
    now: datetime | None = None,
) -> tuple[bool, str]:
    tool_result = ""

    if function_name == "transfer_to_agent":
        new_agent = arguments.get("agent_name")
        if new_agent in AGENTS_MAP:
            session["current_agent"] = new_agent
            tool_result = _transfer_message_for_agent(new_agent)
            save_session_fn(telefone, session)
            return False, tool_result
        else:
            tool_result = f"Erro: Agente {new_agent} não existe."
    elif function_name == "get_menu":
        tool_result = runtime.get_menu(arguments.get("category", "todas"))
    elif function_name == "lookup_catalog_items":
        lookup_fn = getattr(runtime, "lookup_catalog_items", None)
        if lookup_fn is None:
            tool_result = "Busca estruturada de catalogo indisponivel neste runtime."
        else:
            tool_result = lookup_fn(arguments.get("query", ""), arguments.get("catalog", "auto"))
    elif function_name == "get_cake_pricing":
        pricing_fn = getattr(runtime, "get_cake_pricing", None)
        if pricing_fn is None:
            tool_result = "Consulta canonica de preco de bolo indisponivel neste runtime."
        else:
            tool_result = pricing_fn(
                arguments.get("category", "tradicional"),
                arguments.get("tamanho"),
                arguments.get("produto"),
                arguments.get("adicional"),
                arguments.get("cobertura"),
                arguments.get("kit_festou", False),
                arguments.get("quantidade", 1),
            )
    elif function_name == "get_cake_options":
        tool_result = runtime.get_cake_options(
            arguments.get("category", "tradicional"),
            arguments.get("option_type", "recheio"),
        )
    elif function_name == "get_learnings":
        tool_result = runtime.get_learnings()
    elif function_name == "save_learning":
        tool_result = runtime.save_learning(arguments.get("aprendizado"))
    elif function_name == "escalate_to_human":
        runtime.escalate_to_human(telefone, arguments.get("motivo", "Solicitado pelo cliente"))
        _reset_session(session)
        save_session_fn(telefone, session)
        return True, HUMAN_HANDOFF_MESSAGE
    elif function_name == "create_cake_order":
        try:
            _apply_service_date_resolution(arguments, session, now)
            _apply_conversation_correction_resolution(arguments, session)
            order = CakeOrderSchema(**arguments)
            if not _has_explicit_confirmation(session):
                increment_counter(
                    "ai_order_confirmation_blocks_total",
                    tool_name=function_name,
                    agent=session.get("current_agent", "unknown"),
                )
                log_event(
                    "ai_order_confirmation_blocked",
                    tool_name=function_name,
                    agent=session.get("current_agent"),
                    phone_hash=telefone[-4:] if telefone else "anon",
                )
                tool_result = save_cake_order_draft_process(telefone, nome_cliente, cliente_id, order)
            else:
                tool_result = runtime.create_cake_order(telefone, nome_cliente, cliente_id, order)
                if _is_saved_order_result(str(tool_result)):
                    _reset_session(session)
                    save_session_fn(telefone, session)
                    return True, f"✅ O seu pedido foi finalizado e salvo no nosso sistema! {tool_result}"
        except Exception as exc:
            tool_result = f"Erro ao salvar pedido: Falta de campos ou dados inválidos -> {str(exc)}"
    elif function_name == "create_sweet_order":
        try:
            _apply_service_date_resolution(arguments, session, now)
            _apply_conversation_correction_resolution(arguments, session)
            order = SweetOrderSchema(**arguments)
            if not _has_explicit_confirmation(session):
                increment_counter(
                    "ai_order_confirmation_blocks_total",
                    tool_name=function_name,
                    agent=session.get("current_agent", "unknown"),
                )
                log_event(
                    "ai_order_confirmation_blocked",
                    tool_name=function_name,
                    agent=session.get("current_agent"),
                    phone_hash=telefone[-4:] if telefone else "anon",
                )
                tool_result = save_sweet_order_draft_process(telefone, nome_cliente, cliente_id, order)
            else:
                tool_result = runtime.create_sweet_order(telefone, nome_cliente, cliente_id, order)
                if _is_saved_order_result(str(tool_result)):
                    _reset_session(session)
                    save_session_fn(telefone, session)
                    return True, f"✅ O seu pedido foi finalizado e salvo no nosso sistema! {tool_result}"
        except Exception as exc:
            tool_result = f"Erro ao salvar pedido: Falta de campos ou dados inválidos -> {str(exc)}"
    elif function_name == "create_cafeteria_order":
        try:
            _apply_service_date_resolution(arguments, session, now)
            _apply_conversation_correction_resolution(arguments, session)
            order = CafeteriaOrderSchema(**arguments)
            if not _has_explicit_confirmation(session):
                increment_counter(
                    "ai_order_confirmation_blocks_total",
                    tool_name=function_name,
                    agent=session.get("current_agent", "unknown"),
                )
                log_event(
                    "ai_order_confirmation_blocked",
                    tool_name=function_name,
                    agent=session.get("current_agent"),
                    phone_hash=telefone[-4:] if telefone else "anon",
                )
                tool_result = save_cafeteria_order_draft_process(telefone, nome_cliente, cliente_id, order)
            else:
                cafeteria_fn = getattr(runtime, "create_cafeteria_order", None)
                if cafeteria_fn is None:
                    tool_result = "Fluxo estruturado de cafeteria indisponivel neste runtime."
                else:
                    tool_result = cafeteria_fn(telefone, nome_cliente, cliente_id, order)
                    if _is_saved_order_result(str(tool_result)):
                        _reset_session(session)
                        save_session_fn(telefone, session)
                        return True, f"✅ O seu pedido foi finalizado e salvo no nosso sistema! {tool_result}"
        except Exception as exc:
            tool_result = f"Erro ao salvar pedido: Falta de campos ou dados inválidos -> {str(exc)}"
    elif function_name == "create_gift_order":
        try:
            _apply_service_date_resolution(arguments, session, now)
            _apply_conversation_correction_resolution(arguments, session)
            order = GiftOrderSchema(**arguments)
            if not _has_explicit_confirmation(session):
                increment_counter(
                    "ai_order_confirmation_blocks_total",
                    tool_name=function_name,
                    agent=session.get("current_agent", "unknown"),
                )
                log_event(
                    "ai_order_confirmation_blocked",
                    tool_name=function_name,
                    agent=session.get("current_agent"),
                    phone_hash=telefone[-4:] if telefone else "anon",
                )
                tool_result = save_gift_order_draft_process(telefone, nome_cliente, cliente_id, order)
            else:
                gift_fn = getattr(runtime, "create_gift_order", None)
                if gift_fn is None:
                    tool_result = "Fluxo estruturado de presentes regulares indisponivel neste runtime."
                else:
                    tool_result = gift_fn(telefone, nome_cliente, cliente_id, order)
                    if _is_saved_order_result(str(tool_result)):
                        _reset_session(session)
                        save_session_fn(telefone, session)
                        return True, f"✅ O seu pedido foi finalizado e salvo no nosso sistema! {tool_result}"
        except Exception as exc:
            tool_result = f"Erro ao salvar pedido: Falta de campos ou dados inválidos -> {str(exc)}"

    return False, str(tool_result)
