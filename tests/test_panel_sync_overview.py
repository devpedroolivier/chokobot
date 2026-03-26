import os
import unittest

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.application.use_cases.panel_dashboard import build_sync_overview
from app.observability import clear_metrics, increment_counter


class PanelSyncOverviewTests(unittest.TestCase):
    def setUp(self):
        clear_metrics()

    def test_build_sync_overview_surfaces_ai_drafts_human_handoffs_and_block_alerts(self):
        increment_counter("ai_order_confirmation_blocks_total", tool_name="create_cake_order", agent="CakeOrderAgent")
        process_cards = [
            {
                "origin_slug": "ai",
                "stage_slug": "aguardando_confirmacao",
            },
            {
                "origin_slug": "manual",
                "stage_slug": "coletando_endereco",
            },
        ]
        whatsapp_cards = [
            {
                "is_human_handoff": True,
            },
            {
                "is_human_handoff": False,
            },
        ]

        overview = build_sync_overview(
            process_cards,
            whatsapp_cards,
            confirmed_orders_count=5,
        )

        metrics = {item["label"]: item["value"] for item in overview["metrics"]}
        self.assertEqual(metrics["Rascunhos IA"], "1")
        self.assertEqual(metrics["Prontos para fechar"], "1")
        self.assertEqual(metrics["Pedidos confirmados"], "5")
        self.assertEqual(metrics["Handoff humano"], "1")
        self.assertEqual(len(overview["alerts"]), 3)
        self.assertIn("bloqueadas", overview["alerts"][0]["description"])
        telemetry = overview["telemetry"]
        self.assertIsInstance(telemetry, dict)
        self.assertEqual(telemetry["handoffs_by_reason"], [])
        self.assertEqual(telemetry["post_purchase_fallbacks"], [])
        self.assertEqual(len(telemetry["operational_metrics"]), 3)
        self.assertTrue(all((metric["value"] == "—" for metric in telemetry["operational_metrics"])))

    def test_build_sync_overview_reports_telemetry_percentages(self):
        increment_counter("ai_human_guard_handoffs_total", reason="customer_request", agent="CakeOrderAgent")
        increment_counter("ai_runs_total", stage="started", agent="TriageAgent")
        increment_counter("ai_runs_total", stage="started", agent="TriageAgent")
        increment_counter("ai_post_purchase_fallback_total", outcome="success", topic="status", failure_reason="success")
        increment_counter("ai_post_purchase_fallback_total", outcome="failure", topic="status", failure_reason="order_not_found")

        process_cards = []
        whatsapp_cards = []

        overview = build_sync_overview(
            process_cards,
            whatsapp_cards,
            confirmed_orders_count=0,
        )

        metrics = overview["telemetry"]["operational_metrics"]
        failure_metric = next((metric for metric in metrics if metric["label"].startswith("Taxa de falha")), None)
        resolution_metric = next((metric for metric in metrics if metric["label"].startswith("Taxa de resolução de pós-compra")), None)
        human_metric = next((metric for metric in metrics if metric["label"].startswith("Taxa de resolução sem humano")), None)

        self.assertIsNotNone(failure_metric)
        self.assertEqual(failure_metric["value"], "50%")
        self.assertIsNotNone(resolution_metric)
        self.assertEqual(resolution_metric["value"], "50%")
        self.assertIsNotNone(human_metric)
        self.assertEqual(human_metric["value"], "50%")


if __name__ == "__main__":
    unittest.main()
