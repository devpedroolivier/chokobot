from __future__ import annotations

from app.application.commands import GenerateAiReplyCommand


async def generate_ai_reply(command: GenerateAiReplyCommand) -> str:
    from app.ai.runner import process_message_with_ai

    return await process_message_with_ai(
        telefone=command.telefone,
        text=command.text,
        nome_cliente=command.nome_cliente,
        cliente_id=command.cliente_id,
        now=command.now,
    )
