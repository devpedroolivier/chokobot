from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


# ``tenant_id`` is plumbed through every command for forward
# compatibility with Phase B's per-tenant routing. Default ``None``
# keeps the legacy single-tenant Chokodelícia behaviour: tenant_id is
# resolved at the edge (webhook / panel) and propagated downstream
# without further lookups.

@dataclass(frozen=True)
class HandleInboundMessageCommand:
    payload: dict
    tenant_id: str | None = None


@dataclass(frozen=True)
class GenerateAiReplyCommand:
    telefone: str
    text: str
    nome_cliente: str
    cliente_id: int
    now: datetime | None = None
    tenant_id: str | None = None
