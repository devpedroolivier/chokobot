import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict

try:
    from openai import AsyncOpenAI
except ModuleNotFoundError:
    AsyncOpenAI = None

from app.ai.agents import AGENTS_MAP, TriageAgent
from app.ai.policies import (
    caseirinho_clarification_message as _caseirinho_clarification_message,
    build_conversation_correction_instruction,
    build_cafeteria_specificity_retry_instruction as _build_cafeteria_specificity_retry_instruction,
    build_service_date_memory_instruction,
    build_system_time_context,
    build_time_conflict_retry_instruction as _build_time_conflict_retry_instruction,
    response_conflicts_with_cafeteria_specificity as _response_conflicts_with_cafeteria_specificity,
    current_local_datetime,
    normalize_intent_text,
    normalize_reference_time as _normalize_reference_time,
    requests_easter_catalog as _requests_easter_catalog,
    requests_catalog_photo as _requests_catalog_photo,
    requests_easter_date_info as _requests_easter_date_info,
    requests_easter_ready_delivery_handoff as _requests_easter_ready_delivery_handoff,
    requests_post_purchase_topic as _requests_post_purchase_topic,
    requests_regular_gift_topic as _requests_regular_gift_topic,
    should_force_basic_context_switch as _should_force_basic_context_switch,
    requests_human_handoff as _requests_human_handoff,
    is_generic_greeting as _is_generic_greeting,
    requests_opt_out as _requests_opt_out,
    response_conflicts_with_cutoff as _response_conflicts_with_cutoff,
    should_force_same_day_cafeteria_handoff as _should_force_same_day_cafeteria_handoff,
)
from app.application.service_registry import get_customer_repository
from app.services.store_schedule import resolve_service_date_context
from app.services.store_schedule import easter_date_message
from app.ai.tool_execution import handle_tool_call
from app.ai.tool_registry import build_openai_tools
from app.welcome_message import EASTER_CATALOG_MESSAGE, HUMAN_HANDOFF_MESSAGE, OPT_OUT_MESSAGE, WELCOME_MESSAGE
from app.ai.tools import (
    create_cafeteria_order,
    create_cake_order,
    create_gift_order,
    create_sweet_order,
    escalate_to_human,
    get_cake_options,
    get_cake_pricing,
    get_learnings,
    get_menu,
    lookup_catalog_items,
    save_learning,
)
from app.ai.order_support import DEFAULT_ORDER_SUPPORT, OrderSupportService
from app.observability import increment_counter, log_event, normalize_reason_label, observe_duration, should_track_phone
from app.services.estados import ai_sessions
from app.settings import get_settings

client = None

CONVERSATIONS = ai_sessions
_KNOWN_CUSTOMER_WINDOW = timedelta(minutes=5)
_PAYMENT_FORMS = {
    "pix": "PIX",
    "cartao": "Cartão (débito/crédito)",
    "cartao debito": "Cartão (débito/crédito)",
    "cartao credito": "Cartão (débito/crédito)",
    "credito": "Cartão (débito/crédito)",
    "debito": "Cartão (débito/crédito)",
    "dinheiro": "Dinheiro",
}
_REMOVABLE_ADDITIONALS = ("morango", "ameixa", "nozes", "cereja", "abacaxi")

POST_PURCHASE_MESSAGES = {
    "status": (
        "Para acompanhar o status do seu pedido, informe o telefone ou o nome usado e a data desejada. "
        "O painel operacional acompanha as etapas pendente, em preparo, pronto para retirada e entregue, "
        "então a resposta oficial vem da equipe humana em poucos minutos."
    ),
    "pix": (
        "Se quiser confirmar o PIX, envie o comprovante em imagem com o valor e a chave usada. "
        "O financeiro valida o pagamento e informa assim que o valor for reconhecido no sistema."
    ),
    "cancel": (
        "Para cancelar, nos diga o número do pedido, o motivo e a data desejada. "
        "Se o pedido ainda estiver em coleta, conseguimos cancelar no painel; caso contrário, a equipe humana revisará."
    ),
    "invoice": (
        "Para pedir a nota fiscal, confirme CPF ou CNPJ e o número do pedido. "
        "A nota é emitida após a confirmação do pagamento e enviada por e-mail em até um dia útil."
    ),
}


