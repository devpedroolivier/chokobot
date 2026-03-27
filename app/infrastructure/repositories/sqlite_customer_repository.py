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
    def list_customers(self) -> list[CustomerRecord]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clientes ORDER BY criado_em DESC")
            return [_map_customer(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_customer(self, customer_id: int) -> CustomerRecord | None:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clientes WHERE id = ?", (customer_id,))
            return _map_customer(cursor.fetchone())
        finally:
            conn.close()

    def get_customer_by_phone(self, telefone: str) -> CustomerRecord | None:
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

    def get_customers_by_phones(self, phones: Iterable[str]) -> dict[str, CustomerRecord]:
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

    def create_customer(self, nome: str, telefone: str) -> None:
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

    def upsert_customer(self, nome: str, telefone: str) -> int:
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

    def update_customer(self, customer_id: int, nome: str, telefone: str) -> None:
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

    def delete_customer(self, customer_id: int) -> None:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM clientes WHERE id = ?", (customer_id,))
            conn.commit()
        finally:
            conn.close()
