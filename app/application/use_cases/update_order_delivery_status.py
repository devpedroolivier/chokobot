from __future__ import annotations

from dataclasses import dataclass

from app.domain.repositories.order_repository import OrderRepository


@dataclass(frozen=True)
class UpdateOrderDeliveryStatus:
    repository: OrderRepository

    def execute(self, order_id: int, status: str) -> dict:
        self.repository.upsert_delivery_status(order_id, status)
        return {"ok": True, "id": order_id, "status": status}
