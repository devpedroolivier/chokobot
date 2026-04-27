"""Service-registry routing for Postgres backend (Phase B.8a).

When ``DATABASE_URL`` points at Postgres the registry must hand out
``Postgres*Repository`` impls instead of ``SQLite*Repository``. This
test fixes the routing contract without requiring a running Postgres
— ``psycopg.connect`` is never invoked because the test only checks
the *type* returned by the factory.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.application.service_registry import reset_registry


class PostgresRoutingTests(unittest.TestCase):
    def setUp(self):
        reset_registry()

    def tearDown(self):
        reset_registry()

    def test_sqlite_url_yields_sqlite_repos(self):
        """Default DATABASE_URL is sqlite — registry returns SQLite impls."""
        from app.application.service_registry import (
            get_customer_process_repository,
            get_customer_repository,
            get_order_repository,
        )
        from app.infrastructure.repositories.sqlite_customer_process_repository import (
            SQLiteCustomerProcessRepository,
        )
        from app.infrastructure.repositories.sqlite_customer_repository import (
            SQLiteCustomerRepository,
        )
        from app.infrastructure.repositories.sqlite_order_repository import (
            SQLiteOrderRepository,
        )

        with patch("app.db.database.is_postgres", return_value=False):
            self.assertIsInstance(get_customer_repository(), SQLiteCustomerRepository)
            self.assertIsInstance(
                get_customer_process_repository(), SQLiteCustomerProcessRepository,
            )
            self.assertIsInstance(get_order_repository(), SQLiteOrderRepository)

    def test_postgres_url_yields_postgres_repos(self):
        """When is_postgres() is true, the registry routes to PG impls."""
        from app.application.service_registry import (
            get_customer_process_repository,
            get_customer_repository,
            get_order_repository,
        )
        from app.infrastructure.repositories.postgres_customer_process_repository import (
            PostgresCustomerProcessRepository,
        )
        from app.infrastructure.repositories.postgres_customer_repository import (
            PostgresCustomerRepository,
        )
        from app.infrastructure.repositories.postgres_order_repository import (
            PostgresOrderRepository,
        )

        with patch("app.db.database.is_postgres", return_value=True):
            self.assertIsInstance(get_customer_repository(), PostgresCustomerRepository)
            self.assertIsInstance(
                get_customer_process_repository(), PostgresCustomerProcessRepository,
            )
            self.assertIsInstance(get_order_repository(), PostgresOrderRepository)

    def test_local_order_gateway_picks_postgres_write_repo(self):
        """LocalOrderGateway chooses the right OrderWriteRepository at __init__."""
        from app.infrastructure.repositories.postgres_order_write_repository import (
            PostgresOrderWriteRepository,
        )

        with patch("app.db.database.is_postgres", return_value=True):
            from app.infrastructure.gateways.local_order_gateway import LocalOrderGateway

            gateway = LocalOrderGateway()
            # Reach into the persistence-use-case wired in the constructor.
            self.assertIsInstance(
                gateway._persist_order.repository, PostgresOrderWriteRepository,
            )
            self.assertIsInstance(
                gateway._persist_bundle.repository, PostgresOrderWriteRepository,
            )

    def test_local_delivery_gateway_picks_postgres_write_repo(self):
        from app.infrastructure.repositories.postgres_delivery_write_repository import (
            PostgresDeliveryWriteRepository,
        )

        with patch("app.db.database.is_postgres", return_value=True):
            from app.infrastructure.gateways.local_delivery_gateway import (
                LocalDeliveryGateway,
            )

            gateway = LocalDeliveryGateway()
            self.assertIsInstance(
                gateway._persist_delivery.repository, PostgresDeliveryWriteRepository,
            )


class IsPostgresHelperTests(unittest.TestCase):
    """Lock the URL classification rules used by every routing branch."""

    def test_sqlite_url_is_not_postgres(self):
        from app.db.database import is_postgres

        with patch(
            "app.db.database._normalised_database_url",
            return_value="sqlite:///dados/chokobot.db",
        ):
            self.assertFalse(is_postgres())

    def test_postgresql_psycopg_url_is_postgres(self):
        from app.db.database import is_postgres

        with patch(
            "app.db.database._normalised_database_url",
            return_value="postgresql+psycopg://u:p@h:5432/db",
        ):
            self.assertTrue(is_postgres())

    def test_plain_postgresql_url_is_postgres(self):
        from app.db.database import is_postgres

        with patch(
            "app.db.database._normalised_database_url",
            return_value="postgresql://u:p@h/db",
        ):
            self.assertTrue(is_postgres())

    def test_legacy_postgres_alias_is_postgres(self):
        from app.db.database import is_postgres

        with patch(
            "app.db.database._normalised_database_url",
            return_value="postgres://u:p@h/db",
        ):
            self.assertTrue(is_postgres())


class SchemaGuardSkipsOnPostgresTests(unittest.TestCase):
    """When DATABASE_URL is Postgres, schema_guard trusts Alembic."""

    def test_validate_runtime_schema_no_op_on_pg(self):
        from app.db.schema_guard import validate_runtime_schema

        with patch("app.db.schema_guard.is_postgres", return_value=True):
            # Must not crash even with no SQLite file present.
            validate_runtime_schema()


if __name__ == "__main__":
    unittest.main()
