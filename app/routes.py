from fastapi import APIRouter, Request
from app.handler import processar_mensagem

router = APIRouter()

@router.post("/webhook")
async def receber_webhook(request: Request):
    body = await request.json()
    mensagem = body.get("message", {})  # depende da estrutura da Z-API
    await processar_mensagem(mensagem)
    return {"status": "ok"}
