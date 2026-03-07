from __future__ import annotations

from typing import Protocol


class CatalogGateway(Protocol):
    def get_menu(self, category: str = "todas") -> str: ...

    def get_learnings(self) -> str: ...

    def save_learning(self, aprendizado: str) -> str: ...
