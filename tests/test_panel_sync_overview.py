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


if __name__ == "__main__":
    unittest.main()
