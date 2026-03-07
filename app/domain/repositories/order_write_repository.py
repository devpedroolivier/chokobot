from __future__ import annotations

from typing import Protocol


class OrderWriteRepository(Protocol):
    def save_order_payload(
        self,
        *,
        phone: str,
        dados: dict,
        nome_cliente: str,
        cliente_id: int | None = None,
    ) -> int: ...

    def save_cafeteria_items(
        self,
        *,
        phone: str,
        itens: list[str],
        nome_cliente: str = "Nome não informado",
    ) -> None: ...
