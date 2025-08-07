from datetime import datetime
from app.models.clientes import salvar_cliente
from app.utils.mensagens import responder_usuario, is_saudacao
from app.services.encomendas import processar_encomenda
from app.services.cafeteria import processar_cafeteria
from app.services.entregas import processar_entrega
from app.services.atendimento import processar_atendimento
from app.services.estados import estados_encomenda, estados_entrega, estados_cafeteria


CANCELAR_OPCOES = ["cancelar", "sair", "parar", "desistir"]

async def processar_mensagem(mensagem: dict):
    texto = mensagem.get("text", {}).get("message", "").lower().strip()
    telefone = mensagem.get("phone")
    nome_cliente = mensagem.get("chatName", "Nome não informado")

    if not telefone or not texto:
        print("❌ Dados incompletos:", mensagem)
        return

    # Cancelar qualquer processo ativo
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

       # Entregas — DEVE vir primeiro
    if telefone in estados_entrega:
        resultado = await processar_entrega(telefone, texto, estados_entrega[telefone])
        if resultado == "finalizar":
            estados_entrega.pop(telefone)
        return

    # Encomendas
    if telefone in estados_encomenda:
        resultado = await processar_encomenda(telefone, texto, estados_encomenda[telefone], nome_cliente)
        if resultado == "finalizar":
            estados_encomenda.pop(telefone)
        return

    # Cafeteria
    if telefone in estados_cafeteria:
        resultado = await processar_cafeteria(telefone, texto, estados_cafeteria[telefone])
        if resultado == "voltar_menu":
            estados_cafeteria.pop(telefone)
            await responder_usuario(
                telefone,
                "🍫 Olá novamente! Escolha uma opção:\n"
                "1️⃣ Ver cardápio\n"
                "2️⃣ Encomendar bolos\n"
                "3️⃣ Pedidos da cafeteria\n"
                "4️⃣ Entregas\n"
                "5️⃣ Falar com atendente"
            )
        elif resultado == "finalizar":
            estados_cafeteria.pop(telefone)
        return


    # Saudações ou entrada no menu
    salvar_cliente(telefone, nome_cliente)

    if is_saudacao(texto):
        await responder_usuario(
            telefone,
            "🍫 Olá! Bem-vindo(a) à Chokodelícia 🍫\n"
            "Sou a Trufinha 🍬, assistente virtual da nossa cafeteria e confeitaria!\n\n"
            "Escolha uma opção:\n"
            "1️⃣ Ver cardápio\n"
            "2️⃣ Encomendar bolos\n"
            "3️⃣ Pedidos da cafeteria\n"
            "4️⃣ Entregas\n"
            "5️⃣ Falar com atendente"
        )
        return

    # Menu principal
    if texto in ["1", "cardápio", "cardapio"]:
        estados_cafeteria[telefone] = {"subetapa": "aguardando_cardapio"}
        await responder_usuario(
            telefone,
            "📋 Qual cardápio você deseja ver?\n"
            "1️⃣ Cardápio Cafeteria\n"
            "2️⃣ Cardápio Bolos\n"
            "3️⃣ Cardápio Doces\n"
            "4️⃣ Cardápio Sazonais"
        )

    elif texto in ["2", "bolo", "encomendar", "encomendas"]:
        estados_encomenda[telefone] = {"etapa": 1, "dados": {}}
        await responder_usuario(
            telefone,
            "🎂 *Vamos começar sua encomenda!*\n\n"
            "Qual linha de bolo você deseja?\n"
            "1️⃣ Montar bolo personalizado\n"
            "2️⃣ Linha Gourmet\n"
            "3️⃣ Bolos Redondos (P6)\n"
            "4️⃣ Tortas\n"
            "5️⃣ *Pronta Entrega* — ver sabores disponíveis hoje\n\n"
            "📷 Para ver fotos e preços, consulte nosso cardápio: https://keepo.io/boloschoko/"
        )


    elif texto in ["3", "pedido", "cafeteria"]:
        estados_cafeteria[telefone] = {"itens": [], "nome": nome_cliente}
        await responder_usuario(
            telefone,
            "☕ Vamos anotar seu pedido!\n"
            "Digite o que você deseja da cafeteria (ex: cappuccino, pão de queijo).\n"
            "Digite *finalizar* quando terminar seu pedido."
        )

    elif texto in ["4", "entrega", "informações de entrega"]:
        await responder_usuario(
            telefone,
            "🚚 Entregamos na cidade toda (R$10).\n"
            "Para outras regiões, o valor depende da distância (via Uber).\n"
            "Horário de entregas: 10h às 18h."
        )


    elif texto in ["5", "atendente", "humano"]:
        await processar_atendimento(telefone, nome_cliente)

    else:
        await responder_usuario(
            telefone,
            "Desculpe, não entendi sua mensagem 😕\n"
            "Digite uma das opções abaixo:\n"
            "1️⃣ Ver cardápio\n"
            "2️⃣ Encomendar bolos\n"
            "3️⃣ Pedidos da cafeteria\n"
            "4️⃣ Entregas\n"
            "5️⃣ Falar com atendente"
        )
