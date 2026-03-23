from __future__ import annotations

import sqlite3
from datetime import datetime

from app.db.database import get_connection
from app.domain.repositories.delivery_write_repository import DeliveryWriteRepository
from app.observability import log_event


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

        try:
            cur.execute(
                """
                INSERT INTO entregas (encomenda_id, tipo, endereco, data_agendada, status, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    encomenda_id,
                    tipo,
                    endereco,
                    data_agendada,
                    status,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
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
