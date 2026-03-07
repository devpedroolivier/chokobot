from __future__ import annotations

from app.application.commands import GenerateAiReplyCommand, HandleInboundMessageCommand
from app.application.service_registry import get_command_bus


class LocalConversationGateway:
    async def handle_inbound_message(self, payload: dict) -> None:
        await get_command_bus().dispatch(HandleInboundMessageCommand(payload=payload))

    async def generate_reply(
        self,
        *,
        telefone: str,
        text: str,
        nome_cliente: str,
        cliente_id: int,
    ) -> str:
        return await get_command_bus().dispatch(
            GenerateAiReplyCommand(
                telefone=telefone,
                text=text,
                nome_cliente=nome_cliente,
                cliente_id=cliente_id,
            )
        )
