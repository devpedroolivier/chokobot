from __future__ import annotations

from app.application.use_cases.persist_delivery import PersistDelivery


def _build_delivery_write_repository():
    from app.db.database import is_postgres

    if is_postgres():
        from app.infrastructure.repositories.postgres_delivery_write_repository import (
            PostgresDeliveryWriteRepository,
        )

        return PostgresDeliveryWriteRepository()

    from app.infrastructure.repositories.sqlite_delivery_write_repository import (
        SQLiteDeliveryWriteRepository,
    )

    return SQLiteDeliveryWriteRepository()


class LocalDeliveryGateway:
    def __init__(self):
        self._persist_delivery = PersistDelivery(repository=_build_delivery_write_repository())

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
