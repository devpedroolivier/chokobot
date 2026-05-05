"""Service registry — lazy DI container for gateways, repos and buses.

The previous implementation cached every dependency via @lru_cache, which
worked for single-tenant Chokodelícia but cannot hold separate instances
for each tenant once Phase B (multi-tenant) lands.

The new ServiceRegistry keeps a per-tenant dictionary for every
dependency. Today every caller passes ``tenant_id=None`` (single-tenant
default), so the dictionary holds a single entry — behavior is identical
to the old @lru_cache. When tenant-aware factories arrive, the same
registry already supports it without further refactor.

Public module-level functions (``get_catalog_gateway`` etc.) preserve the
single-argument signature for now. Tests that previously called
``get_X.cache_clear()`` should now use ``reset_registry()``.
"""
from __future__ import annotations

from typing import Callable, Generic, TypeVar

from app.application.command_bus import LocalCommandBus
from app.application.commands import GenerateAiReplyCommand, HandleInboundMessageCommand
from app.application.event_bus import LocalEventBus
from app.application.events import (
    AiReplyGeneratedEvent,
    AiReplySkippedEvent,
    HumanHandoffEscalatedEvent,
    MessageReceivedEvent,
    OrderClosedByBotEvent,
    OrderCreatedEvent,
)
from app.application.ports.attention_gateway import AttentionGateway
from app.application.ports.catalog_gateway import CatalogGateway
from app.application.ports.conversation_gateway import ConversationGateway
from app.application.ports.delivery_gateway import DeliveryGateway
from app.application.ports.messaging_gateway import MessagingGateway
from app.application.ports.order_gateway import OrderGateway
from app.domain.repositories.customer_process_repository import CustomerProcessRepository
from app.domain.repositories.customer_repository import CustomerRepository
from app.domain.repositories.order_repository import OrderRepository
from app.infrastructure.state.conversation_state_store import (
    ConversationStateStore,
    build_conversation_state_store,
)
from app.settings import get_settings


T = TypeVar("T")
TenantId = str | None


class _PerTenantCache(Generic[T]):
    """Maps tenant_id → instance, building lazily through a factory."""

    __slots__ = ("_factory", "_cache")

    def __init__(self, factory: Callable[[TenantId], T]) -> None:
        self._factory = factory
        self._cache: dict[TenantId, T] = {}

    def get(self, tenant_id: TenantId) -> T:
        if tenant_id not in self._cache:
            self._cache[tenant_id] = self._factory(tenant_id)
        return self._cache[tenant_id]

    def clear(self) -> None:
        self._cache.clear()


