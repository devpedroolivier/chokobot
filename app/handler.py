from app.application.use_cases.process_inbound_message import (
    generate_ai_reply,
    process_inbound_message,
    save_customer_contact,
)
from app.utils.mensagens import responder_usuario

gerar_resposta_ia = generate_ai_reply

async def processar_mensagem(mensagem: dict):
    return await process_inbound_message(
        mensagem,
        responder_usuario_fn=responder_usuario,
        gerar_resposta_ia_fn=gerar_resposta_ia,
        save_customer_fn=save_customer_contact,
    )
