from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass(frozen=True)
class CustomerRecord:
    id: int
    nome: str
    telefone: str
    criado_em: str | None


# All read/write methods accept ``tenant_id`` as a keyword-only
# argument with default ``None``. The default behaves as
# "single-tenant Chokodelícia" so legacy callers do not break. Phase
# B's tenant-aware callers pass an explicit value resolved from the
# inbound request. The current SQLite implementation accepts and
# ignores the value (no tenant_id column yet); the Postgres
# implementation, introduced at the cutover, filters by tenant_id.

class CustomerRepository(Protocol):
    def list_customers(self, *, tenant_id: str | None = None) -> list[CustomerRecord]: ...

    def get_customer(
        self, customer_id: int, *, tenant_id: str | None = None
    ) -> CustomerRecord | None: ...

    def get_customer_by_phone(
        self, telefone: str, *, tenant_id: str | None = None
    ) -> CustomerRecord | None: ...

    def get_customers_by_phones(
        self, phones: Iterable[str], *, tenant_id: str | None = None
    ) -> dict[str, CustomerRecord]: ...

    def create_customer(
        self, nome: str, telefone: str, *, tenant_id: str | None = None
    ) -> None: ...

    def upsert_customer(
        self, nome: str, telefone: str, *, tenant_id: str | None = None
    ) -> int: ...

    def update_customer(
        self,
        customer_id: int,
        nome: str,
        telefone: str,
        *,
        tenant_id: str | None = None,
    ) -> None: ...

    def delete_customer(
        self, customer_id: int, *, tenant_id: str | None = None
    ) -> None: ...
