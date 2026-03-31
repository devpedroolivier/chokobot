from __future__ import annotations

from dataclasses import dataclass

from app.application.events import OrderCreatedEvent
from app.application.service_registry import get_event_bus
from app.domain.repositories.order_write_repository import OrderWriteRepository


@dataclass(frozen=True)
class PersistOrderBundle:
    repository: OrderWriteRepository

    def execute(
        self,
        *,
        phone: str,
        dados: dict,
        nome_cliente: str,
        cliente_id: int | None = None,
        delivery_data: dict | None = None,
        process_data: dict | None = None,
        sweet_items: list[dict] | None = None,
    ) -> int:
        order_id = self.repository.save_order_bundle(
            phone=phone,
            dados=dados,
            nome_cliente=nome_cliente,
            cliente_id=cliente_id,
            delivery_data=delivery_data,
            process_data=process_data,
            sweet_items=sweet_items,
        )
        if order_id > 0:
            get_event_bus().publish(
                OrderCreatedEvent(
                    order_id=order_id,
                    phone=phone,
                    nome_cliente=nome_cliente,
                    categoria=str(dados.get("categoria") or dados.get("linha") or "tradicional"),
                    source="order_bundle",
                )
            )
        return order_id
