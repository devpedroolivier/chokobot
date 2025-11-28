# app/services/estados.py

"""
Estados em memória para controlar o fluxo de conversa por telefone.
Cada chave é o telefone (str) e o valor é um dict com metadados do fluxo.
"""

# Fluxos automáticos
estados_encomenda: dict = {}
estados_cafeteria: dict = {}
estados_entrega: dict = {}
estados_cestas_box: dict = {}

# 🔹 Novo: clientes em atendimento humano (bot silencioso)
# Exemplo de valor: {"inicio": datetime, "nome": "Cliente"}
estados_atendimento: dict = {}

# ====== PAGAMENTO ======

# Subestados do fluxo de pagamento
SUBESTADO_FORMA_PAGAMENTO = "AGUARDANDO_FORMA_PAGAMENTO"
SUBESTADO_TROCO = "AGUARDANDO_TROCO"

# Opções disponíveis de forma de pagamento
FORMAS_PAGAMENTO = {
    "1": "PIX",
    "2": "Cartão (débito/crédito)",
    "3": "Dinheiro",
}

# ====== CONTROLE ADMINISTRATIVO DO BOT ======
BOT_ATIVO = True  # flag global — True = ativo / False = desativado
