import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from openai import AsyncOpenAI
except ModuleNotFoundError:
    AsyncOpenAI = None

from app.ai.agents import AGENTS_MAP, TriageAgent
from app.welcome_message import HUMAN_HANDOFF_MESSAGE
from app.ai.tools import (
    CakeOrderSchema,
    SweetOrderSchema,
    create_cake_order,
    create_sweet_order,
    escalate_to_human,
    get_learnings,
    get_menu,
    save_learning,
)
from app.observability import increment_counter, log_event, observe_duration
from app.security import ai_learning_enabled
from app.services.estados import ai_sessions
from app.settings import get_settings

client = None

CONVERSATIONS = ai_sessions
DELIVERY_CUTOFF = (17, 30)


@dataclass(frozen=True)
class AIRuntime:
    get_menu: Any
    get_learnings: Any
    save_learning: Any
    escalate_to_human: Any
    create_cake_order: Any
    create_sweet_order: Any


def get_default_ai_runtime() -> AIRuntime:
    return AIRuntime(
        get_menu=get_menu,
        get_learnings=get_learnings,
        save_learning=save_learning,
        escalate_to_human=escalate_to_human,
        create_cake_order=create_cake_order,
        create_sweet_order=create_sweet_order,
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


def _normalize_reference_time(now: datetime | None = None) -> datetime:
    current_time = now or current_local_datetime()
    timezone = _current_timezone()
    if current_time.tzinfo is None:
        return current_time.replace(tzinfo=timezone)
    return current_time.astimezone(timezone)


def _is_after_delivery_cutoff(now: datetime | None = None) -> bool:
    current_time = _normalize_reference_time(now)
    return (current_time.hour, current_time.minute) > DELIVERY_CUTOFF


def _same_day_reference_tokens(now: datetime | None = None) -> tuple[str, ...]:
    current_time = _normalize_reference_time(now)
    return (
        current_time.strftime("%d/%m/%Y"),
        current_time.strftime("%d/%m"),
        current_time.strftime("%d-%m-%Y"),
        current_time.strftime("%d-%m"),
    )


def _mentions_same_day(text: str, now: datetime | None = None) -> bool:
    normalized = (text or "").casefold()
    if re.search(r"\b(hoje|hj)\b", normalized):
        return True
    return any(token in normalized for token in _same_day_reference_tokens(now))


def _mentions_order_intent(text: str) -> bool:
    normalized = (text or "").casefold()
    return bool(
        re.search(
            r"\b(bolo|encomenda\w*|torta|mesvers[aá]rio|baby\s*cake|babycake|gourmet|b3|b4|b6|b7|p4|p6)\b",
            normalized,
        )
    )


def _requests_human_handoff(text: str) -> bool:
    normalized = (text or "").casefold()
    patterns = (
        r"\bfalar com (um )?(humano|atendente|pessoa)\b",
        r"\bquero falar com (um )?(humano|atendente|pessoa)\b",
        r"\b(atendente|humano) real\b",
        r"\bme passa para (um )?(humano|atendente)\b",
        r"\btransfer(e|ir) .* (humano|atendente)\b",
        r"\bdesativar (o )?(chat|bot)\b",
        r"\bquero (um )?humano\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def _response_conflicts_with_cutoff(reply: str | None, *, user_text: str, now: datetime | None = None) -> bool:
    if not reply or _is_after_delivery_cutoff(now) or not _mentions_same_day(user_text, now):
        return False

    normalized = reply.casefold()
    if re.search(r"(j[aá]\s+)?passou\s+das?\s+17[:h]30", normalized):
        return True
    if re.search(r"encomendas?\s+para\s+hoje\s+se\s+encerraram", normalized):
        return True
    return False


def _build_time_conflict_retry_instruction(now: datetime | None = None) -> str:
    current_time = _normalize_reference_time(now)
    return (
        "CORRECAO DE SISTEMA: use exclusivamente o horario oficial de Brasilia. "
        f"Agora sao {current_time.strftime('%H:%M')} em Brasilia e ainda NAO passou das 17:30. "
        "Reescreva a resposta sem afirmar que o horario limite de hoje foi ultrapassado."
    )


def _should_force_same_day_cafeteria_handoff(session: dict, user_text: str, now: datetime | None = None) -> bool:
    if not _is_after_delivery_cutoff(now) or not _mentions_same_day(user_text, now):
        return False

    current_agent = session.get("current_agent")
    if current_agent == "CakeOrderAgent":
        return True
    if current_agent == "TriageAgent" and _mentions_order_intent(user_text):
        return True
    return False


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
    return session

# Mapeamento de funções reais para as definições de Tools da OpenAI
def get_openai_tools(agent, runtime: AIRuntime | None = None):
    runtime = runtime or get_default_ai_runtime()
    openai_tools = []
    
    if runtime.get_menu in agent.tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": "get_menu",
                "description": "Busca os cardapios, produtos e precos da Chokodelicia. Use `category=\"pronta_entrega\"` para vitrine/cafeteria/doces e `category=\"encomendas\"` para bolos personalizados, tortas e cestas.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Categoria do menu: pronta_entrega, encomendas ou todas",
                        }
                    },
                    "required": []
                }
            }
        })
        
    if runtime.get_learnings in agent.tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": "get_learnings",
                "description": "Lê as regras e instruções que você aprendeu com os clientes no passado.",
                "parameters": {"type": "object", "properties": {}, "required": []}
            }
        })
        
    if runtime.save_learning in agent.tools and ai_learning_enabled():
        openai_tools.append({
            "type": "function",
            "function": {
                "name": "save_learning",
                "description": "Salva uma nova regra ou correção ensinada pelo cliente (loop de aprendizagem).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "aprendizado": {"type": "string", "description": "A regra exata a ser salva."}
                    },
                    "required": ["aprendizado"]
                }
            }
        })
        
    if runtime.escalate_to_human in agent.tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": "escalate_to_human",
                "description": "Transfere a conversa imediatamente para um humano se o cliente pedir ou se o agente não souber resolver.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "motivo": {"type": "string", "description": "Por que está transferindo para humano"}
                    },
                    "required": ["motivo"]
                }
            }
        })
        
    if runtime.create_cake_order in agent.tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": "create_cake_order",
                "description": "Salva o pedido de bolo de encomenda após o cliente confirmar TODOS os detalhes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "linha": {"type": "string", "description": "tradicional, gourmet, mesversario, babycake, torta, simples"},
                        "categoria": {"type": "string", "description": "tradicional, ingles, redondo, torta"},
                        "produto": {"type": "string"},
                        "tamanho": {"type": "string"},
                        "massa": {"type": "string"},
                        "recheio": {"type": "string"},
                        "mousse": {"type": "string"},
                        "adicional": {"type": "string"},
                        "descricao": {"type": "string"},
                        "kit_festou": {"type": "boolean"},
                        "quantidade": {"type": "integer"},
                        "data_entrega": {"type": "string", "description": "DD/MM/AAAA"},
                        "horario_retirada": {"type": "string", "description": "HH:MM"},
                        "modo_recebimento": {"type": "string", "enum": ["retirada", "entrega"]},
                        "endereco": {"type": "string"},
                        "taxa_entrega": {"type": "number"},
                        "pagamento": {
                            "type": "object",
                            "properties": {
                                "forma": {"type": "string", "enum": ["PIX", "Cartão (débito/crédito)", "Dinheiro", "Pendente"]},
                                "troco_para": {"type": "number"}
                            },
                            "required": ["forma"]
                        }
                    },
                    "required": ["linha", "categoria", "descricao", "data_entrega", "modo_recebimento", "pagamento"]
                }
            }
        })

    if runtime.create_sweet_order in agent.tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": "create_sweet_order",
                "description": "Salva o pedido de doces avulsos em quantidade apos a confirmacao final do cliente.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "itens": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "nome": {"type": "string"},
                                    "quantidade": {"type": "integer"},
                                },
                                "required": ["nome", "quantidade"],
                            },
                        },
                        "data_entrega": {"type": "string", "description": "DD/MM/AAAA"},
                        "horario_retirada": {"type": "string", "description": "HH:MM"},
                        "modo_recebimento": {"type": "string", "enum": ["retirada", "entrega"]},
                        "endereco": {"type": "string"},
                        "pagamento": {
                            "type": "object",
                            "properties": {
                                "forma": {"type": "string", "enum": ["PIX", "Cartão (débito/crédito)", "Dinheiro", "Pendente"]},
                                "troco_para": {"type": "number"}
                            },
                            "required": ["forma"]
                        }
                    },
                    "required": ["itens", "data_entrega", "modo_recebimento", "pagamento"]
                }
            }
        })

    # Injeta automaticamente o roteamento como uma tool para TODOS os agentes (Handoff)
    openai_tools.append({
        "type": "function",
        "function": {
            "name": "transfer_to_agent",
            "description": "Transfere a conversa para outro agente especializado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string", 
                        "enum": ["TriageAgent", "CakeOrderAgent", "SweetOrderAgent", "KnowledgeAgent", "CafeteriaAgent"]
                    }
                },
                "required": ["agent_name"]
            }
        }
    })

    return openai_tools