def _catalog_photo_reply() -> str:
    link = get_settings().catalog_link
    if link:
        return (
            "Perfeito! Para ver as fotos, nosso catálogo visual está aqui:\n"
            f"{link}\n\n"
            "Me diz qual item você gostou que eu te ajudo a fechar o pedido 😊"
        )
    return (
        "Consigo te ajudar com os detalhes por aqui 😊 "
        "Se quiser fotos, te conecto com a equipe para te enviar o catálogo visual."
    )


def _first_name(nome_cliente: str | None) -> str | None:
    raw = str(nome_cliente or "").strip()
    if not raw:
        return None
    if raw.casefold() in {"nome nao informado", "nome não informado"}:
        return None
    return raw.split()[0]


def _is_known_customer(telefone: str, now: datetime | None = None) -> bool:
    if not telefone:
        return False
    customer = get_customer_repository().get_customer_by_phone(telefone)
    if customer is None:
        return False
    created_at_raw = str(customer.criado_em or "").strip()
    if not created_at_raw:
        return True
    try:
        created_at = datetime.fromisoformat(created_at_raw)
    except ValueError:
        try:
            created_at = datetime.strptime(created_at_raw, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return True
    reference_time = _normalize_reference_time(now)
    created_at_local = _normalize_reference_time(created_at)
    return (reference_time - created_at_local) >= _KNOWN_CUSTOMER_WINDOW


def _known_customer_greeting(nome_cliente: str) -> str:
    first_name = _first_name(nome_cliente)
    if first_name:
        return f"Ola {first_name}! Como posso ajudar hoje? 😊"
    return "Ola! Como posso ajudar hoje? 😊"


def _followup_after_greeting() -> str:
    return "Me conta qual produto voce quer hoje e eu te ajudo a fechar rapidinho."


def _should_record_for_phone(telefone: str | None) -> bool:
    return should_track_phone(telefone)


def _maybe_increment_counter(telefone: str | None, name: str, **labels) -> None:
    if not _should_record_for_phone(telefone):
        return
    increment_counter(name, **labels)


def _maybe_log_event(telefone: str | None, event: str, **fields) -> None:
    if not _should_record_for_phone(telefone):
        return
    log_event(event, **fields)


def _phone_hash(telefone: str | None) -> str:
    return telefone[-4:] if telefone else "anon"


def _record_human_handoff_metrics(
    telefone: str | None,
    agent: str,
    reason_label: str,
    event_name: str,
) -> None:
    normalized_reason = normalize_reason_label(reason_label)
    _maybe_increment_counter(
        telefone,
        "ai_human_guard_handoffs_total",
        agent=agent,
        reason=normalized_reason,
    )
    _maybe_log_event(
        telefone,
        event_name,
        agent=agent,
        handoff_reason=normalized_reason,
        phone_hash=_phone_hash(telefone),
    )


def _respond_with_order_support(topic: str, telefone: str | None, service: OrderSupportService) -> str:
    handled, message, failure_reason = service.handle(topic, telefone)
    outcome = "success" if handled else "failure"
    failure_label = "success" if handled else normalize_reason_label(failure_reason)
    _maybe_increment_counter(
        telefone,
        "ai_post_purchase_fallback_total",
        topic=topic,
        outcome=outcome,
        failure_reason=failure_label,
    )
    _maybe_log_event(
        telefone,
        "ai_post_purchase_flow_result",
        topic=topic,
        outcome=outcome,
        failure_reason=failure_label,
        phone_hash=_phone_hash(telefone),
    )
    return message or POST_PURCHASE_MESSAGES.get(topic, "")


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
    create_gift_order: Any | None = None
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
        create_gift_order=create_gift_order,
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


def _update_service_date_context(session: dict, text: str, now: datetime | None = None) -> None:
    resolved_context = resolve_service_date_context(text, now)
    if resolved_context is not None:
        session["service_date_context"] = resolved_context


def _conversation_service_date_instruction(session: dict) -> str | None:
    return build_service_date_memory_instruction(session.get("service_date_context"))


def _extract_payment_form(normalized_text: str) -> str | None:
    for token, payment_form in _PAYMENT_FORMS.items():
        if re.search(rf"\b{re.escape(token)}\b", normalized_text):
            return payment_form
    return None


def _extract_mode_recebimento(normalized_text: str) -> str | None:
    if re.search(r"\b(retir(ar|o|ada)|buscar|busca|vou buscar|iremos buscar)\b", normalized_text):
        return "retirada"
    if re.search(r"\b(quero q entrega|quero entrega|pode entregar|manda entregar|entregar|delivery)\b", normalized_text):
        return "entrega"
    if re.search(r"\b(data|horario|horario da|taxa)\s+de\s+entrega\b", normalized_text):
        return None
    if re.search(r"\bentrega\b", normalized_text):
        return "entrega"
    return None


def _extract_hour_reference(text: str) -> str | None:
    match = re.search(r"\b(\d{1,2})[:h](\d{2})\b", text or "", flags=re.IGNORECASE)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return None


def _extract_removed_additional(normalized_text: str) -> str | None:
    for additional in _REMOVABLE_ADDITIONALS:
        if re.search(rf"\b(tirar|tirando|remove|remover|sem)\b.*\b{re.escape(additional)}\b", normalized_text):
            return additional.title()
    return None


def _extract_cash_change_amount(normalized_text: str) -> float | None:
    match = re.search(r"\btroco\s+para\s+(\d+(?:[.,]\d{1,2})?)\b", normalized_text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _extract_installments(normalized_text: str) -> int | None:
    match = re.search(r"\b(?:em\s*)?(\d+)x\b", normalized_text)
    if not match:
        match = re.search(r"\b(\d+)\s+vezes\b", normalized_text)
    if match:
        try:
            value = int(match.group(1))
            return value if value > 1 else None
        except ValueError:
            return None
    if "parcelado" in normalized_text or "parcelar" in normalized_text:
        return 2
    return None


def _update_conversation_correction_context(session: dict, text: str) -> None:
    normalized = normalize_intent_text(text)
    if not normalized.strip():
        return

    updates: dict[str, Any] = {}

    mode = _extract_mode_recebimento(normalized)
    if mode:
        updates["modo_recebimento"] = mode

    payment_form = _extract_payment_form(normalized)
    if payment_form:
        updates["pagamento_forma"] = payment_form
        updates["troco_para"] = _extract_cash_change_amount(normalized) if payment_form == "Dinheiro" else None
        updates["parcelas"] = _extract_installments(normalized) if payment_form == "Cartão (débito/crédito)" else None

    pickup_time = _extract_hour_reference(text)
    if pickup_time:
        updates["horario_retirada"] = pickup_time

    removed_additional = _extract_removed_additional(normalized)
    if removed_additional:
        updates["removed_adicional"] = removed_additional

    if not updates:
        return

    correction_context = dict(session.get("conversation_correction_context") or {})
    correction_context.update(updates)
    correction_context["latest_source_text"] = text.strip()
    session["conversation_correction_context"] = correction_context


def _conversation_correction_instruction(session: dict) -> str | None:
    return build_conversation_correction_instruction(session.get("conversation_correction_context"))


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


def _finalize_ai_run(
    *,
    start_time: float,
    session: dict,
    iteration_count: int,
    prompt_tokens: int,
    completion_tokens: int,
    telefone: str | None,
) -> None:
    end_time = time.time()
    if _should_record_for_phone(telefone):
        observe_duration("ai_run_duration_seconds", end_time - start_time, agent=session["current_agent"])
    _maybe_increment_counter(
        telefone,
        "ai_runs_total",
        stage="completed",
        agent=session["current_agent"],
    )
    _maybe_log_event(
        telefone,
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
    order_support_service: OrderSupportService | None = None,
) -> str:
    """Função principal que o handler vai chamar para processar a mensagem pela IA.
    A camada de suporte transacional pode ser substituída via `order_support_service` para testes ou adapters."""
    start_time = time.time()
    session = get_or_create_session(telefone)
    runtime = runtime or get_default_ai_runtime()
    active_client = ai_client or get_ai_client()
    support_service = order_support_service or DEFAULT_ORDER_SUPPORT

    sanitized_messages, dropped_messages = _sanitize_session_messages(list(session.get("messages", [])))
    if dropped_messages:
        session["messages"] = sanitized_messages
        save_session(telefone, session)
        _maybe_log_event(
            telefone,
            "ai_session_history_repaired",
            phone_hash=telefone[-4:] if telefone else "anon",
            agent=session.get("current_agent", "unknown"),
            dropped_messages=dropped_messages,
        )
    
    if not session["messages"]:
        bootstrap_session(session, now, runtime)
        save_session(telefone, session)

    if _is_generic_greeting(text) and session.get("current_agent") == "TriageAgent":
        session["messages"].append({"role": "user", "content": text})
        greeting_already_sent = bool(session.get("greeting_sent"))
        known_customer = _is_known_customer(telefone, now)
        if greeting_already_sent:
            reply = _followup_after_greeting()
        else:
            reply = _known_customer_greeting(nome_cliente) if known_customer else WELCOME_MESSAGE
            session["greeting_sent"] = True
        session["messages"].append({"role": "assistant", "content": reply})
        save_session(telefone, session)
        _maybe_log_event(
            telefone,
            "ai_greeting_sent",
            phone_hash=_phone_hash(telefone),
            short=bool(greeting_already_sent or known_customer),
        )
        return reply

    # Adiciona a mensagem do usuário
    session["messages"].append({"role": "user", "content": text})
    _update_service_date_context(session, text, now)
    _update_conversation_correction_context(session, text)
    save_session(telefone, session)

    if _requests_opt_out(text):
        previous_agent = session.get("current_agent", "TriageAgent")
        session["current_agent"] = "TriageAgent"
        session["messages"] = []
        session.pop("seasonal_context", None)
        session.pop("service_date_context", None)
        session.pop("conversation_correction_context", None)
        session.pop("greeting_sent", None)
        save_session(telefone, session)
        _maybe_increment_counter(telefone, "ai_opt_out_requests_total", agent=previous_agent)
        _maybe_log_event(
            telefone,
            "ai_opt_out_requested",
            previous_agent=previous_agent,
            phone_hash=telefone[-4:] if telefone else "anon",
        )
        return OPT_OUT_MESSAGE

    if _requests_catalog_photo(text):
        _maybe_log_event(
            telefone,
            "ai_catalog_link_sent",
            phone_hash=_phone_hash(telefone),
        )
        return _catalog_photo_reply()

    if _requests_easter_date_info(text):
        _maybe_log_event(
            telefone,
            "ai_easter_date_answered",
            phone_hash=_phone_hash(telefone),
        )
        return easter_date_message(now)

    post_purchase_topic = _requests_post_purchase_topic(text)
    if post_purchase_topic:
        _maybe_increment_counter(
            telefone,
            "ai_post_purchase_flows_total",
            topic=post_purchase_topic,
        )
        _maybe_log_event(
            telefone,
            "ai_post_purchase_flow",
            topic=post_purchase_topic,
            phone_hash=_phone_hash(telefone),
        )
        return _respond_with_order_support(post_purchase_topic, telefone, support_service)

    caseirinho_clarification = _caseirinho_clarification_message(text)
    if caseirinho_clarification:
        previous_agent = session.get("current_agent", "TriageAgent")
        if previous_agent != "CakeOrderAgent":
            session["current_agent"] = "CakeOrderAgent"
            refresh_system_prompt(session, AGENTS_MAP["CakeOrderAgent"], now, runtime)
            save_session(telefone, session)
        _maybe_increment_counter(
            telefone,
            "ai_caseirinho_clarifications_total",
            from_agent=previous_agent,
        )
        _maybe_log_event(
            telefone,
            "ai_caseirinho_clarification_prompted",
            from_agent=previous_agent,
            phone_hash=_phone_hash(telefone),
        )
        return caseirinho_clarification

    if _requests_human_handoff(text):
        previous_agent = session.get("current_agent", "TriageAgent")
        handoff_message = runtime.escalate_to_human(telefone, "Cliente pediu humano")
        session["messages"] = []
        session.pop("seasonal_context", None)
        session.pop("service_date_context", None)
        session.pop("conversation_correction_context", None)
        session.pop("greeting_sent", None)
        save_session(telefone, session)
        _record_human_handoff_metrics(
            telefone,
            previous_agent,
            "customer_request",
            "ai_human_guard_handoff",
        )
        return handoff_message if isinstance(handoff_message, str) and handoff_message.strip() and handoff_message.strip().casefold() != "ok" else HUMAN_HANDOFF_MESSAGE

    if _requests_easter_ready_delivery_handoff(text):
        previous_agent = session.get("current_agent", "TriageAgent")
        handoff_message = runtime.escalate_to_human(telefone, "Ovos pronta entrega exigem atendimento humano")
        session["messages"] = []
        session.pop("seasonal_context", None)
        session.pop("service_date_context", None)
        session.pop("conversation_correction_context", None)
        session.pop("greeting_sent", None)
        save_session(telefone, session)
        _record_human_handoff_metrics(
            telefone,
            previous_agent,
            "easter_ready_delivery",
            "ai_easter_ready_delivery_handoff",
        )
        return handoff_message if isinstance(handoff_message, str) and handoff_message.strip() and handoff_message.strip().casefold() != "ok" else HUMAN_HANDOFF_MESSAGE

    if _requests_easter_catalog(text):
        session["seasonal_context"] = "easter"
        save_session(telefone, session)
        _maybe_log_event(
            telefone,
            "ai_easter_catalog_link_sent",
            phone_hash=telefone[-4:] if telefone else "anon",
        )
        return EASTER_CATALOG_MESSAGE

    if _should_repeat_easter_catalog_link(session, text):
        _maybe_log_event(
            telefone,
            "ai_easter_catalog_context_followup",
            phone_hash=telefone[-4:] if telefone else "anon",
        )
        return EASTER_CATALOG_MESSAGE

    # Interceptor para presentes (QW1)
    if _requests_regular_gift_topic(text) and session.get("current_agent") == "TriageAgent":
        session["current_agent"] = "GiftOrderAgent"
        refresh_system_prompt(session, AGENTS_MAP["GiftOrderAgent"], now, runtime)
        save_session(telefone, session)
        _maybe_log_event(
            telefone,
            "ai_gift_interceptor_handoff",
            from_agent="TriageAgent",
            to_agent="GiftOrderAgent",
            phone_hash=telefone[-4:] if telefone else "anon",
        )

    forced_same_day_cafeteria = False
    if _should_force_same_day_cafeteria_handoff(session, text, now):
        previous_agent = session["current_agent"]
        session["current_agent"] = "CafeteriaAgent"
        refresh_system_prompt(session, AGENTS_MAP["CafeteriaAgent"], now, runtime)
        save_session(telefone, session)
        forced_same_day_cafeteria = True
        _maybe_increment_counter(
            telefone,
            "ai_time_guard_handoffs_total",
            from_agent=previous_agent,
            to_agent="CafeteriaAgent",
        )
        _maybe_log_event(
            telefone,
            "ai_time_guard_handoff",
            from_agent=previous_agent,
            to_agent="CafeteriaAgent",
            phone_hash=telefone[-4:] if telefone else "anon",
            current_time=_normalize_reference_time(now).strftime("%Y-%m-%d %H:%M:%S %z"),
        )

    forced_agent = None if forced_same_day_cafeteria else _should_force_basic_context_switch(session, text)
    if forced_agent:
        previous_agent = session["current_agent"]
        session["current_agent"] = forced_agent
        refresh_system_prompt(session, AGENTS_MAP[forced_agent], now, runtime)
        save_session(telefone, session)
        _maybe_increment_counter(
            telefone,
            "ai_context_switch_handoffs_total",
            from_agent=previous_agent,
            to_agent=forced_agent,
        )
        _maybe_log_event(
            telefone,
            "ai_context_switch_handoff",
            from_agent=previous_agent,
            to_agent=forced_agent,
            phone_hash=telefone[-4:] if telefone else "anon",
            topic=forced_agent,
        )
    
    _maybe_log_event(
        telefone,
        "ai_run_started",
        phone_hash=telefone[-4:] if telefone else "anon",
        agent=session["current_agent"],
    )
    _maybe_increment_counter(telefone, "ai_runs_total", stage="started", agent=session["current_agent"])
    
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
        service_date_instruction = _conversation_service_date_instruction(session)
        if service_date_instruction:
            request_messages.append({"role": "system", "content": service_date_instruction})
        correction_instruction = _conversation_correction_instruction(session)
        if correction_instruction:
            request_messages.append({"role": "system", "content": correction_instruction})
        if transient_system_note:
            request_messages.append({"role": "system", "content": transient_system_note})
        history_count = sum(1 for message in session.get("messages", []) if message.get("role") in {"user", "assistant"})
        _maybe_log_event(
            telefone,
            "ai_history_loaded",
            phone_hash=_phone_hash(telefone),
            agent=session.get("current_agent"),
            history_messages=history_count,
            request_messages=len(request_messages),
        )

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
            _maybe_increment_counter(
                telefone,
                "ai_time_guard_retries_total",
                agent=session["current_agent"],
            )
            _maybe_log_event(
                telefone,
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
            _maybe_increment_counter(
                telefone,
                "ai_cafeteria_specificity_retries_total",
                agent=session["current_agent"],
            )
            _maybe_log_event(
                telefone,
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
                    _maybe_log_event(
                        telefone,
                        "ai_persistence_claim_blocked",
                        agent=session["current_agent"],
                        phone_hash=telefone[-4:] if telefone else "anon",
                        reason="draft_process_only",
                    )
                    _maybe_increment_counter(
                        telefone,
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
                        telefone=telefone,
                    )
                    return draft_tool_result
            _finalize_ai_run(
                start_time=start_time,
                session=session,
                iteration_count=iteration_count,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                telefone=telefone,
            )
            return msg.content
            
        # Se a IA decidiu chamar uma ferramenta
        for tool_call in msg.tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            _maybe_increment_counter(
                telefone,
                "ai_tool_calls_total",
                tool_name=function_name,
                agent=session["current_agent"],
            )
            _maybe_log_event(
                telefone,
                "ai_tool_called",
                tool_name=function_name,
                agent=session["current_agent"],
                phone_hash=telefone[-4:] if telefone else "anon",
            )
            should_return, tool_result = handle_tool_call(
                runtime=runtime,
                function_name=function_name,
                arguments=arguments,
                telefone=telefone,
                nome_cliente=nome_cliente,
                cliente_id=cliente_id,
                session=session,
                save_session_fn=save_session,
                now=now,
            )
            if should_return:
                if function_name == "transfer_to_agent":
                    _maybe_log_event(
                        telefone,
                        "ai_handoff",
                        to_agent=session["current_agent"],
                        phone_hash=telefone[-4:] if telefone else "anon",
                    )
                return tool_result

            if function_name == "transfer_to_agent":
                _maybe_log_event(
                    telefone,
                    "ai_handoff",
                    to_agent=session["current_agent"],
                    phone_hash=telefone[-4:] if telefone else "anon",
                )

            # Adiciona o resultado da ferramenta na memória para a IA "ler"
            session["messages"].append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": str(tool_result)
            })
            save_session(telefone, session)

            if _is_draft_order_result(str(tool_result)):
                _maybe_log_event(
                    telefone,
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
                    telefone=telefone,
                )
                return str(tool_result)
