import os
import tempfile
import unittest

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.application.use_cases.panel_orders import (
    build_create_order_payload,
    build_orders_export_text,
    export_orders_txt,
)


class PanelOrdersTests(unittest.TestCase):
    def test_build_create_order_payload_normalizes_panel_form_fields(self):
        payload = build_create_order_payload(
            nome="Ana",
            telefone="5511999999999",
            produto="Bolo",
            categoria="",
            linha="redondo",
            tamanho="M",
            massa="Baunilha",
            recheio="Brigadeiro",
            mousse="Ninho",
            adicional="",
            fruta_ou_nozes="Morango",
            valor_total="129,90",
            data_entrega="2026-03-25",
            horario="",
            horario_retirada="15:00",
        )

        self.assertEqual(payload["categoria"], "redondo")
        self.assertEqual(payload["adicional"], "Morango")
        self.assertEqual(payload["horario"], "15:00")
        self.assertEqual(payload["data_entrega"], "2026-03-25")

    def test_build_orders_export_text_formats_rows_for_txt_download(self):
        content = build_orders_export_text(
            [
                ("Ana", "Bolo de chocolate", "2026-03-25", "129,90", "pendente"),
                ("Bia", None, None, None, "entregue"),
            ]
        )

        self.assertEqual(
            content,
            "Ana | Bolo de chocolate | 2026-03-25 | R$129,90 | pendente\n"
            "Bia | - | - | R$0,00 | entregue\n",
        )

    def test_export_orders_txt_writes_generated_content(self):
        class _Repository:
            def export_rows(self):
                return [("Ana", "Bolo", "2026-03-25", "129,90", "pendente")]

        with tempfile.TemporaryDirectory() as tmpdir:
            output = export_orders_txt(_Repository(), os.path.join(tmpdir, "export", "encomendas.txt"))
            self.assertTrue(output.exists())
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "Ana | Bolo | 2026-03-25 | R$129,90 | pendente\n",
            )


if __name__ == "__main__":
    unittest.main()
