from __future__ import annotations

from app.ai.agents import AGENTS_MAP
from app.ai.tools import (
    CakeOrderSchema,
    SweetOrderSchema,
    save_cake_order_draft_process,
    save_sweet_order_draft_process,
)
from app.observability import increment_counter, log_event
from app.welcome_message import HUMAN_HANDOFF_MESSAGE

_CONFIRMATION_MARKERS = (
    "confirmo",
    "pode fechar",
    "pode confirmar",
    "sim, confirma",
    "sim confirma",
    "sim, pode",
    "sim pode",
    "pedido confirmado",
    "pode salvar",
    "fechado",
)


def _latest_user_message(session: dict) -> str:
    for message in reversed(session.get("messages", [])):
        if message.get("role") == "user" and message.get("content"):
            return str(message["content"]).strip()
    return ""


def _has_explicit_confirmation(session: dict) -> bool:
    content = _latest_user_message(session).casefold()
    if not content:
        return False
    if any(marker in content for marker in _CONFIRMATION_MARKERS):
        return True
    return content.strip(" .!?") == "sim"


def _is_saved_order_result(tool_result: str) -> bool:
    return tool_result.startswith("Pedido salvo com sucesso!") or tool_result.startswith(
        "Pedido de doces salvo com sucesso!"
    )


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
) -> tuple[bool, str]:
    tool_result = ""

    if function_name == "transfer_to_agent":
        new_agent = arguments.get("agent_name")
        if new_agent in AGENTS_MAP:
            session["current_agent"] = new_agent
            tool_result = f"Sucesso. Conversa transferida para o {new_agent}."
            save_session_fn(telefone, session)
        else:
            tool_result = f"Erro: Agente {new_agent} não existe."
    elif function_name == "get_menu":
        tool_result = runtime.get_menu(arguments.get("category", "todas"))
    elif function_name == "get_learnings":
        tool_result = runtime.get_learnings()
    elif function_name == "save_learning":
        tool_result = runtime.save_learning(arguments.get("aprendizado"))
    elif function_name == "escalate_to_human":
        runtime.escalate_to_human(telefone, arguments.get("motivo", "Solicitado pelo cliente"))
        session["messages"] = []
        save_session_fn(telefone, session)
        return True, HUMAN_HANDOFF_MESSAGE
    elif function_name == "create_cake_order":
        try:
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
                    session["messages"] = []
                    save_session_fn(telefone, session)
                    return True, f"✅ O seu pedido foi finalizado e salvo no nosso sistema! {tool_result}"
        except Exception as exc:
            tool_result = f"Erro ao salvar pedido: Falta de campos ou dados inválidos -> {str(exc)}"
    elif function_name == "create_sweet_order":
        try:
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
                    session["messages"] = []
                    save_session_fn(telefone, session)
                    return True, f"✅ O seu pedido foi finalizado e salvo no nosso sistema! {tool_result}"
        except Exception as exc:
            tool_result = f"Erro ao salvar pedido: Falta de campos ou dados inválidos -> {str(exc)}"

    return False, str(tool_result)
