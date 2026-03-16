from __future__ import annotations

from typing import Protocol


class DeliveryWriteRepository(Protocol):
    def save_delivery(
        self,
        *,
        encomenda_id: int,
        tipo: str = "entrega",
        endereco: str | None = None,
        data_agendada: str | None = None,
        status: str = "pendente",
    ) -> None: ...
