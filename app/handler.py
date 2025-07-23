
import httpx
import os
from datetime import datetime
from app.config import ZAPI_ENDPOINT_TEXT, ZAPI_ENDPOINT_IMAGE, ZAPI_TOKEN

SAUDACOES = ["oi","iae","salve", "olá", "ola", "bom dia", "boa tarde", "boa noite"]
CANCELAR_OPCOES = ["cancelar", "sair", "parar", "desistir"]
estados_encomenda = {}
estados_cafeteria = {}
estados_entrega = {}

def is_saudacao(texto: str) -> bool:
    return any(sauda in texto.lower() for sauda in SAUDACOES)

def salvar_cliente(phone: str, nome: str = "Nome não informado"):
    try:
        if os.path.exists("clientes.txt"):
            with open("clientes.txt", "r", encoding="utf-8") as f:
                if any(phone in linha for linha in f):
                    print(f"🔁 Número já registrado: {phone}")
                    return
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        linha = f"{agora} - {nome} | {phone}\n"
        with open("clientes.txt", "a", encoding="utf-8") as f:
            f.write(linha)
        print("📝 Cliente salvo:", linha.strip())
    except Exception as e:
        print("❌ Erro ao salvar cliente:", e)

def salvar_encomenda(phone: str, dados: dict, nome: str = "Nome não informado"):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    linha = (
        f"{agora} - {nome} | {phone} | "
        f"Tipo: {dados.get('tipo')} | "
        f"Tamanho: {dados.get('tamanho')} | "
        f"Data: {dados.get('data')}\n"
    )
    try:
        with open("encomendas.txt", "a", encoding="utf-8") as f:
            f.write(linha)
        print("📝 Encomenda salva:", linha.strip())
    except Exception as e:
        print("❌ Erro ao salvar encomenda:", e)

