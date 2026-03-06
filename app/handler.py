# app/handler.py
from datetime import datetime, timedelta
from collections import deque
from app.models.clientes import salvar_cliente
from app.security import get_admin_phones, hash_phone, preview_text
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
    if telefone in get_admin_phones():
        cmd = texto.lower()
        if cmd in ["desativar bot", "desligar bot", "pausar bot"]:
            set_bot_ativo(False)
            await responder_usuario(telefone, "🚫 Bot desativado temporariamente.")
            print(f"[ADMIN] bot_desativado phone_hash={hash_phone(telefone)}")
            return

        if cmd in ["ativar bot", "ligar bot", "reativar bot"]:
            set_bot_ativo(True)
            await responder_usuario(telefone, "✅ Bot reativado e pronto para atender!")
            print(f"[ADMIN] bot_reativado phone_hash={hash_phone(telefone)}")
            return

    # ====== VERIFICAÇÃO GLOBAL DO ESTADO DO BOT ======
    if not is_bot_ativo():
        print(
            f"[HANDLER] bot_desativado phone_hash={hash_phone(telefone)} "
            f"text='{preview_text(texto)}'"
        )
        return

    # ====== VALIDAÇÃO BÁSICA DE MENSAGEM ======
    if not telefone or not texto:
        print(
            "[HANDLER] dados_incompletos:",
            {
                "phone_hash": hash_phone(telefone),
                "text": preview_text(texto),
                "tipo": norm["message_type"],
            },
        )
        return


    agora = datetime.now()

    if msg_id and msg_id in mensagens_processadas:
        print(f"[HANDLER] webhook_duplicado message_id={msg_id} phone_hash={hash_phone(telefone)}")
        return
    if msg_id:
        mensagens_processadas.append(msg_id)

    ultima = ultimas_mensagens.get(telefone)
    if ultima and ultima["texto"] == texto and (agora - ultima["hora"]) < timedelta(seconds=2):
        print(
            f"[HANDLER] conteudo_duplicado phone_hash={hash_phone(telefone)} "
            f"text='{preview_text(texto)}'"
        )
        return
    ultimas_mensagens[telefone] = {"texto": texto, "hora": agora}
    # ====== CRIAR CLIENTE (necessário para todos os fluxos) ======
    from app.models.clientes import salvar_cliente
    cliente_id = salvar_cliente(telefone, nome_cliente)

    if telefone in estados_atendimento:
        estado = estados_atendimento[telefone]
        # Garantir que temos um timestamp
        if "inicio" not in estado:
            estado["inicio"] = agora.isoformat()
            
        ultimo_contato = datetime.fromisoformat(estado["inicio"])
        
        # Se passou de 30 minutos desde a última mensagem, reativa automaticamente
        if (agora - ultimo_contato) > timedelta(minutes=30):
            estados_atendimento.pop(telefone, None)
            await responder_usuario(telefone, "🤖 Oi! Como ficamos um tempinho sem nos falar, a Trufinha (IA) foi reativada. Se precisar de algo, estou aqui!")
            # O código continua e a IA vai processar a mensagem atual normalmente
        else:
            if texto in REATIVAR_BOT_OPCOES:
                estados_atendimento.pop(telefone, None)
                await responder_usuario(
                    telefone,
                    "🤖 Bot reativado. Como posso ajudar?"
                )
                return
            else:
                # Atualiza o cronômetro para manter o silêncio enquanto conversam
                estados_atendimento[telefone]["inicio"] = agora.isoformat()
                print(f"[HANDLER] atendimento_humano_ativo phone_hash={hash_phone(telefone)}")
                return

    # ====== PROCESSAMENTO VIA AGENTES DE IA ======
    from app.ai.runner import process_message_with_ai
    
    # Chama o Swarm de Agentes
    resposta_ia = await process_message_with_ai(telefone, texto, nome_cliente, cliente_id)
    
    # Envia a resposta final gerada pela IA (ou pelas tools) de volta ao cliente via WhatsApp
    await responder_usuario(telefone, resposta_ia)
    return
