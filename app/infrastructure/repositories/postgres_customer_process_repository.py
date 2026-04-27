"""Postgres implementation of CustomerProcessRepository (Phase B.8a).

Mirrors the SQLite repo behaviour and adds explicit ``tenant_id``
filtering in every read. Writes carry the resolved tenant pk via the
INSERT column list. The (phone, process_type) UNIQUE constraint is
inherited from migration 0001 — see TODO note for the multi-tenant
hardening once a second tenant goes live.
"""
from __future__ import annotations

import json

from app.db.database import open_postgres_connection, resolve_tenant_pk
from app.domain.repositories.customer_process_repository import (
    CustomerProcessRecord,
    CustomerProcessRepository,
)


_SELECT_COLUMNS = (
    "id, phone, customer_id, process_type, stage, status, source, "
    "draft_payload, order_id, created_at, updated_at"
)


def _map_process(row) -> CustomerProcessRecord | None:
    if row is None:
        return None
    payload = row[7] or "{}"
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8")
    try:
        draft_payload = json.loads(payload) if isinstance(payload, str) else (payload or {})
    except json.JSONDecodeError:
        draft_payload = {}
    return CustomerProcessRecord(
        id=row[0],
        phone=row[1],
        customer_id=row[2],
        process_type=row[3],
        stage=row[4],
        status=row[5],
        source=row[6],
        draft_payload=draft_payload,
        order_id=row[8],
        created_at=row[9].isoformat() if hasattr(row[9], "isoformat") else row[9],
        updated_at=row[10].isoformat() if hasattr(row[10], "isoformat") else row[10],
    )


class PostgresCustomerProcessRepository(CustomerProcessRepository):
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
        tenant_id: str | None = None,
    ) -> int:
        tenant_pk = resolve_tenant_pk(tenant_id)
        payload_json = json.dumps(draft_payload or {}, ensure_ascii=False, sort_keys=True)

        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                # Defensive FK validation — mirror SQLite repo behaviour:
                # silently null out customer_id / order_id if they don't
                # exist in this tenant's scope.
                resolved_customer_id = customer_id
                if resolved_customer_id is not None:
                    cur.execute(
                        "SELECT 1 FROM clientes WHERE id = %s AND tenant_id = %s",
                        (resolved_customer_id, tenant_pk),
                    )
                    if cur.fetchone() is None:
                        resolved_customer_id = None

                resolved_order_id = order_id
                if resolved_order_id is not None:
                    cur.execute(
                        "SELECT 1 FROM encomendas WHERE id = %s AND tenant_id = %s",
                        (resolved_order_id, tenant_pk),
                    )
                    if cur.fetchone() is None:
                        resolved_order_id = None

                cur.execute(
                    """
                    INSERT INTO customer_processes (
                        phone, customer_id, process_type, stage, status,
                        source, draft_payload, order_id, updated_at, tenant_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s
                    )
                    ON CONFLICT (phone, process_type) DO UPDATE SET
                        customer_id = EXCLUDED.customer_id,
                        stage = EXCLUDED.stage,
                        status = EXCLUDED.status,
                        source = COALESCE(EXCLUDED.source, customer_processes.source),
                        draft_payload = EXCLUDED.draft_payload,
                        order_id = COALESCE(EXCLUDED.order_id, customer_processes.order_id),
                        updated_at = NOW()
                    RETURNING id
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
                        tenant_pk,
                    ),
                )
                row = cur.fetchone()
        return int(row[0]) if row else 0

    def get_process(
        self,
        phone: str,
        process_type: str,
        *,
        tenant_id: str | None = None,
    ) -> CustomerProcessRecord | None:
        tenant_pk = resolve_tenant_pk(tenant_id)
        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_SELECT_COLUMNS} FROM customer_processes "
                    "WHERE phone = %s AND process_type = %s AND tenant_id = %s",
                    (phone, process_type, tenant_pk),
                )
                return _map_process(cur.fetchone())

    def list_active_processes(
        self, *, tenant_id: str | None = None
    ) -> list[CustomerProcessRecord]:
        tenant_pk = resolve_tenant_pk(tenant_id)
        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_SELECT_COLUMNS} FROM customer_processes "
                    "WHERE status = 'active' AND tenant_id = %s "
                    "ORDER BY updated_at DESC, id DESC",
                    (tenant_pk,),
                )
                return [_map_process(row) for row in cur.fetchall()]
