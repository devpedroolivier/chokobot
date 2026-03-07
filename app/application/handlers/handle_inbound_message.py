from __future__ import annotations

from app.application.commands import HandleInboundMessageCommand


async def handle_inbound_message(command: HandleInboundMessageCommand) -> None:
    from app.handler import processar_mensagem

    await processar_mensagem(command.payload)
