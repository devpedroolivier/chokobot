from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class CustomerProcessRecord:
    id: int
    phone: str
    customer_id: int | None
    process_type: str
    stage: str
    status: str
    source: str | None
    draft_payload: dict[str, Any]
    order_id: int | None
    created_at: str | None
    updated_at: str | None


class CustomerProcessRepository(Protocol):
    def upsert_process(
        self,
        *,
        phone: str,
        process_type: str,
        stage: str,
        draft_payload: dict[str, Any],
        customer_id: int | None = None,
        status: str = "active",
        source: str | None = None,
        order_id: int | None = None,
    ) -> int: ...

    def get_process(self, phone: str, process_type: str) -> CustomerProcessRecord | None: ...

    def list_active_processes(self) -> list[CustomerProcessRecord]: ...
