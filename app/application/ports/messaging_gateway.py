from __future__ import annotations

from typing import Protocol


class MessagingGateway(Protocol):
    async def send_text(self, phone: str, mensagem: str) -> bool: ...
