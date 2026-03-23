import os
import unittest
from unittest.mock import sentinel

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.api import dependencies


class ApiDependenciesTests(unittest.TestCase):
    def test_order_repository_dependency_delegates_to_service_registry(self):
        original = dependencies.get_order_repository_from_registry
        dependencies.get_order_repository_from_registry = lambda: sentinel.order_repository
        try:
            repository = dependencies.get_order_repository()
        finally:
            dependencies.get_order_repository_from_registry = original

        self.assertIs(repository, sentinel.order_repository)

    def test_customer_repository_dependency_delegates_to_service_registry(self):
        original = dependencies.get_customer_repository_from_registry
        dependencies.get_customer_repository_from_registry = lambda: sentinel.customer_repository
        try:
            repository = dependencies.get_customer_repository()
        finally:
            dependencies.get_customer_repository_from_registry = original

        self.assertIs(repository, sentinel.customer_repository)


if __name__ == "__main__":
    unittest.main()
