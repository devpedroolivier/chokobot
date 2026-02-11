import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from app.handler import processar_mensagem
from app.security import validate_webhook_request

router = APIRouter()


def print_painel(body: dict):
    nome = body.get("chatName", "Desconhecido")
    numero = body.get("phone", "N/A")
    texto = body.get("text", {}).get("message", "")
    hora = datetime.now().strftime("%d/%m/%Y %H:%M")

    print("\n" + "=" * 50)
    print("NOVA MENSAGEM RECEBIDA")
    print(f"Nome: {nome}")
    print(f"Numero: {numero}")
    print(f"Mensagem: {texto}")
    print(f"Horario: {hora}")
    print("=" * 50 + "\n")


@router.post("/webhook")
async def receber_webhook(request: Request):
    raw_body = await request.body()
    validate_webhook_request(request, raw_body)

    try:
        body = json.loads(raw_body.decode("utf-8") or "{}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="JSON invalido") from exc

    if body.get("fromMe") or body.get("type") == "DeliveryCallback":
        print("Ignorado: mensagem enviada por mim ou callback de entrega.")
        return {"status": "ignored"}

    print_painel(body)
    await processar_mensagem(body)
    return {"status": "ok"}
