"""Postgres implementation of DeliveryWriteRepository (Phase B.8a)."""
from __future__ import annotations

from datetime import datetime

from app.db.database import open_postgres_connection, resolve_tenant_pk
from app.domain.repositories.delivery_write_repository import DeliveryWriteRepository
from app.observability import log_event


class PostgresDeliveryWriteRepository(DeliveryWriteRepository):
    def save_delivery(
        self,
        *,
        encomenda_id: int,
        tipo: str = "entrega",
        endereco: str | None = None,
        data_agendada: str | None = None,
        status: str = "pendente",
        tenant_id: str | None = None,
    ) -> None:
        tenant_pk = resolve_tenant_pk(tenant_id)
        try:
            with open_postgres_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO entregas (
                            encomenda_id, tipo, endereco, data_agendada,
                            status, atualizado_em, tenant_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            encomenda_id,
                            tipo,
                            endereco,
                            data_agendada,
                            status,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            tenant_pk,
                        ),
                    )
            log_event(
                "delivery_saved",
                encomenda_id=encomenda_id,
                tipo=tipo,
                status=status,
            )
        except Exception as exc:
            log_event(
                "delivery_save_failed",
                encomenda_id=encomenda_id,
                tipo=tipo,
                status=status,
                error_type=type(exc).__name__,
            )
            raise
