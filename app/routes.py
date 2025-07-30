from fastapi import APIRouter, Request
from app.handler import processar_mensagem
from datetime import datetime

router = APIRouter()

def print_painel(body: dict):
    nome = body.get("chatName", "Desconhecido")
    numero = body.get("phone", "N/A")
    texto = body.get("text", {}).get("message", "")
    hora = datetime.now().strftime("%d/%m/%Y %H:%M")

    print("\n" + "=" * 50)
    print("📬 NOVA MENSAGEM RECEBIDA")
    print(f"👤 Nome: {nome}")
    print(f"📱 Número: {numero}")
    print(f"💬 Mensagem: {texto}")
    print(f"🕐 Horário: {hora}")
    print("=" * 50 + "\n")

@router.post("/webhook")
async def receber_webhook(request: Request):
    body = await request.json()

    # Ignora mensagens que não são do usuário
    if body.get("fromMe") or body.get("type") == "DeliveryCallback":
        print("ℹ️ Ignorado: mensagem enviada por mim ou callback de entrega.")
        return {"status": "ignored"}

    # Mostra o mini painel
    print_painel(body)

    # Processa a mensagem
    await processar_mensagem(body)
    return {"status": "ok"}
