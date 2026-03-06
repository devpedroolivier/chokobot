import json
from openai import AsyncOpenAI
import os
from typing import Dict, Any, List
from app.ai.agents import AGENTS_MAP, TriageAgent
from app.ai.tools import get_menu, escalate_to_human, create_cake_order, CakeOrderSchema, get_learnings, save_learning
from app.observability import increment_counter, log_event, observe_duration
from app.security import ai_learning_enabled

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Gerenciamento de memória em RAM para o MVP (substitui o Redis dos fluxos engessados)
# Estrutura: { telefone: {"messages": [...], "current_agent": "TriageAgent"} }
CONVERSATIONS: Dict[str, Dict[str, Any]] = {}

def get_or_create_session(telefone: str) -> Dict[str, Any]:
    if telefone not in CONVERSATIONS:
        CONVERSATIONS[telefone] = {
            "messages": [],
            "current_agent": "TriageAgent"
        }
    return CONVERSATIONS[telefone]

# Mapeamento de funções reais para as definições de Tools da OpenAI
def get_openai_tools(agent):
    openai_tools = []
    
    if get_menu in agent.tools:
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
        
    if get_learnings in agent.tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": "get_learnings",
                "description": "Lê as regras e instruções que você aprendeu com os clientes no passado.",
                "parameters": {"type": "object", "properties": {}, "required": []}
            }
        })
        
    if save_learning in agent.tools and ai_learning_enabled():
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
        
    if escalate_to_human in agent.tools:
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
        
    if create_cake_order in agent.tools:
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
                        "enum": ["TriageAgent", "CakeOrderAgent", "KnowledgeAgent", "CafeteriaAgent"]
                    }
                },
                "required": ["agent_name"]
            }
        }
    })
    
    return openai_tools


import time
from datetime import datetime

async def process_message_with_ai(telefone: str, text: str, nome_cliente: str, cliente_id: int) -> str:
    """Função principal que o handler vai chamar para processar a mensagem pela IA."""
    start_time = time.time()
    session = get_or_create_session(telefone)
    
    agora = datetime.now()
    data_hora_atual = agora.strftime("Hoje é %d/%m/%Y, e agora são %H:%M.")
    
    if not session["messages"]:
        # Inicializa o prompt de sistema do agente atual
        agent = AGENTS_MAP.get(session["current_agent"], TriageAgent)
        system_instructions = agent.instructions + f"\n\n[CONTEXTO DO SISTEMA: {data_hora_atual}]"
        
        # Inject learnings on boot
        learnings = get_learnings()
        if learnings:
            system_instructions += f"\n\nREGRAS APRENDIDAS ANTERIORMENTE:\n{learnings}"
            
        session["messages"].append({"role": "system", "content": system_instructions})
    
    # Adiciona a mensagem do usuário
    session["messages"].append({"role": "user", "content": text})
    
    log_event("ai_run_started", phone_hash=telefone[-4:] if telefone else "anon", agent=session["current_agent"])
    increment_counter("ai_runs_total", stage="started", agent=session["current_agent"])
    
    total_prompt_tokens = 0
    total_completion_tokens = 0
    iteration_count = 0

    # Loop de raciocínio da IA
    while True:
        iteration_count += 1
        current_agent_name = session["current_agent"]
        agent = AGENTS_MAP.get(current_agent_name, TriageAgent)
        
        # Atualiza as instruções se trocar de agente
        if session["messages"][0]["role"] == "system":
            sys_inst = agent.instructions + f"\n\n[CONTEXTO DO SISTEMA: {data_hora_atual}]"
            learnings = get_learnings()
            if learnings:
                sys_inst += f"\n\nREGRAS APRENDIDAS ANTERIORMENTE:\n{learnings}"
            session["messages"][0]["content"] = sys_inst
            
        tools_config = get_openai_tools(agent)
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=session["messages"],
            tools=tools_config if tools_config else None,
            tool_choice="auto" if tools_config else "none",
            temperature=0.1
        )
        
        # Coleta métricas de tokens
        if response.usage:
            total_prompt_tokens += response.usage.prompt_tokens
            total_completion_tokens += response.usage.completion_tokens
            
        msg = response.choices[0].message
        session["messages"].append(msg)
        
        # Se a IA respondeu com texto final
        if not msg.tool_calls:
            end_time = time.time()
            observe_duration("ai_run_duration_seconds", end_time - start_time, agent=session["current_agent"])
            increment_counter("ai_runs_total", stage="completed", agent=session["current_agent"])
            log_event(
                "ai_run_completed",
                agent=session["current_agent"],
                iterations=iteration_count,
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
            tool_result = ""
            
            if function_name == "transfer_to_agent":
                new_agent = arguments.get("agent_name")
                if new_agent in AGENTS_MAP:
                    session["current_agent"] = new_agent
                    tool_result = f"Sucesso. Conversa transferida para o {new_agent}."
                    log_event("ai_handoff", to_agent=new_agent)
                else:
                    tool_result = f"Erro: Agente {new_agent} não existe."
                    
            elif function_name == "get_menu":
                tool_result = get_menu(arguments.get("category", "todas"))
                
            elif function_name == "get_learnings":
                tool_result = get_learnings()
                
            elif function_name == "save_learning":
                tool_result = save_learning(arguments.get("aprendizado"))
                
            elif function_name == "escalate_to_human":
                tool_result = escalate_to_human(telefone, arguments.get("motivo", "Solicitado pelo cliente"))
                # Limpa a sessão para não reter o estado de erro
                session["messages"] = []
                return "Um momento! Estou transferindo você para um dos nossos atendentes humanos. 👩‍🍳"
                
            elif function_name == "create_cake_order":
                # Instancia o Pydantic model (validação)
                try:
                    order = CakeOrderSchema(**arguments)
                    tool_result = create_cake_order(telefone, nome_cliente, cliente_id, order)
                    session["messages"] = [] # Limpa a sessão após o pedido ser concluído
                    return f"✅ O seu pedido foi finalizado e salvo no nosso sistema! {tool_result}"
                except Exception as e:
                    tool_result = f"Erro ao salvar pedido: Falta de campos ou dados inválidos -> {str(e)}"
            
            # Adiciona o resultado da ferramenta na memória para a IA "ler"
            session["messages"].append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": str(tool_result)
            })
