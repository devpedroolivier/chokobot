from app.domain.repositories.customer_repository import CustomerRepository
from app.domain.repositories.order_repository import OrderRepository
from app.infrastructure.repositories.sqlite_customer_repository import SQLiteCustomerRepository
from app.infrastructure.repositories.sqlite_order_repository import SQLiteOrderRepository


def get_order_repository() -> OrderRepository:
    return SQLiteOrderRepository()


def get_customer_repository() -> CustomerRepository:
    return SQLiteCustomerRepository()
