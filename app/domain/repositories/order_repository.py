from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OrderPanelItem:
    id: int
    cliente_nome: str
    produto: str | None
    categoria: str | None
    data_entrega: str | None
    horario: str | None
    valor_total: float | None
    status: str
    tipo: str
    criado_em: str | None


class OrderRepository(Protocol):
    def list_for_main_panel(
        self, *, tenant_id: str | None = None
    ) -> list[OrderPanelItem]: ...

    def list_for_orders_page(self, *, tenant_id: str | None = None) -> list[tuple]: ...

    def export_rows(self, *, tenant_id: str | None = None) -> list[tuple]: ...

    def create_order(
        self,
        *,
        nome: str,
        telefone: str,
        categoria: str,
        produto: str,
        tamanho: str,
        massa: str | None = None,
        recheio: str | None = None,
        mousse: str | None = None,
        adicional: str | None = None,
        horario: str | None = None,
        valor_total: str,
        data_entrega: str,
        tenant_id: str | None = None,
    ) -> int: ...

    def delete_order(self, order_id: int, *, tenant_id: str | None = None) -> None: ...

    def get_order_details(
        self, order_id: int, *, tenant_id: str | None = None
    ) -> dict | None: ...

    def list_by_phone(
        self, phone: str, *, limit: int = 10, tenant_id: str | None = None
    ) -> list[dict]: ...

    def upsert_delivery_status(
        self, order_id: int, status: str, *, tenant_id: str | None = None
    ) -> None: ...