def _current_timezone() -> ZoneInfo:
    settings = get_settings()
    timezone_name = settings.bot_timezone or settings.tz or "America/Sao_Paulo"
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("America/Sao_Paulo")


def current_local_datetime() -> datetime:
    return datetime.now(_current_timezone())


def build_system_time_context(now: datetime | None = None) -> str:
    current_time = _normalize_reference_time(now)
    cutoff_status = "depois do limite" if _is_after_delivery_cutoff(current_time) else "antes do limite"
    return (
        current_time.strftime("Hoje é %d/%m/%Y, e agora são %H:%M.")
        + " Horario oficial de Brasilia (America/Sao_Paulo)."
        + f" Status do corte das 17:30: {cutoff_status}."
    )


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


def handle_tool_call(
    *,
    runtime: AIRuntime,
    function_name: str,
    arguments: dict,
    telefone: str,
    nome_cliente: str,
    cliente_id: int,
    session: dict,
) -> tuple[bool, str]:
    tool_result = ""

    if function_name == "transfer_to_agent":
        new_agent = arguments.get("agent_name")
        if new_agent in AGENTS_MAP:
            session["current_agent"] = new_agent
            tool_result = f"Sucesso. Conversa transferida para o {new_agent}."
            log_event("ai_handoff", to_agent=new_agent)
            save_session(telefone, session)
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
        save_session(telefone, session)
        return True, HUMAN_HANDOFF_MESSAGE
    elif function_name == "create_cake_order":
        try:
            order = CakeOrderSchema(**arguments)
            tool_result = runtime.create_cake_order(telefone, nome_cliente, cliente_id, order)
            session["messages"] = []
            save_session(telefone, session)
            return True, f"✅ O seu pedido foi finalizado e salvo no nosso sistema! {tool_result}"
        except Exception as exc:
            tool_result = f"Erro ao salvar pedido: Falta de campos ou dados inválidos -> {str(exc)}"
    elif function_name == "create_sweet_order":
        try:
            order = SweetOrderSchema(**arguments)
            tool_result = runtime.create_sweet_order(telefone, nome_cliente, cliente_id, order)
            session["messages"] = []
            save_session(telefone, session)
            return True, f"✅ O seu pedido foi finalizado e salvo no nosso sistema! {tool_result}"
        except Exception as exc:
            tool_result = f"Erro ao salvar pedido: Falta de campos ou dados inválidos -> {str(exc)}"

    return False, str(tool_result)


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
    
    if not session["messages"]:
        bootstrap_session(session, now, runtime)
        save_session(telefone, session)
    
    # Adiciona a mensagem do usuário
    session["messages"].append({"role": "user", "content": text})
    save_session(telefone, session)

    if _requests_human_handoff(text):
        runtime.escalate_to_human(telefone, "Cliente pediu humano")
        session["messages"] = []
        save_session(telefone, session)
        increment_counter("ai_human_guard_handoffs_total", agent=session["current_agent"])
        log_event("ai_human_guard_handoff", phone_hash=telefone[-4:] if telefone else "anon", agent=session["current_agent"])
        return HUMAN_HANDOFF_MESSAGE

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

        session["messages"].append(assistant_message)
        save_session(telefone, session)
        
        # Se a IA respondeu com texto final
        if not msg.tool_calls:
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
            )
            if should_return:
                return tool_result

            # Adiciona o resultado da ferramenta na memória para a IA "ler"
            session["messages"].append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": str(tool_result)
            })
            save_session(telefone, session)