class ServiceRegistry:
    """Holds per-tenant gateway/repository/bus singletons.

    Each accessor accepts an optional ``tenant_id`` (default: ``None`` for
    single-tenant Chokodelícia). When Phase B lands, the same call
    returns the right instance for the resolved tenant.
    """

    def __init__(self) -> None:
        self._catalog_gateways = _PerTenantCache(self._build_catalog_gateway)
        self._order_gateways = _PerTenantCache(self._build_order_gateway)
        self._delivery_gateways = _PerTenantCache(self._build_delivery_gateway)
        self._messaging_gateways = _PerTenantCache(self._build_messaging_gateway)
        self._attention_gateways = _PerTenantCache(self._build_attention_gateway)
        self._conversation_gateways = _PerTenantCache(self._build_conversation_gateway)
        self._customer_repositories = _PerTenantCache(self._build_customer_repository)
        self._customer_process_repositories = _PerTenantCache(
            self._build_customer_process_repository
        )
        self._order_repositories = _PerTenantCache(self._build_order_repository)
        self._state_stores = _PerTenantCache(self._build_state_store)
        # Buses are global today (one CommandBus / EventBus shared across
        # tenants). They stay tenant-agnostic for now; tenant routing
        # happens inside command/event handlers.
        self._command_bus: LocalCommandBus | None = None
        self._event_bus: LocalEventBus | None = None

    # ------------------------------------------------------------------
    #  Public accessors (per-tenant)
    # ------------------------------------------------------------------

    def get_catalog_gateway(self, tenant_id: TenantId = None) -> CatalogGateway:
        return self._catalog_gateways.get(tenant_id)

    def get_order_gateway(self, tenant_id: TenantId = None) -> OrderGateway:
        return self._order_gateways.get(tenant_id)

    def get_delivery_gateway(self, tenant_id: TenantId = None) -> DeliveryGateway:
        return self._delivery_gateways.get(tenant_id)

    def get_messaging_gateway(self, tenant_id: TenantId = None) -> MessagingGateway:
        return self._messaging_gateways.get(tenant_id)

    def get_attention_gateway(self, tenant_id: TenantId = None) -> AttentionGateway:
        return self._attention_gateways.get(tenant_id)

    def get_conversation_gateway(self, tenant_id: TenantId = None) -> ConversationGateway:
        return self._conversation_gateways.get(tenant_id)

    def get_customer_repository(self, tenant_id: TenantId = None) -> CustomerRepository:
        return self._customer_repositories.get(tenant_id)

    def get_customer_process_repository(
        self, tenant_id: TenantId = None
    ) -> CustomerProcessRepository:
        return self._customer_process_repositories.get(tenant_id)

    def get_order_repository(self, tenant_id: TenantId = None) -> OrderRepository:
        return self._order_repositories.get(tenant_id)

    def get_state_store(self, tenant_id: TenantId = None) -> ConversationStateStore:
        return self._state_stores.get(tenant_id)

    def get_command_bus(self) -> LocalCommandBus:
        if self._command_bus is None:
            self._command_bus = self._build_command_bus()
        return self._command_bus

    def get_event_bus(self) -> LocalEventBus:
        if self._event_bus is None:
            self._event_bus = self._build_event_bus()
        return self._event_bus

    # ------------------------------------------------------------------
    #  Cache management (tests call reset_registry())
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self._catalog_gateways.clear()
        self._order_gateways.clear()
        self._delivery_gateways.clear()
        self._messaging_gateways.clear()
        self._attention_gateways.clear()
        self._conversation_gateways.clear()
        self._customer_repositories.clear()
        self._customer_process_repositories.clear()
        self._order_repositories.clear()
        self._state_stores.clear()
        self._command_bus = None
        self._event_bus = None

    # ------------------------------------------------------------------
    #  Factories (tenant_id is accepted for forward compatibility but
    #  unused while the system is single-tenant).
    # ------------------------------------------------------------------

    def _build_catalog_gateway(self, tenant_id: TenantId) -> CatalogGateway:
        from app.infrastructure.gateways.local_catalog_gateway import LocalCatalogGateway

        return LocalCatalogGateway()

    def _build_order_gateway(self, tenant_id: TenantId) -> OrderGateway:
        from app.infrastructure.gateways.local_order_gateway import LocalOrderGateway

        return LocalOrderGateway()

    def _build_delivery_gateway(self, tenant_id: TenantId) -> DeliveryGateway:
        from app.infrastructure.gateways.local_delivery_gateway import LocalDeliveryGateway

        return LocalDeliveryGateway()

    def _build_messaging_gateway(self, tenant_id: TenantId) -> MessagingGateway:
        if get_settings().messaging_provider == "evolution":
            from app.infrastructure.gateways.evolution_messaging_gateway import (
                EvolutionMessagingGateway,
            )

            return EvolutionMessagingGateway()

        from app.infrastructure.gateways.zapi_messaging_gateway import ZapiMessagingGateway

        return ZapiMessagingGateway()

    def _build_attention_gateway(self, tenant_id: TenantId) -> AttentionGateway:
        from app.infrastructure.gateways.local_attention_gateway import LocalAttentionGateway

        return LocalAttentionGateway()

    def _build_conversation_gateway(self, tenant_id: TenantId) -> ConversationGateway:
        conversation_service_url = get_settings().conversation_service_url
        if conversation_service_url:
            from app.infrastructure.gateways.http_conversation_gateway import (
                HttpConversationGateway,
            )

            return HttpConversationGateway(conversation_service_url)

        from app.infrastructure.gateways.local_conversation_gateway import (
            LocalConversationGateway,
        )

        return LocalConversationGateway()

    def _build_customer_repository(self, tenant_id: TenantId) -> CustomerRepository:
        from app.db.database import is_postgres

        if is_postgres():
            from app.infrastructure.repositories.postgres_customer_repository import (
                PostgresCustomerRepository,
            )

            return PostgresCustomerRepository()

        from app.infrastructure.repositories.sqlite_customer_repository import (
            SQLiteCustomerRepository,
        )

        return SQLiteCustomerRepository()

    def _build_customer_process_repository(
        self, tenant_id: TenantId
    ) -> CustomerProcessRepository:
        from app.db.database import is_postgres

        if is_postgres():
            from app.infrastructure.repositories.postgres_customer_process_repository import (
                PostgresCustomerProcessRepository,
            )

            return PostgresCustomerProcessRepository()

        from app.infrastructure.repositories.sqlite_customer_process_repository import (
            SQLiteCustomerProcessRepository,
        )

        return SQLiteCustomerProcessRepository()

    def _build_order_repository(self, tenant_id: TenantId) -> OrderRepository:
        from app.db.database import is_postgres

        if is_postgres():
            from app.infrastructure.repositories.postgres_order_repository import (
                PostgresOrderRepository,
            )

            return PostgresOrderRepository()

        from app.infrastructure.repositories.sqlite_order_repository import (
            SQLiteOrderRepository,
        )

        return SQLiteOrderRepository()

    def _build_state_store(self, tenant_id: TenantId) -> ConversationStateStore:
        return build_conversation_state_store(tenant_id=tenant_id)

    def _build_command_bus(self) -> LocalCommandBus:
        from app.application.handlers.generate_ai_reply import generate_ai_reply
        from app.application.handlers.handle_inbound_message import handle_inbound_message

        bus = LocalCommandBus()
        bus.register(HandleInboundMessageCommand, handle_inbound_message)
        bus.register(GenerateAiReplyCommand, generate_ai_reply)
        return bus

    def _build_event_bus(self) -> LocalEventBus:
        from app.application.handlers.persist_domain_event import persist_domain_event

        bus = LocalEventBus()
        for event_type in (
            MessageReceivedEvent,
            AiReplyGeneratedEvent,
            AiReplySkippedEvent,
            OrderCreatedEvent,
            OrderClosedByBotEvent,
            HumanHandoffEscalatedEvent,
        ):
            bus.subscribe(event_type, persist_domain_event)
        return bus


