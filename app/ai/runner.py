import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

try:
    from openai import AsyncOpenAI
except ModuleNotFoundError:
    AsyncOpenAI = None

from app.ai.agents import AGENTS_MAP, TriageAgent
from app.ai.policies import (
    build_cafeteria_specificity_retry_instruction as _build_cafeteria_specificity_retry_instruction,
    build_system_time_context,
    build_time_conflict_retry_instruction as _build_time_conflict_retry_instruction,
    response_conflicts_with_cafeteria_specificity as _response_conflicts_with_cafeteria_specificity,
    current_local_datetime,
    normalize_reference_time as _normalize_reference_time,
    requests_easter_catalog as _requests_easter_catalog,
    requests_human_handoff as _requests_human_handoff,
    response_conflicts_with_cutoff as _response_conflicts_with_cutoff,
    should_force_same_day_cafeteria_handoff as _should_force_same_day_cafeteria_handoff,
)
from app.ai.tool_execution import handle_tool_call
from app.ai.tool_registry import build_openai_tools
from app.welcome_message import EASTER_CATALOG_MESSAGE, HUMAN_HANDOFF_MESSAGE
from app.ai.tools import (
    create_cafeteria_order,
    create_cake_order,
    create_sweet_order,
    escalate_to_human,
    get_cake_options,
    get_cake_pricing,
    get_learnings,
    get_menu,
    lookup_catalog_items,
    save_learning,
)
from app.observability import increment_counter, log_event, observe_duration
from app.services.estados import ai_sessions
from app.settings import get_settings

client = None

CONVERSATIONS = ai_sessions


@dataclass(frozen=True)
class AIRuntime:
    get_menu: Any
    get_cake_options: Any
    get_learnings: Any
    save_learning: Any
    escalate_to_human: Any
    create_cake_order: Any
    create_sweet_order: Any
    create_cafeteria_order: Any | None = None
    lookup_catalog_items: Any | None = None
    get_cake_pricing: Any | None = None


def get_default_ai_runtime() -> AIRuntime:
    return AIRuntime(
        get_menu=get_menu,
        lookup_catalog_items=lookup_catalog_items,
        get_cake_pricing=get_cake_pricing,
        get_cake_options=get_cake_options,
        get_learnings=get_learnings,
        save_learning=save_learning,
        escalate_to_human=escalate_to_human,
        create_cake_order=create_cake_order,
        create_sweet_order=create_sweet_order,
        create_cafeteria_order=create_cafeteria_order,
    )


def build_ai_client(api_key: str | None = None):
    settings = get_settings()
    resolved_api_key = api_key if api_key is not None else settings.openai_api_key
    if AsyncOpenAI is None or not resolved_api_key:
        return None
    return AsyncOpenAI(api_key=resolved_api_key)


def get_ai_client():
    global client
    if client is None:
        client = build_ai_client()
    return client


def set_ai_client(ai_client) -> None:
    global client
    client = ai_client


def reset_ai_client() -> None:
    set_ai_client(None)


