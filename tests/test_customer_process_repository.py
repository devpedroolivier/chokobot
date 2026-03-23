import os
import tempfile
import unittest

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.infrastructure.repositories.sqlite_customer_process_repository import SQLiteCustomerProcessRepository
from app.models import criar_tabelas


class CustomerProcessRepositoryTests(unittest.TestCase):
    def test_upsert_and_list_active_processes(self):
        repository = SQLiteCustomerProcessRepository()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "chokobot.db")
            previous_db_path = os.environ.get("DB_PATH")
            os.environ["DB_PATH"] = db_path
            try:
                criar_tabelas()
                process_id = repository.upsert_process(
                    phone="5511999999999",
                    customer_id=7,
                    process_type="delivery_order",
                    stage="coletando_endereco",
                    status="active",
                    source="legacy_delivery",
                    draft_payload={"categoria": "tradicional", "valor_total": 130.0},
                )
                repository.upsert_process(
                    phone="5511999999999",
                    customer_id=7,
                    process_type="delivery_order",
                    stage="pedido_confirmado",
                    status="converted",
                    source="legacy_delivery",
                    draft_payload={"categoria": "tradicional", "valor_total": 130.0},
                    order_id=321,
                )

                row = repository.get_process("5511999999999", "delivery_order")
                active = repository.list_active_processes()
            finally:
                if previous_db_path is None:
                    os.environ.pop("DB_PATH", None)
                else:
                    os.environ["DB_PATH"] = previous_db_path

        self.assertGreater(process_id, 0)
        self.assertIsNotNone(row)
        self.assertEqual(row.status, "converted")
        self.assertEqual(row.order_id, 321)
        self.assertEqual(row.draft_payload["categoria"], "tradicional")
        self.assertEqual(active, [])
