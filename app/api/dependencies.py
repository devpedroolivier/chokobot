from app.domain.repositories.customer_process_repository import CustomerProcessRepository
from app.domain.repositories.customer_repository import CustomerRepository
from app.domain.repositories.order_repository import OrderRepository
from app.application.service_registry import (
    get_customer_process_repository as get_customer_process_repository_from_registry,
    get_customer_repository as get_customer_repository_from_registry,
    get_order_repository as get_order_repository_from_registry,
)


def get_order_repository() -> OrderRepository:
    return get_order_repository_from_registry()


def get_customer_repository() -> CustomerRepository:
    return get_customer_repository_from_registry()


def get_customer_process_repository() -> CustomerProcessRepository:
    return get_customer_process_repository_from_registry()
