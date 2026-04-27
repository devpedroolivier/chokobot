"""Postgres implementation of CustomerRepository (Phase B.8a).

Mirrors ``SQLiteCustomerRepository`` but enforces tenant isolation.
The application passes ``tenant_id`` as the slug string (resolved at
the webhook); this repo translates the slug into the ``tenants.id``
BIGINT via the in-process cache in :mod:`app.db.database`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from app.db.database import open_postgres_connection, resolve_tenant_pk
from app.domain.repositories.customer_repository import CustomerRecord, CustomerRepository


def _map_customer(row) -> CustomerRecord | None:
    if row is None:
        return None
    return CustomerRecord(
        id=row[0],
        nome=row[1],
        telefone=row[2],
        criado_em=row[3].isoformat() if hasattr(row[3], "isoformat") else row[3],
    )


_SELECT_COLUMNS = "id, nome, telefone, criado_em"


class PostgresCustomerRepository(CustomerRepository):
    def list_customers(self, *, tenant_id: str | None = None) -> list[CustomerRecord]:
        tenant_pk = resolve_tenant_pk(tenant_id)
        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_SELECT_COLUMNS} FROM clientes "
                    "WHERE tenant_id = %s ORDER BY criado_em DESC",
                    (tenant_pk,),
                )
                return [_map_customer(row) for row in cur.fetchall()]

    def get_customer(
        self, customer_id: int, *, tenant_id: str | None = None
    ) -> CustomerRecord | None:
        tenant_pk = resolve_tenant_pk(tenant_id)
        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_SELECT_COLUMNS} FROM clientes "
                    "WHERE id = %s AND tenant_id = %s",
                    (customer_id, tenant_pk),
                )
                return _map_customer(cur.fetchone())

    def get_customer_by_phone(
        self, telefone: str, *, tenant_id: str | None = None
    ) -> CustomerRecord | None:
        tenant_pk = resolve_tenant_pk(tenant_id)
        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_SELECT_COLUMNS} FROM clientes "
                    "WHERE telefone = %s AND tenant_id = %s",
                    (telefone, tenant_pk),
                )
                return _map_customer(cur.fetchone())

    def get_customers_by_phones(
        self, phones: Iterable[str], *, tenant_id: str | None = None
    ) -> dict[str, CustomerRecord]:
        unique_phones = tuple(dict.fromkeys(phone for phone in phones if phone))
        if not unique_phones:
            return {}
        tenant_pk = resolve_tenant_pk(tenant_id)
        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_SELECT_COLUMNS} FROM clientes "
                    "WHERE tenant_id = %s AND telefone = ANY(%s)",
                    (tenant_pk, list(unique_phones)),
                )
                customers = [_map_customer(row) for row in cur.fetchall()]
        return {c.telefone: c for c in customers if c is not None}

    def create_customer(
        self, nome: str, telefone: str, *, tenant_id: str | None = None
    ) -> None:
        tenant_pk = resolve_tenant_pk(tenant_id)
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO clientes (nome, telefone, criado_em, tenant_id) "
                    "VALUES (%s, %s, %s, %s)",
                    (nome, telefone, agora, tenant_pk),
                )

    def upsert_customer(
        self, nome: str, telefone: str, *, tenant_id: str | None = None
    ) -> int:
        """Insert-or-update by (tenant_id, telefone). Returns the customer id.

        Relies on the ``clientes_tenant_telefone_key`` unique constraint
        added in migration 0003.
        """
        tenant_pk = resolve_tenant_pk(tenant_id)
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO clientes (nome, telefone, criado_em, tenant_id) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (tenant_id, telefone) "
                    "DO UPDATE SET nome = EXCLUDED.nome "
                    "RETURNING id",
                    (nome, telefone, agora, tenant_pk),
                )
                row = cur.fetchone()
        return int(row[0])

    def update_customer(
        self,
        customer_id: int,
        nome: str,
        telefone: str,
        *,
        tenant_id: str | None = None,
    ) -> None:
        tenant_pk = resolve_tenant_pk(tenant_id)
        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE clientes SET nome = %s, telefone = %s "
                    "WHERE id = %s AND tenant_id = %s",
                    (nome, telefone, customer_id, tenant_pk),
                )

    def delete_customer(
        self, customer_id: int, *, tenant_id: str | None = None
    ) -> None:
        tenant_pk = resolve_tenant_pk(tenant_id)
        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM clientes WHERE id = %s AND tenant_id = %s",
                    (customer_id, tenant_pk),
                )
