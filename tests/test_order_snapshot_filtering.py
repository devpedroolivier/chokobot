import os
import unittest

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.api.routes.pedidos import build_orders_snapshot_payload


class OrderSnapshotFilteringTests(unittest.TestCase):
    def test_build_orders_snapshot_payload_hides_test_and_zero_value_orders(self):
        payload = build_orders_snapshot_payload(
            [
                (
                    1,
                    "Ana",
                    "5511999999999",
                    "tradicional",
                    "Chocolate",
                    "Brigadeiro",
                    "Ninho",
                    "",
                    "B3",
                    "nao",
                    "retirada",
                    "2026-03-18 09:00:00",
                    "pendente",
                    "Bolo de chocolate",
                    "2026-03-20",
                    120.0,
                ),
                (
                    2,
                    "Cliente Teste",
                    "5511888888888",
                    "tradicional",
                    "Chocolate",
                    "Brigadeiro",
                    "Ninho",
                    "",
                    "B3",
                    "nao",
                    "retirada",
                    "2026-03-18 09:00:00",
                    "pendente",
                    "Pedido teste",
                    "2026-03-20",
                    120.0,
                ),
                (
                    3,
                    "Bia",
                    "5511777777777",
                    "tradicional",
                    "Chocolate",
                    "Brigadeiro",
                    "Ninho",
                    "",
                    "B3",
                    "nao",
                    "retirada",
                    "2026-03-18 09:00:00",
                    "pendente",
                    "Bolo branco",
                    "2026-03-20",
                    0.0,
                ),
            ]
        )

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["id"], 1)


if __name__ == "__main__":
    unittest.main()
