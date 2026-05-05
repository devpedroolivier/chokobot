from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _event_time() -> str:
    return datetime.utcnow().isoformat() + "Z"


@dataclass(frozen=True)
class MessageReceivedEvent:
    payload: dict[str, Any]
    tenant_id: str | None = None
    occurred_at: str = field(default_factory=_event_time)


@dataclass(frozen=True)
class AiReplyGeneratedEvent:
    telefone: str
    nome_cliente: str
    reply: str
    tenant_id: str | None = None
    occurred_at: str = field(default_factory=_event_time)


@dataclass(frozen=True)
class OrderCreatedEvent:
    order_id: int
    phone: str
    nome_cliente: str
    categoria: str
    source: str
    tenant_id: str | None = None
    occurred_at: str = field(default_factory=_event_time)


@dataclass(frozen=True)
class OrderClosedByBotEvent:
    phone: str
    agente: str
    ferramenta: str
    order_id: int | None
    protocolo: str | None
    tenant_id: str | None = None
    occurred_at: str = field(default_factory=_event_time)


@dataclass(frozen=True)
class HumanHandoffEscalatedEvent:
    phone: str
    nome: str
    motivo: str
    categoria: str
    origem: str
    tenant_id: str | None = None
    occurred_at: str = field(default_factory=_event_time)


@dataclass(frozen=True)
class AiReplySkippedEvent:
    """Emitido quando uma mensagem do cliente entra mas a IA decide não responder.

    Reduz o "buraco preto" entre MessageReceivedEvent (8.153) e
    AiReplyGeneratedEvent (5.395) — antes desse evento, ~35% das mensagens
    sumiam silenciosamente sem motivo registrado.
    """

    phone: str
    motivo: str
    tenant_id: str | None = None
    occurred_at: str = field(default_factory=_event_time)
