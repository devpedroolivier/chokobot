from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _event_time() -> str:
    return datetime.utcnow().isoformat() + "Z"


@dataclass(frozen=True)
class MessageReceivedEvent:
    payload: dict[str, Any]
    occurred_at: str = field(default_factory=_event_time)


@dataclass(frozen=True)
class AiReplyGeneratedEvent:
    telefone: str
    nome_cliente: str
    reply: str
    occurred_at: str = field(default_factory=_event_time)


@dataclass(frozen=True)
class OrderCreatedEvent:
    order_id: int
    phone: str
    nome_cliente: str
    categoria: str
    source: str
    occurred_at: str = field(default_factory=_event_time)


@dataclass(frozen=True)
class OrderClosedByBotEvent:
    phone: str
    agente: str
    ferramenta: str
    order_id: int | None
    protocolo: str | None
    occurred_at: str = field(default_factory=_event_time)


@dataclass(frozen=True)
class HumanHandoffEscalatedEvent:
    phone: str
    nome: str
    motivo: str
    categoria: str
    origem: str
    occurred_at: str = field(default_factory=_event_time)
