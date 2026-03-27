import os
import tempfile
import unittest

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.domain.repositories.customer_repository import CustomerRecord
from app.infrastructure.repositories.sqlite_customer_repository import SQLiteCustomerRepository
from app.models import criar_tabelas


class CustomerRepositoryTests(unittest.TestCase):
    def test_sqlite_customer_repository_returns_typed_records(self):
        repository = SQLiteCustomerRepository()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "chokobot.db")
            previous_db_path = os.environ.get("DB_PATH")
            os.environ["DB_PATH"] = db_path
            try:
                criar_tabelas()
                repository.create_customer("Ana", "5511999999999")
                repository.create_customer("Bia", "5511888888888")

                customers = repository.list_customers()
                customer = repository.get_customer_by_phone("5511999999999")
                customers_by_phone = repository.get_customers_by_phones(
                    ["5511999999999", "5511888888888", "5511777777777"]
                )
            finally:
                if previous_db_path is None:
                    os.environ.pop("DB_PATH", None)
                else:
                    os.environ["DB_PATH"] = previous_db_path

        self.assertEqual(len(customers), 2)
        self.assertTrue(all(isinstance(item, CustomerRecord) for item in customers))
        self.assertIsNotNone(customer)
        self.assertIsInstance(customer, CustomerRecord)
        self.assertEqual(customer.nome, "Ana")
        self.assertEqual(customer.telefone, "5511999999999")
        self.assertEqual(set(customers_by_phone), {"5511999999999", "5511888888888"})
        self.assertEqual(customers_by_phone["5511888888888"].nome, "Bia")

    def test_get_customer_by_phone_returns_none_when_clientes_table_is_missing(self):
        repository = SQLiteCustomerRepository()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "chokobot.db")
            previous_db_path = os.environ.get("DB_PATH")
            os.environ["DB_PATH"] = db_path
            try:
                customer = repository.get_customer_by_phone("5511999999999")
            finally:
                if previous_db_path is None:
                    os.environ.pop("DB_PATH", None)
                else:
                    os.environ["DB_PATH"] = previous_db_path

        self.assertIsNone(customer)


if __name__ == "__main__":
    unittest.main()
