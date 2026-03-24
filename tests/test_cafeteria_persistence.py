import unittest
from unittest.mock import Mock

from app.application.use_cases.persist_cafeteria_order import PersistCafeteriaOrder


class PersistCafeteriaOrderTests(unittest.TestCase):
    def test_execute_only_persists_items_without_fake_order_created_event(self):
        repository = Mock()

        PersistCafeteriaOrder(repository=repository).execute(
            phone="5511888888888",
            itens=["cafe", "bolo"],
            nome_cliente="Cliente Cafe",
        )

        repository.save_cafeteria_items.assert_called_once_with(
            phone="5511888888888",
            itens=["cafe", "bolo"],
            nome_cliente="Cliente Cafe",
        )


if __name__ == "__main__":
    unittest.main()
