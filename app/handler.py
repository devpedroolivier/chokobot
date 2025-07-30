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
            with open("dados/clientes.txt", "r", encoding="utf-8") as f:
                if any(phone in linha for linha in f):
                    print(f"🔁 Número já registrado: {phone}")
                    return
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        linha = f"{agora} - {nome} | {phone}\n"
        with open("dados/clientes.txt", "a", encoding="utf-8") as f:
            f.write(linha)
        print("📝 Cliente salvo:", linha.strip())
    except Exception as e:
        print("❌ Erro ao salvar cliente:", e)

def salvar_encomenda(phone: str, dados: dict, nome: str = "Nome não informado"):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    linha_bolo = dados.get("linha", "Normal").lower()

    if linha_bolo in ["gourmet", "redondo", "torta"]:
        linha = (
            f"{agora} - {nome} | {phone} | "
            f"Linha: {dados.get('linha')} | "
            f"Bolo: {dados.get('gourmet', 'Não informado')} | "
            f"Data: {dados.get('data', dados.get('pronta_entrega', '-'))}\n"
        )
    else:
        linha = (
            f"{agora} - {nome} | {phone} | "
            f"Linha: {dados.get('linha', 'Normal')} | "
            f"Massa: {dados.get('massa', '-') } | "
            f"Recheio: {dados.get('recheio', '-') } | "
            f"Mousse: {dados.get('mousse', '-') } | "
            f"Adicional: {dados.get('adicional', 'Nenhum')} | "
            f"Tamanho: {dados.get('tamanho', '-')} | "
            f"Data: {dados.get('data', dados.get('pronta_entrega', '-'))}\n"
        )

    try:
        with open("dados/encomendas.txt", "a", encoding="utf-8") as f:
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
            print("\n📤 ENVIANDO MENSAGEM")
            print(f"📱 Para: {phone}")
            print(f"💬 Conteúdo:\n{mensagem}\n")

            response = await client.post(ZAPI_ENDPOINT_TEXT, json=payload, headers=headers)

            print(f"✅ Enviado com sucesso! Código: {response.status_code}")
            print(f"📦 Retorno: {response.text}\n" + "-"*50)

        except Exception as e:
            print("❌ Erro inesperado ao enviar mensagem:")
            print(repr(e))
            print("-" * 50)

