from __future__ import annotations

from app.application.use_cases.persist_delivery import PersistDelivery
from app.infrastructure.repositories.sqlite_delivery_write_repository import SQLiteDeliveryWriteRepository


class LocalDeliveryGateway:
    def __init__(self):
        self._persist_delivery = PersistDelivery(repository=SQLiteDeliveryWriteRepository())

    def create_delivery(
        self,
        *,
        encomenda_id: int,
        tipo: str = "entrega",
        endereco: str | None = None,
        data_agendada: str | None = None,
        status: str = "pendente",
    ) -> None:
        self._persist_delivery.execute(
            encomenda_id=encomenda_id,
            tipo=tipo,
            endereco=endereco,
            data_agendada=data_agendada,
            status=status,
        )
