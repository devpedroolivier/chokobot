# app/handler.py
from datetime import datetime
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


async def processar_mensagem(mensagem: dict):
    texto = mensagem.get("text", {}).get("message", "").lower().strip()
    telefone = mensagem.get("phone")
    nome_cliente = mensagem.get("chatName", "Nome não informado")

    if not telefone or not texto:
        print("❌ Dados incompletos:", mensagem)
        return

    # Atendimento humano
    if telefone in estados_atendimento:
        if texto in REATIVAR_BOT_OPCOES:
            estados_atendimento.pop(telefone, None)
            await responder_usuario(
                telefone,
                "🤖 Bot reativado. Vamos continuar!\n"
                "1️⃣ Ver cardápios\n"
                "2️⃣ Encomendar bolos ou tortas\n"
                "3️⃣ Pedidos Delivery Cafeteria\n"
                "4️⃣ Entregas 🚚"
                
            )
        else:
            print(f"👤 {telefone} em atendimento humano — bot silencioso.")
        return

    # Cancelar global
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

    # Menu global
    if texto in MENU_OPCOES:
        estados_encomenda.pop(telefone, None)
        estados_cafeteria.pop(telefone, None)
        estados_entrega.pop(telefone, None)
        await responder_usuario(
            telefone,
            "🍫 *Menu Principal*\n"
            "1️⃣ Ver cardápios\n"
            "2️⃣ Encomendar bolos ou tortas\n"
            "3️⃣ Pedidos Delivery Cafeteria\n"
            "4️⃣ Entregas 🚚"
            
        )
        return

    # Entregas
    if telefone in estados_entrega:
        resultado = await processar_entrega(telefone, texto, estados_entrega[telefone])
        if resultado == "finalizar":
            estados_entrega.pop(telefone, None)
            estados_encomenda.pop(telefone, None)
            print(f"✅ DEBUG: Estados limpos para {telefone} após finalizar entrega")
        return

    # Encomendas
    if telefone in estados_encomenda:
        resultado = await processar_encomenda(telefone, texto, estados_encomenda[telefone], nome_cliente)
        if resultado == "finalizar":
            estados_encomenda.pop(telefone, None)
        return

    # Cafeteria
    if telefone in estados_cafeteria:
        resultado = await processar_cafeteria(telefone, texto, estados_cafeteria[telefone])
        if resultado == "voltar_menu":
            estados_cafeteria.pop(telefone, None)
            await responder_usuario(
                telefone,
                "🍫 Olá novamente! Escolha uma opção:\n"
                "1️⃣ Ver cardápios\n"
                "2️⃣ Encomendar bolos ou tortas\n"
                "3️⃣ Pedidos Delivery Cafeteria\n"
                "4️⃣ Entregas 🚚"
                
            )
        elif resultado == "finalizar":
            estados_cafeteria.pop(telefone, None)
        return

    # Saudações / entrada
    salvar_cliente(telefone, nome_cliente)

    if is_saudacao(texto):
        await responder_usuario(
            telefone,
            "🍫 Olá! Bem-vindo(a) à *Chokodelícia* 🍫\n"
            "Sou a *Trufinha* 🍬, assistente virtual da nossa Cafeteria e Doceria!\n\n"
            "Escolha uma opção:\n"
            "1️⃣ Ver cardápios\n"
            "2️⃣ Encomendar bolos ou tortas\n"
            "3️⃣ Pedidos Delivery Cafeteria\n"
            "4️⃣ Entregas 🚚"
            
        )
        return

    # Menu principal
    if texto in ["1", "cardápio", "cardapio", "cardapios"]:
        estados_cafeteria[telefone] = {"subetapa": "aguardando_cardapio"}
        await responder_usuario(
            telefone,
            "📋 Qual cardápio você deseja ver?\n"
            "1️⃣ Cardápio Cafeteria\n"
            "2️⃣ Cardápio Bolos & Tortas\n"
            "3️⃣ Cardápio Doces"
            
        )

    elif texto in ["2", "bolo", "encomendar", "encomendas", "torta", "tortas"]:
        estados_encomenda[telefone] = {"etapa": 1, "dados": {}}
        await responder_usuario(
            telefone,
            "🎂 *Vamos começar sua encomenda!*\n\n"
            "Qual linha você deseja?\n"
            "1️⃣ Pronta Entrega — sabores disponíveis hoje\n"
            "2️⃣ Monte seu bolo (B3 | B4 | B6 | B7)\n"
            "3️⃣ Linha Gourmet (Inglês ou Redondo P6)\n"
            "4️⃣ Linha Mesversário ou Revelação\n"
            "5️⃣ Linha Individual Baby Cake\n"
            "6️⃣ Tortas\n\n"
            "📷 Fotos e preços: https://keepo.io/boloschoko/"
        )


    elif texto in ["3", "pedido", "cafeteria", "delivery"]:
        await responder_usuario(
            telefone,
            f"☕ Os pedidos da *cafeteria* são feitos pelo nosso link oficial: {CAFETERIA_URL}\n"
            "Qualquer dúvida, me chame aqui. 😉"
        )
        return

    elif texto in ["4", "entrega", "informações de entrega", "delivery"]:
        await responder_usuario(
            telefone,
            "🚚 Entregamos em *Pitangueiras-SP* (taxa R$10) *exceto zona rural*.\n"
            "Ibitiuva, zona rural ou Usina: combinar valor especial.\n"
            "Para outras regiões, o valor depende da distância (via Uber).\n"
            "Horário de entregas: 10h às 18h."
        )

            

    elif texto in ["5", "atendente", "humano", "falar"]:
        await processar_atendimento(telefone, nome_cliente)
        return

    else:
        await responder_usuario(
            telefone,
            "Desculpe, não entendi sua mensagem 😕\n"
            "Digite uma das opções abaixo:\n"
            "1️⃣ Ver cardápios\n"
            "2️⃣ Encomendar bolos ou tortas\n"
            "3️⃣ Pedidos Delivery Cafeteria\n"
            "4️⃣ Entregas 🚚"
            
        )
