# app/handler.py
from datetime import datetime, timedelta
from collections import deque
from app.models.clientes import salvar_cliente
from app.utils.mensagens import responder_usuario, is_saudacao
from app.utils.payload import normalize_incoming
from app.services.encomendas import processar_encomenda
from app.services.cafeteria import processar_cafeteria
from app.services.cestas_box import processar_cestas_box
from app.services.entregas import processar_entrega
from app.services.atendimento import processar_atendimento
from app.services.estados import (
    estados_encomenda,
    estados_entrega,
    estados_cafeteria,
    estados_cestas_box,
    estados_atendimento,
    is_bot_ativo,
    set_bot_ativo,
)
from app.config import CAFETERIA_URL, DOCES_URL


CANCELAR_OPCOES = ["cancelar", "sair", "parar", "desistir"]
MENU_OPCOES = ["menu", "voltar", "inicio", "principal", "bot"]
REATIVAR_BOT_OPCOES = ["voltar", "menu", "bot", "reativar", "voltar ao bot"]

MENU_OPTIONS = [
    "1️⃣ Pronta Entrega B3 ou B4 — sabores disponíveis hoje",
    "2️⃣ Ver cardápios",
    "3️⃣ Encomendar bolos ou tortas",
    "4️⃣ Pedidos Delivery Cafeteria",
    "5️⃣ Cestas Box Café ou Chocolate",
    "6️⃣ Entregas 🚚",
    "7️⃣ Docinhos 🍬",
    "8️⃣ Falar com atendente 👩‍🍳",
]
MENU_PROMPT = "Escolha uma opção:\n" + "\n".join(MENU_OPTIONS)
MAIN_MENU_GREETING = (
    "🍫 Olá! Bem-vindo(a) à *Chokodelícia* 🍫\n"
    "Sou a *Trufinha* 🍬, assistente virtual da nossa Cafeteria e Doceria!"
)
MAIN_MENU_MESSAGE = f"{MAIN_MENU_GREETING}\n\n{MENU_PROMPT}"
MENU_PRINCIPAL_MESSAGE = f"🍫 *Menu Principal*\n{MENU_PROMPT}"

mensagens_processadas = deque(maxlen=2000)
ultimas_mensagens = {}

async def processar_mensagem(mensagem: dict):
    norm = normalize_incoming(mensagem)
    texto = norm["text"]
    if texto:
        texto = texto.lower().strip()
    telefone = norm["phone"]
    nome_cliente = norm["chat_name"] or "Nome não informado"
    msg_id = norm["message_id"]

    

    # ====== COMANDOS DE ADMINISTRADOR ======
    if telefone in ["5516992622680"]:  # 👈 seu número adminn
        cmd = texto.lower()
        if cmd in ["desativar bot", "desligar bot", "pausar bot"]:
            set_bot_ativo(False)
            await responder_usuario(telefone, "🚫 Bot desativado temporariamente.")
            print("🚫 BOT DESATIVADO PELO ADMIN.")
            return

        if cmd in ["ativar bot", "ligar bot", "reativar bot"]:
            set_bot_ativo(True)
            await responder_usuario(telefone, "✅ Bot reativado e pronto para atender!")
            print("✅ BOT REATIVADO PELO ADMIN.")
            return

    # ====== VERIFICAÇÃO GLOBAL DO ESTADO DO BOT ======
    if not is_bot_ativo():
        print(f"⚠️ BOT DESATIVADO — Mensagem ignorada de {telefone}: {texto}")
        return

    # ====== VALIDAÇÃO BÁSICA DE MENSAGEM ======
    if not telefone or not texto:
        print("❌ Dados incompletos:", {"telefone": telefone, "texto": texto, "tipo": norm["message_type"]})
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
    # ====== CRIAR CLIENTE (necessário para todos os fluxos) ======
    from app.models.clientes import salvar_cliente
    cliente_id = salvar_cliente(telefone, nome_cliente)


    if telefone in estados_atendimento:
        if texto in REATIVAR_BOT_OPCOES:
            estados_atendimento.pop(telefone, None)
            await responder_usuario(
                telefone,
                "🤖 Bot reativado. Vamos continuar!\n"
                f"{MENU_PROMPT}"
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
        await responder_usuario(telefone, MENU_PRINCIPAL_MESSAGE)
        return


    if telefone in estados_entrega:
        estado = estados_entrega[telefone]
        resultado = await processar_entrega(telefone, texto, estado)
        estados_entrega[telefone] = estado
        if resultado == "finalizar":
            estados_entrega.pop(telefone, None)
            estados_encomenda.pop(telefone, None)
        return

    if telefone in estados_cestas_box:
        estado = estados_cestas_box[telefone]
        resultado = await processar_cestas_box(telefone, texto, estado, nome_cliente, cliente_id)
        estados_cestas_box[telefone] = estado
        if resultado == "finalizar":
            estados_cestas_box.pop(telefone, None)
        return

    if telefone in estados_encomenda:
        estado = estados_encomenda[telefone]
        resultado = await processar_encomenda(telefone, texto, estado, nome_cliente, cliente_id)

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
                f"🍫 Olá novamente!\n{MENU_PROMPT}"
            )

        elif resultado == "finalizar":
            estados_cafeteria.pop(telefone, None)

        return




    if is_saudacao(texto):
        await responder_usuario(telefone, MAIN_MENU_MESSAGE)
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
            "3️⃣ Cardápio Doces\n"
            "4️⃣ Cardápio Cestas Box/Presentes\n"
            "5️⃣ Cardápio Páscoa Inesquecível"
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
            "5️⃣ Tortas\n"
            "6️⃣ Linha Simples\n\n"

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

    elif texto in ["5", "cestas", "cesta", "box", "chocolate", "café", "cafe"]:
        estados_cestas_box[telefone] = {"etapa": "selecao", "dados": {}}
        from app.services.cestas_box import montar_menu_cestas
        await responder_usuario(telefone, montar_menu_cestas())
        return

    elif texto in ["6", "entrega", "informações de entrega", "delivery"]:
        await responder_usuario(
            telefone,
            "🚚 Entregamos em *Pitangueiras-SP* (taxa R$10) *exceto zona rural*.\n"
            "Ibitiuva, zona rural ou Usina: combinar valor especial.\n"
            "Para outras regiões, o valor depende da distância (via Uber).\n"
            "Horário de entregas: 10h às 18h."
        )
        return

    elif texto in ["7", "doces", "docinhos"]:
        await responder_usuario(
            telefone,
            f"🍬 *Docinhos*\n"
            f"Cardápio: {DOCES_URL}\n"
            "Envie os itens que deseja (ex: Brigadeiro Belga x25). "
            "Em seguida confirmamos o valor, formas de entrega e pagamento."
        )
        return

    elif texto in ["8", "atendente", "humano", "falar"]:
        await processar_atendimento(telefone, nome_cliente)
        return

    else:
        await responder_usuario(
            telefone,
            f"Desculpe, não entendi sua mensagem 😕\n{MENU_PROMPT}"
        )
