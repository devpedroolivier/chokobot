from fastapi import APIRouter, Request
from app.handler import processar_mensagem

router = APIRouter()

@router.post("/webhook")
async def receber_webhook(request: Request):
    body = await request.json()
    print("📩 Webhook recebido:", body)

    # Ignora mensagens que não são do usuário
    if body.get("fromMe") or body.get("type") == "DeliveryCallback":
        print("ℹ️ Ignorado: mensagem enviada por mim ou callback de entrega.")
        return {"status": "ignored"}

    await processar_mensagem(body)
    return {"status": "ok"}
