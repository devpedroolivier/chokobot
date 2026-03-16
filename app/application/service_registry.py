from __future__ import annotations

from functools import lru_cache

from app.application.command_bus import LocalCommandBus
from app.application.commands import GenerateAiReplyCommand, HandleInboundMessageCommand
from app.application.event_bus import LocalEventBus
from app.application.events import AiReplyGeneratedEvent, MessageReceivedEvent, OrderCreatedEvent
from app.application.ports.attention_gateway import AttentionGateway
from app.application.ports.catalog_gateway import CatalogGateway
from app.application.ports.conversation_gateway import ConversationGateway
from app.application.ports.delivery_gateway import DeliveryGateway
from app.application.ports.messaging_gateway import MessagingGateway
from app.application.ports.order_gateway import OrderGateway
from app.domain.repositories.customer_repository import CustomerRepository
from app.settings import get_settings


@lru_cache
def get_catalog_gateway() -> CatalogGateway:
    from app.infrastructure.gateways.local_catalog_gateway import LocalCatalogGateway

    return LocalCatalogGateway()


@lru_cache
def get_order_gateway() -> OrderGateway:
    from app.infrastructure.gateways.local_order_gateway import LocalOrderGateway

    return LocalOrderGateway()


@lru_cache
def get_delivery_gateway() -> DeliveryGateway:
    from app.infrastructure.gateways.local_delivery_gateway import LocalDeliveryGateway

    return LocalDeliveryGateway()


@lru_cache
def get_messaging_gateway() -> MessagingGateway:
    from app.infrastructure.gateways.zapi_messaging_gateway import ZapiMessagingGateway

    return ZapiMessagingGateway()


@lru_cache
def get_attention_gateway() -> AttentionGateway:
    from app.infrastructure.gateways.local_attention_gateway import LocalAttentionGateway

    return LocalAttentionGateway()


@lru_cache
def get_customer_repository() -> CustomerRepository:
    from app.infrastructure.repositories.sqlite_customer_repository import SQLiteCustomerRepository

    return SQLiteCustomerRepository()


@lru_cache
def get_command_bus() -> LocalCommandBus:
    from app.application.handlers.generate_ai_reply import generate_ai_reply
    from app.application.handlers.handle_inbound_message import handle_inbound_message

    bus = LocalCommandBus()
    bus.register(HandleInboundMessageCommand, handle_inbound_message)
    bus.register(GenerateAiReplyCommand, generate_ai_reply)
    return bus


@lru_cache
def get_event_bus() -> LocalEventBus:
    from app.application.handlers.persist_domain_event import persist_domain_event

    bus = LocalEventBus()
    for event_type in (MessageReceivedEvent, AiReplyGeneratedEvent, OrderCreatedEvent):
        bus.subscribe(event_type, persist_domain_event)
    return bus


@lru_cache
def get_conversation_gateway() -> ConversationGateway:
    conversation_service_url = get_settings().conversation_service_url
    if conversation_service_url:
        from app.infrastructure.gateways.http_conversation_gateway import HttpConversationGateway

        return HttpConversationGateway(conversation_service_url)

    from app.infrastructure.gateways.local_conversation_gateway import LocalConversationGateway

    return LocalConversationGateway()