def _assistant_message_to_dict(message) -> dict:
    payload = {
        "role": getattr(message, "role", "assistant"),
        "content": getattr(message, "content", None),
    }
    tool_calls = []
    for tool_call in getattr(message, "tool_calls", []) or []:
        tool_calls.append(
            {
                "id": tool_call.id,
                "type": getattr(tool_call, "type", "function"),
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
        )
    if tool_calls:
        payload["tool_calls"] = tool_calls
    return payload


def _sanitize_session_messages(messages: list[dict]) -> tuple[list[dict], int]:
    cleaned: list[dict] = []
    pending_assistant: dict | None = None
    pending_tools: list[dict] = []
    expected_tool_ids: set[str] = set()
    dropped_messages = 0

    for message in messages:
        role = message.get("role")

        if pending_assistant is not None:
            if role == "tool" and message.get("tool_call_id") in expected_tool_ids:
                pending_tools.append(message)
                expected_tool_ids.discard(message["tool_call_id"])
                if not expected_tool_ids:
                    cleaned.append(pending_assistant)
                    cleaned.extend(pending_tools)
                    pending_assistant = None
                    pending_tools = []
                continue

            dropped_messages += 1 + len(pending_tools)
            pending_assistant = None
            pending_tools = []
            expected_tool_ids = set()

        if role == "assistant" and message.get("tool_calls"):
            tool_ids = {tool_call.get("id") for tool_call in message.get("tool_calls", []) if tool_call.get("id")}
            if tool_ids:
                pending_assistant = message
                expected_tool_ids = tool_ids
                pending_tools = []
                continue

        if role == "tool":
            dropped_messages += 1
            continue

        cleaned.append(message)

    if pending_assistant is not None:
        dropped_messages += 1 + len(pending_tools)

    return cleaned, dropped_messages


def save_session(telefone: str, session: dict) -> None:
    CONVERSATIONS[telefone] = session

def get_or_create_session(telefone: str) -> Dict[str, Any]:
    session = CONVERSATIONS.get(telefone)
    if session is None:
        session = {
            "messages": [],
            "current_agent": "TriageAgent",
        }
        save_session(telefone, session)
    else:
        sanitized_messages, dropped_messages = _sanitize_session_messages(list(session.get("messages", [])))
        if dropped_messages:
            session["messages"] = sanitized_messages
            save_session(telefone, session)
    return session


def _should_repeat_easter_catalog_link(session: dict, text: str) -> bool:
    if session.get("seasonal_context") != "easter":
        return False

    normalized = (text or "").strip().casefold()
    if not normalized:
        return False

    link_patterns = (
        "cardapio",
        "cardápio",
        "catalogo",
        "catálogo",
        "menu",
        "link",
        "manda",
        "me envia",
        "me envia o link",
    )

    return any(pattern in normalized for pattern in link_patterns)


def _is_draft_order_result(tool_result: str | None) -> bool:
    normalized = (tool_result or "").casefold()
    return normalized.startswith("resumo final do pedido") and (
        "ainda nao foi salvo como pedido confirmado no sistema." in normalized
    )


def _response_claims_order_saved(reply: str | None) -> bool:
    normalized = (reply or "").casefold()
    patterns = (
        "pedido foi salvo",
        "seu pedido foi salvo",
        "pedido salvo",
        "pedido finalizado",
        "seu pedido esta garantido",
        "seu pedido estará garantido",
        "pedido confirmado no sistema",
    )
    return any(pattern in normalized for pattern in patterns)


def _latest_draft_tool_result(session: dict) -> str | None:
    for message in reversed(session.get("messages", [])):
        if message.get("role") != "tool":
            continue
        content = str(message.get("content") or "")
        if _is_draft_order_result(content):
            return content
    return None

# Mapeamento de funções reais para as definições de Tools da OpenAI
def get_openai_tools(agent, runtime: AIRuntime | None = None):
    runtime = runtime or get_default_ai_runtime()
    return build_openai_tools(agent, runtime)


def build_system_instructions(agent, now: datetime | None = None, runtime: AIRuntime | None = None) -> str:
    runtime = runtime or get_default_ai_runtime()
    system_time_context = build_system_time_context(now)
    instructions = agent.instructions + f"\n\n[CONTEXTO DO SISTEMA: {system_time_context}]"
    learnings = runtime.get_learnings()
    if learnings:
        instructions += f"\n\nREGRAS APRENDIDAS ANTERIORMENTE:\n{learnings}"
    return instructions


def bootstrap_session(session: dict, now: datetime | None = None, runtime: AIRuntime | None = None) -> None:
    agent = AGENTS_MAP.get(session["current_agent"], TriageAgent)
    session["messages"].append({"role": "system", "content": build_system_instructions(agent, now, runtime)})


def refresh_system_prompt(session: dict, agent, now: datetime | None = None, runtime: AIRuntime | None = None) -> None:
    if session["messages"] and session["messages"][0]["role"] == "system":
        session["messages"][0]["content"] = build_system_instructions(agent, now, runtime)


async def request_ai_completion(ai_client, *, messages: list[dict], tools_config: list[dict]):
    return await ai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=tools_config if tools_config else None,
        tool_choice="auto" if tools_config else "none",
        temperature=0.1,
    )