async def processar_mensagem(mensagem: dict):
    texto = mensagem.get("text", {}).get("message", "").lower().strip()
    telefone = mensagem.get("phone")
    nome_cliente = mensagem.get("chatName", "Nome não informado")

    if not telefone or not texto:
        print("❌ Dados incompletos:", mensagem)
        return

    # Verificação de submenu de cardápios
    if telefone in estados_cafeteria:
        estado = estados_cafeteria[telefone]

        if estado.get("subetapa") == "aguardando_cardapio":
            mensagem = ""

            if texto == "1":
                mensagem = (
                    "📋 Aqui está nosso cardápio *Cafeteria*:\n"
                    "http://bit.ly/44ZlKlZ\n"
                )
            elif texto == "2":
                mensagem = (
                    "📋 Aqui está nosso cardápio *Bolos*:\n"
                    "https://keepo.io/boloschoko/\n"
                )
            elif texto == "3":
                mensagem = (
                    "📋 Aqui está nosso cardápio *Doces*:\n"
                    "https://bit.ly/cardapiodoceschoko\n"
                )
            elif texto == "4":
                mensagem = (
                    "📋 Aqui está nosso cardápio *Sazonais*:\n"
                    "https://drive.google.com/file/d/1HkfUa5fiIJ2_CmUwFiCSp1RToaJfvu6T/view\n"
                )
            else:
                await responder_usuario(telefone, "❌ Opção inválida. Digite 1, 2, 3 ou 4.")
                return

            mensagem += (
                "\n📖 Deseja ver outro cardápio ou voltar ao menu principal?\n"
                "1️⃣ Ver outro cardápio\n"
                "2️⃣ Voltar ao menu"
            )

            await responder_usuario(telefone, mensagem)
            estados_cafeteria[telefone]["subetapa"] = "cardapio_exibido"
            return


        elif estado.get("subetapa") == "cardapio_exibido":
            if texto == "1":
                estados_cafeteria[telefone]["subetapa"] = "aguardando_cardapio"
                await responder_usuario(
                    telefone,
                    "📋 Qual cardápio você deseja ver?\n"
                    "1️⃣ Cardápio Cafeteria\n"
                    "2️⃣ Cardápio Bolos\n"
                    "3️⃣ Cardápio Doces\n"
                    "4️⃣ Cardápio Sazonais"
                )
            elif texto == "2":
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
            else:
                await responder_usuario(telefone, "❌ Opção inválida. Digite 1 para ver outro cardápio ou 2 para voltar ao menu.")
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

    # Encomendas (Fluxo interativo "Monte seu Bolo")
    if telefone in estados_encomenda:
        etapa = estados_encomenda[telefone]["etapa"]
        dados = estados_encomenda[telefone]["dados"]

        if etapa == 1:
            if texto in ["1", "normal", "personalizado"]:
                estados_encomenda[telefone]["linha"] = "normal"
                estados_encomenda[telefone]["etapa"] = "massa"
                await responder_usuario(
                    telefone,
                    "🍰 *Monte seu bolo personalizado!*\n\n"
                    "1️⃣ Escolha a massa:\n"
                    "- Branca\n- Chocolate\n- Mesclada"
                )
                return

            elif texto in ["2", "gourmet"]:
                estados_encomenda[telefone]["linha"] = "gourmet"
                estados_encomenda[telefone]["etapa"] = "gourmet"
                await responder_usuario(
                    telefone,
                    "✨ *Linha Gourmet:*\n"
                    "- Bolo Inglês\n- Inglês Belga\n- Floresta Negra\n"
                    "- Língua de Gato\n- Ninho com Morango\n"
                    "- Nozes com Doce de Leite\n- Olho de Sogra\n- Red Velvet\n\n"
                    "📷 Veja fotos e preços no cardápio: https://keepo.io/boloschoko/\n\n"
                    "📝 Digite o nome do bolo desejado:"
                )
                return

            elif texto in ["3", "p6", "redondo", "bolo redondo"]:
                estados_encomenda[telefone]["linha"] = "redondo"
                estados_encomenda[telefone]["etapa"] = "gourmet"
                await responder_usuario(
                    telefone,
                    "🍥 *Bolos Redondos P6 (serve 20 pessoas):*\n"
                    "- P6 Língua de Gato de Chocolate\n"
                    "- P6 Língua de Gato de Chocolate Branco\n"
                    "- P6 Camafeu\n"
                    "- P6 Naked Cake\n"
                    "- P6 Red Velvet\n\n"
                    "📷 Veja fotos e preços no cardápio: https://keepo.io/boloschoko/\n\n"
                    "📝 Digite o nome do bolo desejado:"
                )
                return

            elif texto in ["4", "torta", "tortas"]:
                estados_encomenda[telefone]["linha"] = "torta"
                estados_encomenda[telefone]["etapa"] = "gourmet"
                await responder_usuario(
                    telefone,
                    "🥧 *Tortas (serve 16 pessoas):*\n"
                    "- Torta Argentina\n- Torta Banoffee\n"
                    "- Cheesecake Tradicional\n- Cheesecake Pistache\n"
                    "- Citrus Pie\n- Torta Limão\n\n"
                    "📷 Veja fotos e preços no cardápio: https://keepo.io/boloschoko/\n\n"
                    "📝 Digite o nome da torta desejada:"
                )
                return

            else:
                await responder_usuario(
                    telefone,
                    "🎂 *Escolha uma linha de bolo para começar:*\n"
                    "1️⃣ Montar bolo personalizado\n"
                    "2️⃣ Linha Gourmet\n"
                    "3️⃣ Bolos Redondos (P6)\n"
                    "4️⃣ Tortas\n\n"
                    "Digite o número ou nome da linha desejada."
                )
                return


        if etapa == 2:
            if "+" not in texto:
                await responder_usuario(telefone, "⚠️ Por favor, envie o recheio e mousse no formato: Brigadeiro + Ninho")
                return
            recheio, mousse = map(str.strip, texto.split("+", 1))
            dados["recheio"] = recheio
            dados["mousse"] = mousse
            estados_encomenda[telefone]["etapa"] = 3
            await responder_usuario(
                telefone,
                "🍓 Deseja adicionar alguma fruta ou noz? (R$ adicional)\n"
                "- Morango\n- Abacaxi\n- Ameixa\n- Nozes\n\n"
                "Ou digite *não* para pular."
            )
            return

        if etapa == 3:
            dados["adicional"] = texto if texto != "não" else "Nenhum"
            estados_encomenda[telefone]["etapa"] = 4
            await responder_usuario(
                telefone,
                "📏 Escolha o tamanho do bolo:\n"
                "- Mini (15 pessoas)\n- Pequeno (30 pessoas)\n"
                "- Médio (50 pessoas)\n- Grande (80 pessoas)"
            )
            return

        if etapa == 4:
            dados["tamanho"] = texto
            estados_encomenda[telefone]["etapa"] = 5
            await responder_usuario(
                telefone,
                "📆 Para qual data deseja o bolo?\n"
                "⚠️ *Precisa de 2 dias de antecedência.*\n\n"
                "Ou digite *pronta entrega* para ver sabores disponíveis hoje."
            )
            return

        if etapa == 5:
            if "pronta entrega" in texto:
                await responder_usuario(
                    telefone,
                    "📦 *Pronta entrega disponível hoje:*\n"
                    "- B3 Mesclado com Brigadeiro e Ninho\n"
                    "- B4 Mesclado com Brigadeiro e Ninho\n\n"
                    "Digite o nome do bolo desejado para confirmar."
                )
                estados_encomenda[telefone]["etapa"] = "confirmar_pronta"
                return
            else:
                dados["data"] = texto
                salvar_encomenda(telefone, dados, nome_cliente)
                await responder_usuario(telefone, "✅ Obrigado! Sua encomenda foi registrada com sucesso 🎂")
                estados_encomenda.pop(telefone)
                return

        if etapa == "confirmar_pronta":
            dados["pronta_entrega"] = texto
            salvar_encomenda(telefone, dados, nome_cliente)
            await responder_usuario(telefone, "✅ Pronta entrega registrada! Em breve confirmaremos com você 🎉")
            estados_encomenda.pop(telefone)
            return

        if etapa == "gourmet":
            dados["linha"] = estados_encomenda[telefone]["linha"]
            dados["gourmet"] = texto  # armazena o nome do bolo
            estados_encomenda[telefone]["etapa"] = 5
            await responder_usuario(
                telefone,
                "📆 Para qual data deseja o bolo?\n"
                "⚠️ *Precisa de 2 dias de antecedência.*\n\n"
                "Ou digite *pronta entrega* para ver sabores disponíveis hoje."
            )
            return



    # Pedido cafeteria
    if telefone in estados_cafeteria and estados_cafeteria[telefone].get("itens"):
        pedido = texto
        estado = estados_cafeteria[telefone]
        nome = estado["nome"]

        if pedido in ["finalizar", "só isso", "obrigado", "obrigada"]:
            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            itens = estado["itens"]
            linha = f"{agora} - {nome} | {telefone} | Pedido: {', '.join(itens)}\n"

            try:
                with open("dados/pedidos_cafeteria.txt", "a", encoding="utf-8") as f:
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

    # Entregas
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
                with open("dados/entregas.txt", "a", encoding="utf-8") as f:
                    f.write(linha)
                print("📝 Entrega registrada:", linha.strip())
            except Exception as e:
                print("❌ Erro ao salvar entrega:", e)

            estados_entrega.pop(telefone)
            await responder_usuario(telefone, "🚚 Endereço registrado! Em breve confirmaremos o envio com você.")
        return

    # Mensagens principais
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
        await responder_usuario(
            telefone,
            "📋 Qual cardápio você deseja ver?\n"
            "1️⃣ Cardápio Cafeteria\n"
            "2️⃣ Cardápio Bolos\n"
            "3️⃣ Cardápio Doces\n"
            "4️⃣ Cardápio Sazonais"
        )
        estados_cafeteria[telefone] = {
            "subetapa": "aguardando_cardapio"
        }

    elif texto in ["2", "bolo", "encomendar", "encomendas"]:
        estados_encomenda[telefone] = {
            "etapa": 1,
            "dados": {}
        }
        await responder_usuario(
            telefone,
            "🎂 *Vamos começar sua encomenda!*\n\n"
            "Qual linha de bolo você deseja?\n"
            "1️⃣ Montar bolo personalizado\n"
            "2️⃣ Linha Gourmet\n"
            "3️⃣ Bolos Redondos (P6)\n"
            "4️⃣ Tortas\n\n"
            "📷 Para ver fotos e preços, consulte nosso cardápio: https://keepo.io/boloschoko/"
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
            with open("dados/atendimentos.txt", "a", encoding="utf-8") as f:
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
