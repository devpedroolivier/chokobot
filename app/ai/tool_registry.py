from __future__ import annotations

from app.security import ai_learning_enabled


def build_openai_tools(agent, runtime) -> list[dict]:
    openai_tools = []

    if runtime.get_menu in agent.tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": "get_menu",
                    "description": (
                        "Busca os cardapios, produtos e precos da Chokodelicia. "
                        'Use `category="pronta_entrega"` para vitrine/cafeteria/doces e '
                        '`category="encomendas"` para bolos personalizados, tortas e cestas.'
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "Categoria do menu: pronta_entrega, encomendas ou todas",
                            }
                        },
                        "required": [],
                    },
                },
            }
        )

    if runtime.get_cake_options in agent.tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": "get_cake_options",
                    "description": (
                        "Retorna as opcoes canonicas de bolo para uma categoria especifica. "
                        "Use para listar recheios, mousses, adicionais, massas ou tamanhos "
                        "sem omitir itens e sem misturar categorias."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": ["tradicional", "mesversario"],
                                "description": "Categoria do bolo: tradicional ou mesversario",
                            },
                            "option_type": {
                                "type": "string",
                                "enum": ["massa", "tamanho", "recheio", "mousse", "adicional"],
                                "description": "Tipo de opcao que deve ser listada",
                            },
                        },
                        "required": ["category", "option_type"],
                    },
                },
            }
        )

    if runtime.get_learnings in agent.tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": "get_learnings",
                    "description": "Lê as regras e instruções que você aprendeu com os clientes no passado.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }
        )

    if runtime.save_learning in agent.tools and ai_learning_enabled():
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": "save_learning",
                    "description": "Salva uma nova regra ou correção ensinada pelo cliente (loop de aprendizagem).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "aprendizado": {
                                "type": "string",
                                "description": "A regra exata a ser salva.",
                            }
                        },
                        "required": ["aprendizado"],
                    },
                },
            }
        )

    if runtime.escalate_to_human in agent.tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": "escalate_to_human",
                    "description": (
                        "Transfere a conversa imediatamente para um humano se o cliente pedir "
                        "ou se o agente não souber resolver."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "motivo": {"type": "string", "description": "Por que está transferindo para humano"}
                        },
                        "required": ["motivo"],
                    },
                },
            }
        )

    if runtime.create_cake_order in agent.tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": "create_cake_order",
                    "description": (
                        "Salva o pedido de bolo de encomenda apenas apos a confirmacao final explicita do cliente. "
                        "So use se a ultima mensagem do cliente for algo como 'sim', 'confirmo', "
                        "'pode fechar' ou equivalente."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "linha": {
                                "type": "string",
                                "description": "tradicional, gourmet, mesversario, babycake, torta, simples",
                            },
                            "categoria": {
                                "type": "string",
                                "description": "tradicional, ingles, redondo, torta",
                            },
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
                                    "forma": {
                                        "type": "string",
                                        "enum": ["PIX", "Cartão (débito/crédito)", "Dinheiro", "Pendente"],
                                    },
                                    "troco_para": {"type": "number"},
                                },
                                "required": ["forma"],
                            },
                        },
                        "required": [
                            "linha",
                            "categoria",
                            "descricao",
                            "data_entrega",
                            "modo_recebimento",
                            "pagamento",
                        ],
                    },
                },
            }
        )

    if runtime.create_sweet_order in agent.tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": "create_sweet_order",
                    "description": (
                        "Salva o pedido de doces avulsos em quantidade apenas apos a confirmacao final explicita do cliente. "
                        "So use se a ultima mensagem do cliente for algo como 'sim', 'confirmo', "
                        "'pode fechar' ou equivalente."
                    ),
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
                                    "forma": {
                                        "type": "string",
                                        "enum": ["PIX", "Cartão (débito/crédito)", "Dinheiro", "Pendente"],
                                    },
                                    "troco_para": {"type": "number"},
                                },
                                "required": ["forma"],
                            },
                        },
                        "required": ["itens", "data_entrega", "modo_recebimento", "pagamento"],
                    },
                },
            }
        )

    openai_tools.append(
        {
            "type": "function",
            "function": {
                "name": "transfer_to_agent",
                "description": "Transfere a conversa para outro agente especializado.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "enum": [
                                "TriageAgent",
                                "CakeOrderAgent",
                                "SweetOrderAgent",
                                "KnowledgeAgent",
                                "CafeteriaAgent",
                            ],
                        }
                    },
                    "required": ["agent_name"],
                },
            },
        }
    )

    return openai_tools
