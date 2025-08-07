import httpx
from app.config import ZAPI_ENDPOINT_TEXT, ZAPI_TOKEN

SAUDACOES = ["oi","iae","salve", "olá", "ola", "bom dia", "boa tarde", "boa noite"]

def is_saudacao(texto: str) -> bool:
    return any(sauda in texto.lower() for sauda in SAUDACOES)

async def responder_usuario(phone: str, mensagem: str):
    payload = {"phone": phone, "message": mensagem}
    headers = {
        "Content-Type": "application/json",
        "Client-Token": ZAPI_TOKEN
    }

    async with httpx.AsyncClient() as client:
        try:
            print(f"\n📤 ENVIANDO MENSAGEM\n📱 Para: {phone}\n💬 Conteúdo:\n{mensagem}\n")
            response = await client.post(ZAPI_ENDPOINT_TEXT, json=payload, headers=headers)
            print(f"✅ Enviado! Código: {response.status_code}")
            print(f"📦 Retorno: {response.text}\n" + "-"*50)
        except Exception as e:
            print("❌ Erro ao enviar mensagem:", repr(e))
