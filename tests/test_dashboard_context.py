import os
import unittest
from datetime import date

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.api.routes.painel import _normalize_status, _parse_order_date, build_dashboard_context
from app.domain.repositories.order_repository import OrderPanelItem


class DashboardContextTests(unittest.TestCase):
    def test_parse_order_date_accepts_iso_and_br_formats(self):
        self.assertEqual(_parse_order_date("2026-03-19"), date(2026, 3, 19))
        self.assertEqual(_parse_order_date("19/03/2026"), date(2026, 3, 19))
        self.assertIsNone(_parse_order_date("19-03-26"))

    def test_normalize_status_respects_pickup_labels(self):
        self.assertEqual(_normalize_status("Retirar na loja", "retirada"), "retirada")
        self.assertEqual(_normalize_status("entregue", "entrega"), "entregue")
        self.assertEqual(_normalize_status("agendada", "entrega"), "agendada")

    def test_build_dashboard_context_groups_orders_for_operations(self):
        items = [
            OrderPanelItem(
                id=1,
                cliente_nome="Ana",
                produto="Bolo de chocolate",
                categoria="tradicional",
                data_entrega="2026-03-18",
                horario="10:00",
                valor_total=120.0,
                status="pendente",
                tipo="entrega",
                criado_em="2026-03-18 09:00:00",
            ),
            OrderPanelItem(
                id=2,
                cliente_nome="Bia",
                produto="Torta de limão",
                categoria="torta",
                data_entrega="19/03/2026",
                horario="15:00",
                valor_total=150.0,
                status="em preparo",
                tipo="entrega",
                criado_em="2026-03-18 14:00:00",
            ),
            OrderPanelItem(
                id=3,
                cliente_nome="Caio",
                produto="Cesta box",
                categoria="cesta_box",
                data_entrega="2026-03-22",
                horario="09:00",
                valor_total=180.0,
                status="Retirar na loja",
                tipo="retirada",
                criado_em="2026-03-10 08:30:00",
            ),
            OrderPanelItem(
                id=4,
                cliente_nome="Dani",
                produto="Bolo branco",
                categoria="tradicional",
                data_entrega="2026-03-19",
                horario="11:00",
                valor_total=200.0,
                status="entregue",
                tipo="entrega",
                criado_em="2026-03-17 12:00:00",
            ),
            OrderPanelItem(
                id=5,
                cliente_nome="Pedro Suporte Trufinha",
                produto="Pedido teste",
                categoria="tradicional",
                data_entrega="2025-12-01",
                horario="",
                valor_total=50.0,
                status="pendente",
                tipo="entrega",
                criado_em="2025-11-30 09:00:00",
            ),
        ]

        dashboard = build_dashboard_context(items, today=date(2026, 3, 19))

        metrics = {item["label"]: item["value"] for item in dashboard["metrics"]}
        quality = {item["label"]: item["value"] for item in dashboard["quality_metrics"]}
        priorities = {item["title"]: item["items"] for item in dashboard["priority_sections"]}
        kanban = {item["title"]: item["items"] for item in dashboard["kanban_columns"]}

        self.assertEqual(metrics["Em operação"], "3")
        self.assertEqual(metrics["Hoje"], "1")
        self.assertEqual(metrics["Atrasados"], "1")
        self.assertIn("Receita em operação", metrics)
        self.assertEqual(quality["Sem data"], "0")
        self.assertEqual(len(priorities["Atrasados"]), 1)
        self.assertEqual(len(priorities["Hoje"]), 1)
        self.assertEqual(len(priorities["Próximos 7 dias"]), 1)
        self.assertEqual(len(kanban["Pendentes"]), 1)
        self.assertEqual(len(kanban["Em preparo"]), 1)
        self.assertEqual(len(kanban["Retirada / Agendados"]), 1)
        self.assertEqual(len(kanban["Concluídos"]), 1)
        self.assertEqual(dashboard["orders"][0]["id"], 1)
        self.assertFalse(any(item["id"] == 5 for item in dashboard["orders"]))


if __name__ == "__main__":
    unittest.main()
