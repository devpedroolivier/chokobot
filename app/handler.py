# app/handler.py
from datetime import datetime, timedelta
from collections import deque
from app.models.clientes import salvar_cliente
from app.utils.mensagens import responder_usuario, is_saudacao
from app.services.encomendas import processar_encomenda
from app.services.cafeteria import processar_cafeteria
from app.services.entregas import processar_entrega
from app.services.atendimento import processar_atendimento
from app.services.estados import (
    estados_encomenda,
    estados_entrega,
    estados_cafeteria,
    estados_atendimento,
)
from app.config import CAFETERIA_URL

CANCELAR_OPCOES = ["cancelar", "sair", "parar", "desistir"]
MENU_OPCOES = ["menu", "voltar", "inicio", "principal", "bot"]
REATIVAR_BOT_OPCOES = ["voltar", "menu", "bot", "reativar", "voltar ao bot"]

mensagens_processadas = deque(maxlen=2000)
ultimas_mensagens = {}

async def processar_mensagem(mensagem: dict):
    texto = (mensagem.get("text", {}) or {}).get("message", "")
    if texto:
        texto = texto.lower().strip()
    telefone = (mensagem.get("phone") or "").replace("+", "").strip()
    nome_cliente = mensagem.get("chatName", "Nome não informado")
    msg_id = mensagem.get("id") or mensagem.get("messageId")

    if not telefone or not texto:
        print("❌ Dados incompletos:", mensagem)
        return

    agora = datetime.now()

    if msg_id and msg_id in mensagens_processadas:
        print(f"⚠️ Ignorado webhook duplicado ({msg_id}) de {telefone}")
        return
    if msg_id:
        mensagens_processadas.append(msg_id)

    ultima = ultimas_mensagens.get(telefone)
    if ultima and ultima["texto"] == texto and (agora - ultima["hora"]) < timedelta(seconds=2):
        print(f"⚠️ Ignorado duplicado por conteúdo de {telefone}: '{texto}'")
        return
    ultimas_mensagens[telefone] = {"texto": texto, "hora": agora}

    if telefone in estados_atendimento:
        if texto in REATIVAR_BOT_OPCOES:
            estados_atendimento.pop(telefone, None)
            await responder_usuario(
                telefone,
                "🤖 Bot reativado. Vamos continuar!\n"
                "1️⃣ Pronta Entrega B3 ou B4 — sabores disponíveis hoje\n"
                "2️⃣ Ver cardápios\n"
                "3️⃣ Encomendar bolos ou tortas\n"
                "4️⃣ Pedidos Delivery Cafeteria\n"
                "5️⃣ Entregas 🚚"
            )
        else:
            print(f"👤 {telefone} em atendimento humano — bot silencioso.")
        return

    if texto in CANCELAR_OPCOES:
        if telefone in estados_encomenda:
            estados_encomenda.pop(telefone)
            await responder_usuario(telefone, "❌ Encomenda cancelada com sucesso.")
        elif telefone in estados_cafeteria:
            estados_cafeteria.pop(telefone)
            await responder_usuario(telefone, "❌ Pedido da cafeteria cancelado com sucesso.")
        elif telefone in estados_entrega:
            estados_entrega.pop(telefone)
            await responder_usuario(telefone, "❌ Solicitação de entrega cancelada com sucesso.")
        else:
            await responder_usuario(telefone, "⚠️ Nenhuma operação em andamento para cancelar.")
        return

    if texto in MENU_OPCOES:
        estados_encomenda.pop(telefone, None)
        estados_cafeteria.pop(telefone, None)
        estados_entrega.pop(telefone, None)
        await responder_usuario(
            telefone,
            "🍫 *Menu Principal*\n"
            "1️⃣ Pronta Entrega B3 ou B4 — sabores disponíveis hoje\n"
            "2️⃣ Ver cardápios\n"
            "3️⃣ Encomendar bolos ou tortas\n"
            "4️⃣ Pedidos Delivery Cafeteria\n"
            "5️⃣ Entregas 🚚"
        )
        return

    if telefone in estados_entrega:
        estado = estados_entrega[telefone]
        resultado = await processar_entrega(telefone, texto, estado)
        estados_entrega[telefone] = estado
        if resultado == "finalizar":
            estados_entrega.pop(telefone, None)
            estados_encomenda.pop(telefone, None)
        return

    if telefone in estados_encomenda:
        estado = estados_encomenda[telefone]
        resultado = await processar_encomenda(telefone, texto, estado, nome_cliente)
        estados_encomenda[telefone] = estado
        if resultado == "finalizar":
            estados_encomenda.pop(telefone, None)
        return

    if telefone in estados_cafeteria:
        estado = estados_cafeteria[telefone]
        resultado = await processar_cafeteria(telefone, texto, estado)
        estados_cafeteria[telefone] = estado
        if resultado == "voltar_menu":
            estados_cafeteria.pop(telefone, None)
            await responder_usuario(
                telefone,
                "🍫 Olá novamente! Escolha uma opção:\n"
                "1️⃣ Pronta Entrega B3 ou B4 — sabores disponíveis hoje\n"
                "2️⃣ Ver cardápios\n"
                "3️⃣ Encomendar bolos ou tortas\n"
                "4️⃣ Pedidos Delivery Cafeteria\n"
                "5️⃣ Entregas 🚚"
            )
        elif resultado == "finalizar":
            estados_cafeteria.pop(telefone, None)
        return

    salvar_cliente(telefone, nome_cliente)

    if is_saudacao(texto):
        await responder_usuario(
            telefone,
            "🍫 Olá! Bem-vindo(a) à *Chokodelícia* 🍫\n"
            "Sou a *Trufinha* 🍬, assistente virtual da nossa Cafeteria e Doceria!\n\n"
            "Escolha uma opção:\n"
            "1️⃣ Pronta Entrega B3 ou B4 — sabores disponíveis hoje\n"
            "2️⃣ Ver cardápios\n"
            "3️⃣ Encomendar bolos ou tortas\n"
            "4️⃣ Pedidos Delivery Cafeteria\n"
            "5️⃣ Entregas 🚚"
        )
        return

    elif texto in ["1", "pronta", "pronta entrega", "pronta-entrega"]:
        estados_encomenda[telefone] = {
            "etapa": "pronta_item",
            "dados": {"linha": "pronta_entrega"}
        }
        await responder_usuario(
            telefone,
            "📦 *Pronta entrega de hoje:*\n\n"
            "🎂 Mesclado de Brigadeiro com Ninho\n\n"
            "B3 (até 15 pessoas) — R$120\n"
            "B4 (até 30 pessoas) — R$180\n\n"
            "Adicione +R$35 e leve o *Kit Festou* 🎉 (25 brigadeiros + 1 Balão personalizado)\n\n"
            "📝 Digite *B3* ou *B4*"
        )
        return


    elif texto in ["2", "cardápio", "cardapio", "cardapios"]:
        estados_cafeteria[telefone] = {"subetapa": "aguardando_cardapio"}
        await responder_usuario(
            telefone,
            "📋 Qual cardápio você deseja ver?\n"
            "1️⃣ Cardápio Cafeteria\n"
            "2️⃣ Cardápio Bolos & Tortas\n"
            "3️⃣ Cardápio Doces"
        )
        return

    elif texto in ["3", "bolo", "encomendar", "encomendas", "torta", "tortas"]:
        estados_encomenda[telefone] = {"etapa": 1, "dados": {}}
        await responder_usuario(
            telefone,
            "🎂 *Vamos começar sua encomenda!*\n\n"
            "Qual linha você deseja?\n"
            "1️⃣ Monte seu bolo (B3 | B4 | B6 | B7)\n"
            "2️⃣ Linha Gourmet (Inglês ou Redondo P6)\n"
            "3️⃣ Linha Mesversário ou Revelação\n"
            "4️⃣ Linha Individual Baby Cake\n"
            "5️⃣ Tortas\n\n"
            "📷 Fotos e preços: https://keepo.io/boloschoko/"
        )
        return

    elif texto in ["4", "pedido", "cafeteria", "delivery"]:
        await responder_usuario(
            telefone,
            f"☕ Os pedidos da *cafeteria* são feitos pelo nosso link oficial: {CAFETERIA_URL}\n"
            "Qualquer dúvida, me chame aqui. 😉"
        )
        return

    elif texto in ["5", "entrega", "informações de entrega", "delivery"]:
        await responder_usuario(
            telefone,
            "🚚 Entregamos em *Pitangueiras-SP* (taxa R$10) *exceto zona rural*.\n"
            "Ibitiuva, zona rural ou Usina: combinar valor especial.\n"
            "Para outras regiões, o valor depende da distância (via Uber).\n"
            "Horário de entregas: 10h às 18h."
        )
        return

    elif texto in ["6", "atendente", "humano", "falar"]:
        await processar_atendimento(telefone, nome_cliente)
        return

    else:
        await responder_usuario(
            telefone,
            "Desculpe, não entendi sua mensagem 😕\n"
            "Digite uma das opções abaixo:\n"
            "1️⃣ Pronta Entrega B3 ou B4 — sabores disponíveis hoje\n"
            "2️⃣ Ver cardápios\n"
            "3️⃣ Encomendar bolos ou tortas\n"
            "4️⃣ Pedidos Delivery Cafeteria\n"
            "5️⃣ Entregas 🚚"
        )
