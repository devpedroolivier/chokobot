from __future__ import annotations

from typing import Protocol


class ConversationGateway(Protocol):
    async def handle_inbound_message(self, payload: dict) -> None: ...

    async def generate_reply(
        self,
        *,
        telefone: str,
        text: str,
        nome_cliente: str,
        cliente_id: int,
    ) -> str: ...
