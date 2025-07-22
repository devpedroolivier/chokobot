import httpx
from app.config import ZAPI_URL, ZAPI_TOKEN

SAUDACOES = ["oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]

def is_saudacao(texto: str) -> bool:
    texto = texto.lower()
    return any(sauda in texto for sauda in SAUDACOES)

import httpx
from app.config import ZAPI_URL, ZAPI_TOKEN

async def responder_usuario(phone: str, mensagem: str):
    payload = {
        "phone": phone,
        "message": mensagem
    }
    headers = {
        "Content-Type": "application/json",
        "Client-Token": ZAPI_TOKEN  # necessário para autenticar
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(ZAPI_URL, json=payload, headers=headers)
            print("✅ Mensagem enviada:", response.status_code, response.text)
        except Exception as e:
            print("❌ Erro ao enviar mensagem:", e)


async def processar_mensagem(mensagem: dict):
    texto = mensagem.get("body", "").lower().strip()
    telefone = mensagem.get("phone")

    if is_saudacao(texto):
        resposta = (
            "🍫 Olá! Bem-vindo(a) à Chokodelícia 💕\n"
            "Sou o assistente virtual da nossa cafeteria e confeitaria!\n\n"
            "Qual opção você deseja:\n"
            "1 - Nosso cardápio\n"
            "2 - Encomendas de bolos\n"
            "3 - Pedidos da cafeteria\n"
            "4 - Informações sobre entregas\n\n"
            "Digite a opção desejada! 😊"
        )
        await responder_usuario(telefone, resposta)
    
    elif texto in ["1", "cardápio", "cardapio"]:
        await responder_usuario(telefone, "📋 Aqui está nosso cardápio completo, cheio de delícias:\nhttps://seusite.com/cardapio.pdf\n\nQualquer dúvida é só me chamar! 😊")
    
    elif texto in ["2", "bolo", "encomendar", "encomendas"]:
        await responder_usuario(telefone, "🎂 Para encomendar um bolo, envie uma mensagem com o tipo, tamanho e data desejada.\nNosso time vai te responder rapidinho! 😊")
    
    elif texto in ["3", "pedido", "cafeteria"]:
        await responder_usuario(telefone, "☕ Para pedidos da cafeteria, acesse o link: https://seusite.com/pedidos ou envie o pedido por aqui mesmo!")
    
    elif texto in ["4", "entrega", "informações de entrega"]:
        await responder_usuario(telefone, "🚚 Fazemos entregas em toda a região da Vila Mariana!\nHorários: 10h às 18h. Frete grátis acima de R$ 60! 😉")
    
    else:
        await responder_usuario(telefone, "Desculpe, não entendi sua mensagem 😕\nPor favor, digite uma das opções do menu ou fale com um atendente!")

