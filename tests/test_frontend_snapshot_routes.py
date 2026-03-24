import os
import unittest

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.api.routes.clientes import build_customer_details_snapshot_payload, build_customers_snapshot_payload
from app.api.routes.pedidos import build_order_details_snapshot_payload, build_orders_snapshot_payload
from app.domain.repositories.customer_repository import CustomerRecord


class FrontendSnapshotRoutesTests(unittest.TestCase):
    def test_build_customers_snapshot_payload_serializes_records(self):
        payload = build_customers_snapshot_payload(
            [
                CustomerRecord(
                    id=1,
                    nome="Ana",
                    telefone="5511999999999",
                    criado_em="2026-03-23 18:00:00",
                )
            ]
        )

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["nome"], "Ana")
        self.assertEqual(payload["items"][0]["telefone"], "5511999999999")

    def test_build_orders_snapshot_payload_serializes_order_rows(self):
        payload = build_orders_snapshot_payload(
            [
                (
                    10,
                    "Bia",
                    "5511888888888",
                    "tradicional",
                    "Chocolate",
                    "Brigadeiro",
                    "Ninho",
                    "Morango",
                    "B3",
                    "nao",
                    "entrega",
                    "2026-03-23 18:10:00",
                )
            ],
            statuses_by_id={10: "em_preparo"},
        )

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["id"], 10)
        self.assertEqual(payload["items"][0]["cliente_nome"], "Bia")
        self.assertEqual(payload["items"][0]["categoria"], "tradicional")
        self.assertEqual(payload["items"][0]["status"], "em_preparo")

    def test_build_orders_snapshot_payload_uses_embedded_status_when_present(self):
        payload = build_orders_snapshot_payload(
            [
                (
                    10,
                    "Bia",
                    "5511888888888",
                    "tradicional",
                    "Chocolate",
                    "Brigadeiro",
                    "Ninho",
                    "Morango",
                    "B3",
                    "nao",
                    "entrega",
                    "2026-03-23 18:10:00",
                    "agendada",
                )
            ]
        )

        self.assertEqual(payload["items"][0]["status"], "agendada")

    def test_build_customer_details_snapshot_payload_serializes_record(self):
        payload = build_customer_details_snapshot_payload(
            CustomerRecord(
                id=7,
                nome="Clara",
                telefone="5511777777777",
                criado_em="2026-03-23 18:00:00",
            )
        )

        self.assertEqual(payload["item"]["id"], 7)
        self.assertEqual(payload["item"]["nome"], "Clara")
        self.assertEqual(payload["item"]["telefone"], "5511777777777")

    def test_build_order_details_snapshot_payload_serializes_detail_dict(self):
        payload = build_order_details_snapshot_payload(
            {
                "id": 10,
                "cliente_nome": "Bia",
                "categoria": "tradicional",
                "produto": "Bolo de chocolate",
                "tamanho": "B3",
                "status": "pendente",
                "valor_total": 120.0,
            }
        )

        self.assertEqual(payload["item"]["id"], 10)
        self.assertEqual(payload["item"]["cliente_nome"], "Bia")
        self.assertEqual(payload["item"]["produto"], "Bolo de chocolate")
        self.assertEqual(payload["item"]["status"], "pendente")


if __name__ == "__main__":
    unittest.main()
