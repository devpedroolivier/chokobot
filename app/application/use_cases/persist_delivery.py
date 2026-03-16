from __future__ import annotations

from dataclasses import dataclass

from app.domain.repositories.delivery_write_repository import DeliveryWriteRepository


@dataclass(frozen=True)
class PersistDelivery:
    repository: DeliveryWriteRepository

    def execute(
        self,
        *,
        encomenda_id: int,
        tipo: str = "entrega",
        endereco: str | None = None,
        data_agendada: str | None = None,
        status: str = "pendente",
    ) -> None:
        self.repository.save_delivery(
            encomenda_id=encomenda_id,
            tipo=tipo,
            endereco=endereco,
            data_agendada=data_agendada,
            status=status,
        )