async def responder_usuario(phone: str, mensagem: str):
    payload = {
        "phone": phone,
        "message": mensagem
    }
    headers = {
        "Content-Type": "application/json",
        "Client-Token": ZAPI_TOKEN
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(ZAPI_ENDPOINT_TEXT, json=payload, headers=headers)
            print("✅ Mensagem enviada:", response.status_code, response.text)
        except Exception as e:
            print("❌ Erro inesperado ao enviar mensagem:", repr(e))

async def processar_mensagem(mensagem: dict):
    texto = mensagem.get("text", {}).get("message", "").lower().strip()
    telefone = mensagem.get("phone")
    nome_cliente = mensagem.get("chatName", "Nome não informado")
     
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

    if telefone in estados_encomenda:
        if texto in ["recheios", "opções de bolo", "sabores"]:
            await responder_usuario(
                telefone,
                "🍰 *Veja nossos recheios e mousses para montar seu bolo:*\n\n"
                "*️Bolo com Fruta ou Nozes = adicional no valor*\n\n"
                "📌 *1ª Escolha 1 Recheio:*\n"
                "- Beijinho\n"
                "- Brigadeiro\n"
                "- Brigadeiro de Nutella\n"
                "- Brigadeiro Branco\n"
                "- Brigadeiro Branco Gourmet\n"
                "- Brigadeiro Branco de Ninho\n"
                "- Casadinho (brigadeiro branco + brigadeiro preto). _Esse sabor não adiciona mousse no recheio_\n"
                "- Doce de Leite\n\n"
                "📌 *2ª Escolha 1 tipo de Mousse:*\n"
                "- Ninho ou Trufa Branca\n"
                "- Chocolate ou Trufa Preta\n\n"
                "📝 Agora, digite qual recheio e mousse que você deseja:"
            )
            return

        etapa = estados_encomenda[telefone]["etapa"]
        dados = estados_encomenda[telefone]["dados"]

        if etapa == 1:
            dados["tipo"] = texto
            estados_encomenda[telefone]["etapa"] = 2
            await responder_usuario(telefone, "📏 Qual o tamanho do bolo? (ex: pequeno, médio, grande)")

        elif etapa == 2:
            dados["tamanho"] = texto
            estados_encomenda[telefone]["etapa"] = 3
            await responder_usuario(telefone, "📅 Para qual data você deseja o bolo?")

        elif etapa == 3:
            dados["data"] = texto
            salvar_encomenda(telefone, dados, nome_cliente)
            await responder_usuario(telefone, "✅ Obrigado! Sua encomenda foi registrada com sucesso 🎂")
            estados_encomenda.pop(telefone)
        return
    
    if telefone in estados_cafeteria:
        pedido = texto
        estado = estados_cafeteria[telefone]
        nome = estado["nome"]

        if pedido in ["finalizar", "só isso", "obrigado", "obrigada"]:
            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            itens = estado["itens"]
            linha = f"{agora} - {nome} | {telefone} | Pedido: {', '.join(itens)}\n"

            try:
                with open("pedidos_cafeteria.txt", "a", encoding="utf-8") as f:
                    f.write(linha)
                print("📝 Pedido do café salvo:", linha.strip())
            except Exception as e:
                print("❌ Erro ao salvar pedido do café:", e)

            estados_cafeteria.pop(telefone)
            await responder_usuario(telefone, "☕ Obrigado pelo seu pedido! Em breve confirmaremos com você.")
        else:
            estados_cafeteria[telefone]["itens"].append(pedido)
            await responder_usuario(telefone, "✅ Pedido registrado! Deseja pedir mais alguma coisa? Digite o item ou diga *finalizar*.")
        return
    
    if telefone in estados_entrega:
        estado = estados_entrega[telefone]
        etapa = estado["etapa"]
        dados = estado["dados"]
        nome = estado["nome"]

        if etapa == 1:
            dados["endereco"] = texto
            estados_entrega[telefone]["etapa"] = 2
            await responder_usuario(telefone, "📞 Informe um telefone alternativo ou referência, se tiver:")

        elif etapa == 2:
            dados["referencia"] = texto
            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            linha = f"{agora} - {nome} | {telefone} | Endereço: {dados['endereco']} | Referência: {dados['referencia']}\n"

            try:
                with open("entregas.txt", "a", encoding="utf-8") as f:
                    f.write(linha)
                print("📝 Entrega registrada:", linha.strip())
            except Exception as e:
                print("❌ Erro ao salvar entrega:", e)

            estados_entrega.pop(telefone)
            await responder_usuario(telefone, "🚚 Endereço registrado! Em breve confirmaremos o envio com você.")
        return

    if not telefone or not texto:
        print("❌ Dados incompletos:", mensagem)
        return

    salvar_cliente(telefone, nome_cliente)

    if is_saudacao(texto):
        resposta = (
            "🍫 Olá! Bem-vindo(a) à Chokodelícia 🍫\n"
            "Sou a Trufinha 🍬, assistente virtual da nossa cafeteria e confeitaria!\n\n"
            "Escolha uma opção:\n"
            "1️⃣ Ver cardápio\n"
            "2️⃣ Encomendar bolos\n"
            "3️⃣ Pedidos da cafeteria\n"
            "4️⃣ Entregas\n"
            "5️⃣ Falar com atendente"
        )
        await responder_usuario(telefone, resposta)

    elif texto in ["1", "cardápio", "cardapio"]:
        await responder_usuario(telefone, "📋 Aqui está nosso cardápio cheio de delícias:\nhttp://bit.ly/44ZlKlZ")

    elif texto in ["2", "bolo", "encomendar", "encomendas"]:
        estados_encomenda[telefone] = {"etapa": 1, "dados": {}}
        await responder_usuario(
            telefone,
            "🎂 Vamos fazer sua encomenda!\nQual o tipo de bolo que você deseja?\n\nDigite *recheios* para ver as opções disponíveis."
        )

    elif texto in ["3", "pedido", "cafeteria"]:
        estados_cafeteria[telefone] = {
            "itens": [],
            "nome": nome_cliente
}

        await responder_usuario(
            telefone,
            "☕ Vamos anotar seu pedido!\nDigite o que você deseja da cafeteria (ex: cappuccino, pão de queijo).\n\nDigite *finalizar* quando terminar seu pedido."
        )

    elif texto in ["4", "entrega", "informações de entrega"]:
        await responder_usuario(
            telefone,
            "🚚 Entregamos na cidade toda (R$10).\nPara outras regiões, o valor depende da distância (via Uber).\nHorário de entregas: 10h às 18h.\n\n📍 Por favor, informe o endereço completo para entrega (Rua, número, bairro):"
        )
        estados_entrega[telefone] = {"etapa": 1, "dados": {}, "nome": nome_cliente}

    elif texto in ["5", "atendente", "humano"]:
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        linha = f"{agora} - {nome_cliente} | {telefone} solicitou atendimento humano\n"

        try:
            with open("atendimentos.txt", "a", encoding="utf-8") as f:
                f.write(linha)
            print("🧑‍💻 Atendimento humano solicitado:", linha.strip())
        except Exception as e:
            print("❌ Erro ao registrar atendimento:", e)

        await responder_usuario(
            telefone,
            "👤 Sua solicitação foi registrada!\nEm breve um atendente humano falará com você pelo WhatsApp 😊"
        )


    else:
        await responder_usuario(telefone,
            "Desculpe, não entendi sua mensagem 😕\n"
            "Digite uma das opções abaixo:\n"
            "1️⃣ Ver cardápio\n"
            "2️⃣ Encomendar bolos\n"
            "3️⃣ Pedidos da cafeteria\n"
            "4️⃣ Entregas\n"
            "5️⃣ Falar com atendente"
        )
