from __future__ import annotations

from app.application.use_cases.persist_cafeteria_order import PersistCafeteriaOrder
from app.application.use_cases.persist_order_payload import PersistOrderPayload
from app.infrastructure.repositories.sqlite_order_write_repository import SQLiteOrderWriteRepository


class LocalOrderGateway:
    def __init__(self):
        repository = SQLiteOrderWriteRepository()
        self._persist_order = PersistOrderPayload(repository=repository)
        self._persist_cafeteria = PersistCafeteriaOrder(repository=repository)

    def create_order(
        self,
        *,
        phone: str,
        dados: dict,
        nome_cliente: str,
        cliente_id: int,
    ) -> int:
        return self._persist_order.execute(
            phone=phone,
            dados=dados,
            nome_cliente=nome_cliente,
            cliente_id=cliente_id,
        )

    def save_cafeteria_order(
        self,
        *,
        phone: str,
        itens: list[str],
        nome_cliente: str,
    ) -> None:
        self._persist_cafeteria.execute(
            phone=phone,
            itens=itens,
            nome_cliente=nome_cliente,
        )
