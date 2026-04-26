from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Iterable

from app.db.database import get_connection
from app.domain.repositories.customer_repository import CustomerRecord, CustomerRepository


def _map_customer(row) -> CustomerRecord | None:
    if row is None:
        return None
    return CustomerRecord(
        id=row["id"],
        nome=row["nome"],
        telefone=row["telefone"],
        criado_em=row["criado_em"],
    )


class SQLiteCustomerRepository(CustomerRepository):
    """SQLite implementation of CustomerRepository.

    The ``tenant_id`` keyword is part of every method signature for
    forward compatibility with Phase B's Postgres implementation. While
    the SQLite schema does not yet have a ``tenant_id`` column, the
    parameter is silently ignored — the cutover migration adds the
    column and the Postgres implementation enforces filtering.
    """

    def list_customers(self, *, tenant_id: str | None = None) -> list[CustomerRecord]:
        del tenant_id
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clientes ORDER BY criado_em DESC")
            return [_map_customer(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_customer(
        self, customer_id: int, *, tenant_id: str | None = None
    ) -> CustomerRecord | None:
        del tenant_id
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clientes WHERE id = ?", (customer_id,))
            return _map_customer(cursor.fetchone())
        finally:
            conn.close()

    def get_customer_by_phone(
        self, telefone: str, *, tenant_id: str | None = None
    ) -> CustomerRecord | None:
        del tenant_id
        conn = get_connection()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT * FROM clientes WHERE telefone = ?", (telefone,))
            except sqlite3.OperationalError as exc:
                if "no such table" in str(exc).lower():
                    return None
                raise
            return _map_customer(cursor.fetchone())
        finally:
            conn.close()

    def get_customers_by_phones(
        self, phones: Iterable[str], *, tenant_id: str | None = None
    ) -> dict[str, CustomerRecord]:
        del tenant_id
        unique_phones = tuple(dict.fromkeys(phone for phone in phones if phone))
        if not unique_phones:
            return {}

        placeholders = ",".join("?" for _ in unique_phones)
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM clientes WHERE telefone IN ({placeholders})",
                unique_phones,
            )
            return {
                customer.telefone: customer
                for customer in (_map_customer(row) for row in cursor.fetchall())
                if customer is not None
            }
        finally:
            conn.close()

    def create_customer(
        self, nome: str, telefone: str, *, tenant_id: str | None = None
    ) -> None:
        del tenant_id
        conn = get_connection()
        try:
            cursor = conn.cursor()
            agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO clientes (nome, telefone, criado_em) VALUES (?, ?, ?)",
                (nome, telefone, agora),
            )
            conn.commit()
        finally:
            conn.close()

    def upsert_customer(
        self, nome: str, telefone: str, *, tenant_id: str | None = None
    ) -> int:
        del tenant_id
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM clientes WHERE telefone = ?", (telefone,))
            row = cursor.fetchone()
            if row:
                customer_id = row["id"] if hasattr(row, "keys") else row[0]
                cursor.execute("UPDATE clientes SET nome = ? WHERE id = ?", (nome, customer_id))
            else:
                agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO clientes (nome, telefone, criado_em) VALUES (?, ?, ?)",
                    (nome, telefone, agora),
                )
                customer_id = cursor.lastrowid
            conn.commit()
            return int(customer_id)
        finally:
            conn.close()

    def update_customer(
        self,
        customer_id: int,
        nome: str,
        telefone: str,
        *,
        tenant_id: str | None = None,
    ) -> None:
        del tenant_id
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE clientes SET nome = ?, telefone = ? WHERE id = ?",
                (nome, telefone, customer_id),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_customer(
        self, customer_id: int, *, tenant_id: str | None = None
    ) -> None:
        del tenant_id
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM clientes WHERE id = ?", (customer_id,))
            conn.commit()
        finally:
            conn.close()
