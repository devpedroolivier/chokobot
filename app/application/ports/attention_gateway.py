from __future__ import annotations

from typing import Protocol


class AttentionGateway(Protocol):
    def activate_human_handoff(self, *, telefone: str, motivo: str, context: dict | None = None) -> str: ...

    def deactivate_human_handoff(self, *, telefone: str) -> bool: ...
