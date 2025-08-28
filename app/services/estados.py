# app/services/estados.py

"""
Estados em memória para controlar o fluxo de conversa por telefone.
Cada chave é o telefone (str) e o valor é um dict com metadados do fluxo.
"""

# Fluxos automáticos
estados_encomenda: dict = {}
estados_cafeteria: dict = {}
estados_entrega: dict = {}

# 🔹 Novo: clientes em atendimento humano (bot silencioso)
# Exemplo de valor: {"inicio": datetime, "nome": "Cliente"}
estados_atendimento: dict = {}
