import os
import unittest
from datetime import datetime

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.api.routes.painel import build_panel_snapshot_payload


class PanelSnapshotPayloadTests(unittest.TestCase):
    def test_build_panel_snapshot_payload_removes_sort_fields_and_keeps_contract(self):
        payload = build_panel_snapshot_payload(
            dashboard={
                "generated_at": "23/03/2026 18:00",
                "kanban_columns": [
                    {
                        "title": "Pendentes",
                        "items": [
                            {
                                "id": 1,
                                "cliente_nome": "Ana",
                                "status_slug": "pendente",
                                "data_iso": "2026-03-23",
                            }
                        ],
                    }
                ],
            },
            process_sections=[
                {
                    "title": "Prontos para fechamento",
                    "cards": [
                        {
                            "cliente_nome": "Bia",
                            "updated_sort": datetime(2026, 3, 23, 18, 0, 0),
                            "stage_slug": "aguardando_confirmacao",
                        }
                    ],
                }
            ],
            whatsapp_cards=[
                {
                    "cliente_nome": "Clara",
                    "last_seen_sort": datetime(2026, 3, 23, 17, 55, 0),
                    "owner_label": "Ação do bot",
                }
            ],
            sync_overview={"metrics": [], "alerts": []},
        )

        self.assertIn("dashboard", payload)
        self.assertIn("process_sections", payload)
        self.assertIn("whatsapp_cards", payload)
        self.assertIn("sync_overview", payload)
        self.assertNotIn("updated_sort", payload["process_sections"][0]["cards"][0])
        self.assertNotIn("last_seen_sort", payload["whatsapp_cards"][0])
        self.assertEqual(payload["process_sections"][0]["cards"][0]["cliente_nome"], "Bia")


if __name__ == "__main__":
    unittest.main()