def _finalize_ai_run(*, start_time: float, session: dict, iteration_count: int, prompt_tokens: int, completion_tokens: int) -> None:
    end_time = time.time()
    observe_duration("ai_run_duration_seconds", end_time - start_time, agent=session["current_agent"])
    increment_counter("ai_runs_total", stage="completed", agent=session["current_agent"])
    log_event(
        "ai_run_completed",
        agent=session["current_agent"],
        iterations=iteration_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


async def process_message_with_ai(
    telefone: str,
    text: str,
    nome_cliente: str,
    cliente_id: int,
    now: datetime | None = None,
    ai_client=None,
    runtime: AIRuntime | None = None,
) -> str:
    """Função principal que o handler vai chamar para processar a mensagem pela IA."""
    start_time = time.time()
    session = get_or_create_session(telefone)
    runtime = runtime or get_default_ai_runtime()
    active_client = ai_client or get_ai_client()

    sanitized_messages, dropped_messages = _sanitize_session_messages(list(session.get("messages", [])))
    if dropped_messages:
        session["messages"] = sanitized_messages
        save_session(telefone, session)
        log_event(
            "ai_session_history_repaired",
            phone_hash=telefone[-4:] if telefone else "anon",
            agent=session.get("current_agent", "unknown"),
            dropped_messages=dropped_messages,
        )
    
    if not session["messages"]:
        bootstrap_session(session, now, runtime)
        save_session(telefone, session)
    
    # Adiciona a mensagem do usuário
    session["messages"].append({"role": "user", "content": text})
    save_session(telefone, session)

    if _requests_human_handoff(text):
        runtime.escalate_to_human(telefone, "Cliente pediu humano")
        session["messages"] = []
        session.pop("seasonal_context", None)
        save_session(telefone, session)
        increment_counter("ai_human_guard_handoffs_total", agent=session["current_agent"])
        log_event("ai_human_guard_handoff", phone_hash=telefone[-4:] if telefone else "anon", agent=session["current_agent"])
        return HUMAN_HANDOFF_MESSAGE

    if _requests_easter_catalog(text):
        session["seasonal_context"] = "easter"
        save_session(telefone, session)
        log_event("ai_easter_catalog_link_sent", phone_hash=telefone[-4:] if telefone else "anon")
        return EASTER_CATALOG_MESSAGE

    if _should_repeat_easter_catalog_link(session, text):
        log_event("ai_easter_catalog_context_followup", phone_hash=telefone[-4:] if telefone else "anon")
        return EASTER_CATALOG_MESSAGE

    if _should_force_same_day_cafeteria_handoff(session, text, now):
        previous_agent = session["current_agent"]
        session["current_agent"] = "CafeteriaAgent"
        refresh_system_prompt(session, AGENTS_MAP["CafeteriaAgent"], now, runtime)
        save_session(telefone, session)
        increment_counter("ai_time_guard_handoffs_total", from_agent=previous_agent, to_agent="CafeteriaAgent")
        log_event(
            "ai_time_guard_handoff",
            from_agent=previous_agent,
            to_agent="CafeteriaAgent",
            phone_hash=telefone[-4:] if telefone else "anon",
            current_time=_normalize_reference_time(now).strftime("%Y-%m-%d %H:%M:%S %z"),
        )
    
    log_event("ai_run_started", phone_hash=telefone[-4:] if telefone else "anon", agent=session["current_agent"])
    increment_counter("ai_runs_total", stage="started", agent=session["current_agent"])
    
    total_prompt_tokens = 0
    total_completion_tokens = 0
    iteration_count = 0
    time_conflict_retry_used = False
    cafeteria_specificity_retry_used = False
    transient_system_note = None

    if active_client is None:
        return "Integracao de IA indisponivel no ambiente atual. Instale a dependencia 'openai' para ativar esse fluxo."

    # Loop de raciocínio da IA
    while True:
        iteration_count += 1
        current_agent_name = session["current_agent"]
        agent = AGENTS_MAP.get(current_agent_name, TriageAgent)
        
        refresh_system_prompt(session, agent, now, runtime)
        save_session(telefone, session)
            
        tools_config = get_openai_tools(agent, runtime)
        request_messages = list(session["messages"])
        if transient_system_note:
            request_messages.append({"role": "system", "content": transient_system_note})

        response = await request_ai_completion(active_client, messages=request_messages, tools_config=tools_config)
        transient_system_note = None
        
        # Coleta métricas de tokens
        if response.usage:
            total_prompt_tokens += response.usage.prompt_tokens
            total_completion_tokens += response.usage.completion_tokens
            
        msg = response.choices[0].message
        assistant_message = _assistant_message_to_dict(msg)

        if (
            not msg.tool_calls
            and not time_conflict_retry_used
            and _response_conflicts_with_cutoff(msg.content, user_text=text, now=now)
        ):
            time_conflict_retry_used = True
            transient_system_note = _build_time_conflict_retry_instruction(now)
            increment_counter("ai_time_guard_retries_total", agent=session["current_agent"])
            log_event(
                "ai_time_guard_retry",
                agent=session["current_agent"],
                phone_hash=telefone[-4:] if telefone else "anon",
                current_time=_normalize_reference_time(now).strftime("%Y-%m-%d %H:%M:%S %z"),
            )
            continue

        if (
            not msg.tool_calls
            and not cafeteria_specificity_retry_used
            and _response_conflicts_with_cafeteria_specificity(
                msg.content,
                user_text=text,
                current_agent=current_agent_name,
            )
        ):
            cafeteria_specificity_retry_used = True
            transient_system_note = _build_cafeteria_specificity_retry_instruction(text)
            increment_counter("ai_cafeteria_specificity_retries_total", agent=session["current_agent"])
            log_event(
                "ai_cafeteria_specificity_retry",
                agent=session["current_agent"],
                phone_hash=telefone[-4:] if telefone else "anon",
            )
            continue

        session["messages"].append(assistant_message)
        save_session(telefone, session)
        
        # Se a IA respondeu com texto final
        if not msg.tool_calls:
            if _response_claims_order_saved(msg.content):
                draft_tool_result = _latest_draft_tool_result(session)
                if draft_tool_result:
                    log_event(
                        "ai_persistence_claim_blocked",
                        agent=session["current_agent"],
                        phone_hash=telefone[-4:] if telefone else "anon",
                        reason="draft_process_only",
                    )
                    increment_counter(
                        "ai_persistence_claim_blocks_total",
                        agent=session["current_agent"],
                        reason="draft_process_only",
                    )
                    _finalize_ai_run(
                        start_time=start_time,
                        session=session,
                        iteration_count=iteration_count,
                        prompt_tokens=total_prompt_tokens,
                        completion_tokens=total_completion_tokens,
                    )
                    return draft_tool_result
            _finalize_ai_run(
                start_time=start_time,
                session=session,
                iteration_count=iteration_count,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
            )
            return msg.content
            
        # Se a IA decidiu chamar uma ferramenta
        for tool_call in msg.tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            increment_counter("ai_tool_calls_total", tool_name=function_name, agent=session["current_agent"])
            log_event("ai_tool_called", tool_name=function_name, agent=session["current_agent"])
            should_return, tool_result = handle_tool_call(
                runtime=runtime,
                function_name=function_name,
                arguments=arguments,
                telefone=telefone,
                nome_cliente=nome_cliente,
                cliente_id=cliente_id,
                session=session,
                save_session_fn=save_session,
            )
            if should_return:
                if function_name == "transfer_to_agent":
                    log_event("ai_handoff", to_agent=session["current_agent"])
                return tool_result

            if function_name == "transfer_to_agent":
                log_event("ai_handoff", to_agent=session["current_agent"])

            # Adiciona o resultado da ferramenta na memória para a IA "ler"
            session["messages"].append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": str(tool_result)
            })
            save_session(telefone, session)

            if _is_draft_order_result(str(tool_result)):
                log_event(
                    "ai_draft_order_response_short_circuit",
                    agent=session["current_agent"],
                    phone_hash=telefone[-4:] if telefone else "anon",
                    tool_name=function_name,
                )
                _finalize_ai_run(
                    start_time=start_time,
                    session=session,
                    iteration_count=iteration_count,
                    prompt_tokens=total_prompt_tokens,
                    completion_tokens=total_completion_tokens,
                )
                return str(tool_result)
