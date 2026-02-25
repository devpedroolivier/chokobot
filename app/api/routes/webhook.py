from fastapi import APIRouter, Request
from datetime import datetime
import traceback
from app.handler import processar_mensagem
from app.utils.payload import normalize_incoming, is_group_message
from app.utils.mensagens import responder_usuario

router = APIRouter()

def print_painel(body: dict):
    norm = normalize_incoming(body)
    nome = norm["chat_name"]
    numero = norm["phone"] or "N/A"
    texto = norm["text"]
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
    if is_group_message(body):
        print("ℹ️ Ignorado: mensagem de grupo.")
        return {"status": "ignored"}

    print_painel(body)

    try:
        await processar_mensagem(body)
        return {"status": "ok"}
    except Exception as exc:
        print(f"❌ Erro ao processar webhook: {exc}")
        traceback.print_exc()
        phone = normalize_incoming(body).get("phone")
        if phone:
            await responder_usuario(
                phone,
                "⚠️ Tive um problema interno ao processar sua mensagem. Pode repetir em instantes?"
            )
        return {"status": "error"}
