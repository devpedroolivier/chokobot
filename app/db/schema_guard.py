from __future__ import annotations

import sqlite3

from app.db.database import get_connection


class SchemaValidationError(RuntimeError):
    pass


_REQUIRED_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "clientes": ("id", "nome", "telefone"),
    "customer_processes": ("id", "phone", "process_type", "stage", "status", "draft_payload"),
    "encomendas": (
        "id",
        "cliente_id",
        "categoria",
        "produto",
        "tamanho",
        "massa",
        "recheio",
        "mousse",
        "adicional",
        "kit_festou",
        "quantidade",
        "data_entrega",
        "horario",
        "valor_total",
        "serve_pessoas",
    ),
    "entregas": ("id", "encomenda_id", "tipo", "endereco", "data_agendada", "status"),
    "pedidos_cafeteria": ("id", "cliente_id", "pedido"),
}


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table});")
    return {str(row[1]) for row in cur.fetchall()}


def validate_runtime_schema() -> None:
    conn = get_connection()
    try:
        for table, required_columns in _REQUIRED_TABLE_COLUMNS.items():
            existing_columns = _existing_columns(conn, table)
            if not existing_columns:
                raise SchemaValidationError(f"Missing table: {table}")

            missing_columns = [column for column in required_columns if column not in existing_columns]
            if missing_columns:
                missing = ", ".join(missing_columns)
                raise SchemaValidationError(f"Table {table} is missing required columns: {missing}")
    finally:
        conn.close()
