from __future__ import annotations

from dataclasses import dataclass

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
