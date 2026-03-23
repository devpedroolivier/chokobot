from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CustomerRecord:
    id: int
    nome: str
    telefone: str
    criado_em: str | None


class CustomerRepository(Protocol):
    def list_customers(self) -> list[CustomerRecord]: ...

    def get_customer(self, customer_id: int) -> CustomerRecord | None: ...

    def get_customer_by_phone(self, telefone: str) -> CustomerRecord | None: ...

    def create_customer(self, nome: str, telefone: str) -> None: ...

    def upsert_customer(self, nome: str, telefone: str) -> int: ...

    def update_customer(self, customer_id: int, nome: str, telefone: str) -> None: ...

    def delete_customer(self, customer_id: int) -> None: ...
