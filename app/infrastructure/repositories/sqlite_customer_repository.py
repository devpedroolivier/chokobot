from __future__ import annotations

from datetime import datetime

from app.db.database import get_connection
from app.domain.repositories.customer_repository import CustomerRepository


class SQLiteCustomerRepository(CustomerRepository):
    def list_customers(self) -> list:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clientes ORDER BY criado_em DESC")
            return cursor.fetchall()
        finally:
            conn.close()

    def get_customer(self, customer_id: int):
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clientes WHERE id = ?", (customer_id,))
            return cursor.fetchone()
        finally:
            conn.close()

    def get_customer_by_phone(self, telefone: str):
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clientes WHERE telefone = ?", (telefone,))
            return cursor.fetchone()
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
