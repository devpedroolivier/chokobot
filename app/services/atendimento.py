# app/services/atendimento.py
from datetime import datetime
from typing import Dict, Any

from app.utils.mensagens import responder_usuario
from app.services.estados import (
    estados_atendimento,
    estados_encomenda,
    estados_cafeteria,
    estados_entrega,
)

def salvar_atendimento_txt(telefone: str, nome: str) -> None:
    """
    Log simples em arquivo texto para auditoria/histórico.
    """
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    linha = f"{agora} - {nome} | {telefone} solicitou atendimento humano\n"

    try:
        with open("dados/atendimentos.txt", "a", encoding="utf-8") as f:
            f.write(linha)
        print("🧑‍💻 Atendimento humano registrado:", linha.strip())
    except Exception as e:
        print("❌ Erro ao salvar atendimento:", e)

async def processar_atendimento(telefone: str, nome: str = "Cliente") -> None:
    """
    Ativa o modo 'atendimento humano' para o telefone informado.
    - Limpa qualquer fluxo pendente (encomenda/cafeteria/entrega).
    - Marca o telefone em estados_atendimento (bot fica silencioso).
    - Envia confirmação ao cliente.
    """
    # 1) Log/auditoria opcional em TXT
    salvar_atendimento_txt(telefone, nome)

    # 2) Limpa fluxos automáticos pendentes
    estados_encomenda.pop(telefone, None)
    estados_cafeteria.pop(telefone, None)
    estados_entrega.pop(telefone, None)

    # 3) Liga o modo atendente (bot silencioso para este número)
    meta: Dict[str, Any] = {
        "inicio": datetime.now(),
        "nome": nome,
        "motivo": "solicitado_pelo_cliente",
    }
    estados_atendimento[telefone] = meta
    print(f"🔕 Bot silenciado para {telefone} (atendimento humano ativo). Metadados: {meta}")

    # 4) Confirmação ao cliente
    await responder_usuario(
        telefone,
        "👩‍🍳 Certo! Vou te transferir para uma atendente.\n"
        "A partir de agora o bot ficará em silêncio pra vocês conversarem tranquilamente. 🙂"
    )

async def encerrar_atendimento(telefone: str) -> None:
    """
    Reativa o bot para o telefone informado (encerra o atendimento humano).
    Pode ser chamada por um comando do atendente ou por automação interna.
    """
    if telefone in estados_atendimento:
        estados_atendimento.pop(telefone, None)
        print(f"✅ Atendimento humano encerrado para {telefone}. Bot reativado.")
    else:
        print(f"ℹ️ Não havia atendimento humano ativo para {telefone}.")

    await responder_usuario(
        telefone,
        "🤖 Bot reativado. Podemos continuar pelo menu?\n"
        "1️⃣ Ver cardápio\n2️⃣ Encomendar bolos\n3️⃣ Pedidos da cafeteria\n4️⃣ Entregas\n5️⃣ Falar com atendente"
    )
