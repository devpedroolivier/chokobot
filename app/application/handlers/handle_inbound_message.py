from __future__ import annotations

from app.application.commands import HandleInboundMessageCommand
from app.application.use_cases.process_inbound_message import process_inbound_message


async def handle_inbound_message(command: HandleInboundMessageCommand) -> None:
    await process_inbound_message(command.payload)
