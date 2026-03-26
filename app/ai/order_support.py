from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Protocol, Iterable, Optional

from app.observability import normalize_tracking_phone
from app.settings import get_settings


@dataclass(frozen=True)
class OrderRecord:
    phone: str
    order_id: str
    status: str
    pix_confirmed: bool
    cancelable: bool
    invoice_email: str


class OrderSupportAdapter(Protocol):
    def fetch_orders(self, phone: str) -> Iterable[OrderRecord]:
        ...


class MockOrderSupportAdapter:
    def __init__(self, records: Iterable[OrderRecord] | None = None):
        self._records = list(records or [])

    def fetch_orders(self, phone: str) -> Iterable[OrderRecord]:
        normalized = phone.strip()
        for record in self._records:
            if record.phone == normalized:
                yield record


class OrderSupportService:
    def __init__(self, adapter: OrderSupportAdapter):
        self._adapter = adapter

    def _find_latest(self, phone: str) -> Optional[OrderRecord]:
        records = list(self._adapter.fetch_orders(phone))
        if not records:
            return None
        return sorted(records, key=lambda rec: rec.order_id, reverse=True)[0]

    def handle(self, topic: str, phone: str, **kwargs) -> tuple[bool, str, str | None]:
        order = self._find_latest(phone)
        if order is None:
            return False, "Não encontrei nenhum pedido recente. Posso chamar um atendente humano para ajudar?", "order_not_found"

        if topic == "status":
            return (
                True,
                f"O pedido {order.order_id} está com status *{order.status}*. O painel pode confirmar se já foi preparado.",
                None,
            )
        if topic == "pix":
            if order.pix_confirmed:
                return True, "Recebemos e registramos o PIX obrigatório para esse pedido.", None
            return False, "Ainda não consta PIX confirmado para esse pedido. Pode reenviar o comprovante?", "pix_missing"
        if topic == "cancel":
            if order.cancelable:
                return True, "Esse pedido ainda pode ser cancelado pelo painel operacional. Informe o motivo para finalizar o cancelamento.", None
            return False, "Esse pedido já está em preparo ou já foi entregue; vou conectar você a um atendente humano.", "cancel_blocked"
        if topic == "invoice":
            return (
                True,
                f"A nota fiscal do pedido {order.order_id} será enviada para {order.invoice_email} em até um dia útil.",
                None,
            )

        return False, "Desculpe, não tenho os dados necessários para essa solicitação.", "unsupported_topic"


class SQLiteOrderSupportAdapter:
    def __init__(self, *, db_path: str | None = None, invoice_email: str | None = None):
        settings = get_settings()
        self._db_path = db_path or settings.order_support_db_path
        self._invoice_email = invoice_email or settings.order_support_invoice_email

    def fetch_orders(self, phone: str) -> Iterable[OrderRecord]:
        normalized = normalize_tracking_phone(phone)
        if not normalized:
            return
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT
                        e.id AS order_id,
                        COALESCE(d.status, 'pendente') AS status
                    FROM clientes c
                    JOIN encomendas e ON e.cliente_id = c.id
                    LEFT JOIN entregas d ON d.encomenda_id = e.id
                    WHERE c.telefone = ?
                    ORDER BY e.id DESC
                    LIMIT 1
                    """,
                    (normalized,),
                )
                row = cursor.fetchone()
        except sqlite3.Error:
            return

        if not row:
            return

        status = (row["status"] or "pendente").lower()
        pix_confirmed = status not in {"pendente", "agendada"}
        cancelable = status in {"pendente", "agendada"}
        yield OrderRecord(
            phone=normalized,
            order_id=str(row["order_id"]),
            status=status,
            pix_confirmed=pix_confirmed,
            cancelable=cancelable,
            invoice_email=self._invoice_email,
        )


DEFAULT_ORDER_SUPPORT = OrderSupportService(SQLiteOrderSupportAdapter())
