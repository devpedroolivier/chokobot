from __future__ import annotations

import json

from app.db.database import get_connection
from app.domain.repositories.customer_process_repository import CustomerProcessRecord, CustomerProcessRepository


def _map_process(row) -> CustomerProcessRecord | None:
    if row is None:
        return None
    payload = row["draft_payload"] or "{}"
    try:
        draft_payload = json.loads(payload)
    except json.JSONDecodeError:
        draft_payload = {}
    return CustomerProcessRecord(
        id=row["id"],
        phone=row["phone"],
        customer_id=row["customer_id"],
        process_type=row["process_type"],
        stage=row["stage"],
        status=row["status"],
        source=row["source"],
        draft_payload=draft_payload,
        order_id=row["order_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SQLiteCustomerProcessRepository(CustomerProcessRepository):
    def upsert_process(
        self,
        *,
        phone: str,
        process_type: str,
        stage: str,
        draft_payload: dict,
        customer_id: int | None = None,
        status: str = "active",
        source: str | None = None,
        order_id: int | None = None,
    ) -> int:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            resolved_customer_id = customer_id
            if resolved_customer_id is not None:
                cursor.execute("SELECT 1 FROM clientes WHERE id = ?", (resolved_customer_id,))
                if cursor.fetchone() is None:
                    resolved_customer_id = None

            resolved_order_id = order_id
            if resolved_order_id is not None:
                cursor.execute("SELECT 1 FROM encomendas WHERE id = ?", (resolved_order_id,))
                if cursor.fetchone() is None:
                    resolved_order_id = None

            payload_json = json.dumps(draft_payload or {}, ensure_ascii=False, sort_keys=True)
            cursor.execute(
                """
                INSERT INTO customer_processes (
                    phone,
                    customer_id,
                    process_type,
                    stage,
                    status,
                    source,
                    draft_payload,
                    order_id,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(phone, process_type) DO UPDATE SET
                    customer_id = excluded.customer_id,
                    stage = excluded.stage,
                    status = excluded.status,
                    source = COALESCE(excluded.source, customer_processes.source),
                    draft_payload = excluded.draft_payload,
                    order_id = COALESCE(excluded.order_id, customer_processes.order_id),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    phone,
                    resolved_customer_id,
                    process_type,
                    stage,
                    status,
                    source,
                    payload_json,
                    resolved_order_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        row = self.get_process(phone, process_type)
        return 0 if row is None else row.id

    def get_process(self, phone: str, process_type: str) -> CustomerProcessRecord | None:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT *
                FROM customer_processes
                WHERE phone = ? AND process_type = ?
                """,
                (phone, process_type),
            )
            return _map_process(cursor.fetchone())
        finally:
            conn.close()

    def list_active_processes(self) -> list[CustomerProcessRecord]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT *
                FROM customer_processes
                WHERE status = 'active'
                ORDER BY updated_at DESC, id DESC
                """
            )
            return [_map_process(row) for row in cursor.fetchall()]
        finally:
            conn.close()
