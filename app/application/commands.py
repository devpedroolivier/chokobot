from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class HandleInboundMessageCommand:
    payload: dict


@dataclass(frozen=True)
class GenerateAiReplyCommand:
    telefone: str
    text: str
    nome_cliente: str
    cliente_id: int
    now: datetime | None = None