# ----------------------------------------------------------------------
#  Module-level singleton + backward-compat accessors
# ----------------------------------------------------------------------

_registry: ServiceRegistry | None = None


def get_registry() -> ServiceRegistry:
    global _registry
    if _registry is None:
        _registry = ServiceRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the registry — used by tests that previously called
    ``get_X.cache_clear()``."""
    global _registry
    if _registry is not None:
        _registry.reset()
    _registry = None


def get_catalog_gateway(tenant_id: TenantId = None) -> CatalogGateway:
    return get_registry().get_catalog_gateway(tenant_id)


def get_order_gateway(tenant_id: TenantId = None) -> OrderGateway:
    return get_registry().get_order_gateway(tenant_id)


def get_delivery_gateway(tenant_id: TenantId = None) -> DeliveryGateway:
    return get_registry().get_delivery_gateway(tenant_id)


def get_messaging_gateway(tenant_id: TenantId = None) -> MessagingGateway:
    return get_registry().get_messaging_gateway(tenant_id)


def get_attention_gateway(tenant_id: TenantId = None) -> AttentionGateway:
    return get_registry().get_attention_gateway(tenant_id)


def get_conversation_gateway(tenant_id: TenantId = None) -> ConversationGateway:
    return get_registry().get_conversation_gateway(tenant_id)


def get_customer_repository(tenant_id: TenantId = None) -> CustomerRepository:
    return get_registry().get_customer_repository(tenant_id)


def get_customer_process_repository(tenant_id: TenantId = None) -> CustomerProcessRepository:
    return get_registry().get_customer_process_repository(tenant_id)


def get_order_repository(tenant_id: TenantId = None) -> OrderRepository:
    return get_registry().get_order_repository(tenant_id)


def get_state_store(tenant_id: TenantId = None) -> ConversationStateStore:
    return get_registry().get_state_store(tenant_id)


def get_command_bus() -> LocalCommandBus:
    return get_registry().get_command_bus()


def get_event_bus() -> LocalEventBus:
    return get_registry().get_event_bus()
