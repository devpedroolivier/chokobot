from __future__ import annotations

from dataclasses import dataclass

from app.application.events import OrderCreatedEvent
from app.application.service_registry import get_event_bus
from app.domain.repositories.order_write_repository import OrderWriteRepository


@dataclass(frozen=True)
class PersistCafeteriaOrder:
    repository: OrderWriteRepository

    def execute(self, *, phone: str, itens: list[str], nome_cliente: str) -> None:
        self.repository.save_cafeteria_items(
            phone=phone,
            itens=itens,
            nome_cliente=nome_cliente,
        )
        get_event_bus().publish(
            OrderCreatedEvent(
                order_id=-1,
                phone=phone,
                nome_cliente=nome_cliente,
                categoria="cafeteria",
                source="cafeteria_order",
            )
        )
