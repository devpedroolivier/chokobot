import os
import unittest

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.application.use_cases.panel_dashboard import build_process_sections


class PanelProcessSectionsTests(unittest.TestCase):
    def test_build_process_sections_splits_ready_to_close_from_follow_up(self):
        sections = build_process_sections(
            [
                {"process_id": 1, "stage_slug": "aguardando_confirmacao", "cliente_nome": "Ana"},
                {"process_id": 2, "stage_slug": "pagamento_pendente", "cliente_nome": "Bia"},
                {"process_id": 3, "stage_slug": "coletando_endereco", "cliente_nome": "Caio"},
            ]
        )

        self.assertEqual(sections[0]["title"], "Prontos para fechamento")
        self.assertEqual(sections[0]["count"], 2)
        self.assertEqual([card["process_id"] for card in sections[0]["cards"]], [1, 2])
        self.assertEqual(sections[1]["title"], "Em coleta e acompanhamento")
        self.assertEqual(sections[1]["count"], 1)
        self.assertEqual(sections[1]["cards"][0]["process_id"], 3)


if __name__ == "__main__":
    unittest.main()
