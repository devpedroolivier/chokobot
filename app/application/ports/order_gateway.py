from __future__ import annotations

from typing import Protocol


class OrderGateway(Protocol):
    def create_order(
        self,
        *,
        phone: str,
        dados: dict,
        nome_cliente: str,
        cliente_id: int,
    ) -> int: ...

    def save_cafeteria_order(
        self,
        *,
        phone: str,
        itens: list[str],
        nome_cliente: str,
    ) -> None: ...

    def create_order_bundle(
        self,
        *,
        phone: str,
        dados: dict,
        nome_cliente: str,
        cliente_id: int,
        delivery_data: dict | None = None,
        process_data: dict | None = None,
        sweet_items: list[dict] | None = None,
    ) -> int: ...
