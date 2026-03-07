from __future__ import annotations

from dataclasses import dataclass

from app.application.events import OrderCreatedEvent
from app.application.service_registry import get_event_bus
from app.domain.repositories.order_write_repository import OrderWriteRepository


@dataclass(frozen=True)
class PersistOrderPayload:
    repository: OrderWriteRepository

    def execute(
        self,
        *,
        phone: str,
        dados: dict,
        nome_cliente: str,
        cliente_id: int | None = None,
    ) -> int:
        order_id = self.repository.save_order_payload(
            phone=phone,
            dados=dados,
            nome_cliente=nome_cliente,
            cliente_id=cliente_id,
        )
        if order_id > 0:
            get_event_bus().publish(
                OrderCreatedEvent(
                    order_id=order_id,
                    phone=phone,
                    nome_cliente=nome_cliente,
                    categoria=str(dados.get("categoria") or dados.get("linha") or "tradicional"),
                    source="order_payload",
                )
            )
        return order_id
