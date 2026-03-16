from __future__ import annotations

import sqlite3
from datetime import datetime

from app.db.database import get_connection
from app.domain.repositories.delivery_write_repository import DeliveryWriteRepository
from app.observability import log_event


def _existing_columns(conn: sqlite3.Connection, table: str, candidates: list[str]) -> list[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table});")
    existing = {r[1] for r in cur.fetchall()}
    return [c for c in candidates if c in existing]


class SQLiteDeliveryWriteRepository(DeliveryWriteRepository):
    def save_delivery(
        self,
        *,
        encomenda_id: int,
        tipo: str = "entrega",
        endereco: str | None = None,
        data_agendada: str | None = None,
        status: str = "pendente",
    ) -> None:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        candidate_cols = ["encomenda_id", "tipo", "endereco", "data_agendada", "status", "criado_em"]
        cols = _existing_columns(conn, "entregas", candidate_cols)
        values_map = {
            "encomenda_id": encomenda_id,
            "tipo": tipo,
            "endereco": endereco,
            "data_agendada": data_agendada,
            "status": status,
            "criado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        placeholders = ", ".join("?" for _ in cols)
        sql = f"INSERT INTO entregas ({', '.join(cols)}) VALUES ({placeholders})"

        try:
            cur.execute(sql, [values_map.get(c) for c in cols])
            conn.commit()
            log_event(
                "delivery_saved",
                encomenda_id=encomenda_id,
                tipo=tipo,
                status=status,
            )
        except Exception as exc:
            conn.rollback()
            log_event(
                "delivery_save_failed",
                encomenda_id=encomenda_id,
                tipo=tipo,
                status=status,
                error_type=type(exc).__name__,
            )
            raise
        finally:
            conn.close()
