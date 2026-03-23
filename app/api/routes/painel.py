from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.api.dependencies import (
    get_customer_process_repository,
    get_customer_repository,
    get_order_repository,
)
from app.application.use_cases.panel_dashboard import (
    build_dashboard_context as _build_dashboard_context_impl,
    build_process_cards as _build_process_cards_impl,
    build_process_sections as _build_process_sections_impl,
    build_sync_overview as _build_sync_overview_impl,
    build_whatsapp_cards as _build_whatsapp_cards_impl,
    normalize_status as _normalize_status_impl,
    parse_order_date as _parse_order_date_impl,
)
from app.domain.repositories.customer_process_repository import CustomerProcessRepository
from app.application.use_cases.update_order_delivery_status import UpdateOrderDeliveryStatus
from app.domain.repositories.customer_repository import CustomerRepository
from app.domain.repositories.order_repository import OrderPanelItem, OrderRepository
from app.infrastructure.web.templates import templates
from app.infrastructure.web.admin_frontend import resolve_admin_frontend_url
from app.security import require_panel_auth

router = APIRouter(dependencies=[Depends(require_panel_auth)])


def _parse_order_date(raw_value: str | None) -> date | None:
    return _parse_order_date_impl(raw_value)


def _normalize_status(raw_status: str | None, raw_type: str | None) -> str:
    return _normalize_status_impl(raw_status, raw_type)


def build_whatsapp_cards(customer_repository: CustomerRepository, *, now: datetime | None = None) -> list[dict]:
    return _build_whatsapp_cards_impl(customer_repository, now=now)


def build_process_cards(
    process_repository: CustomerProcessRepository,
    customer_repository: CustomerRepository,
    *,
    now: datetime | None = None,
) -> list[dict]:
    return _build_process_cards_impl(process_repository, customer_repository, now=now)


def build_dashboard_context(items: list[OrderPanelItem], *, today: date | None = None) -> dict:
    return _build_dashboard_context_impl(items, today=today)


def build_sync_overview(
    process_cards: list[dict],
    whatsapp_cards: list[dict],
    *,
    confirmed_orders_count: int,
) -> dict:
    return _build_sync_overview_impl(
        process_cards,
        whatsapp_cards,
        confirmed_orders_count=confirmed_orders_count,
    )


def build_process_sections(process_cards: list[dict]) -> list[dict]:
    return _build_process_sections_impl(process_cards)


def _sanitize_snapshot_payload(value):
    if isinstance(value, dict):
        return {
            key: _sanitize_snapshot_payload(item)
            for key, item in value.items()
            if not key.endswith("_sort")
        }
    if isinstance(value, list):
        return [_sanitize_snapshot_payload(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def build_panel_snapshot_payload(
    *,
    dashboard: dict,
    process_sections: list[dict],
    whatsapp_cards: list[dict],
    sync_overview: dict,
) -> dict:
    return _sanitize_snapshot_payload(
        {
            "dashboard": dashboard,
            "process_sections": process_sections,
            "whatsapp_cards": whatsapp_cards,
            "sync_overview": sync_overview,
        }
    )


@router.get("/painel", response_class=HTMLResponse)
def painel_principal(
    request: Request,
    repository: OrderRepository = Depends(get_order_repository),
    customer_repository: CustomerRepository = Depends(get_customer_repository),
    process_repository: CustomerProcessRepository = Depends(get_customer_process_repository),
):
    frontend_url = resolve_admin_frontend_url("/")
    if frontend_url:
        return RedirectResponse(url=frontend_url, status_code=302)

    dashboard = build_dashboard_context(repository.list_for_main_panel())
    process_cards = build_process_cards(process_repository, customer_repository)
    process_sections = build_process_sections(process_cards)
    whatsapp_cards = build_whatsapp_cards(customer_repository)
    sync_overview = build_sync_overview(
        process_cards,
        whatsapp_cards,
        confirmed_orders_count=len(dashboard["operational_orders"]),
    )
    return templates.TemplateResponse(
        "painel_principal.html",
        {
            "request": request,
            "dashboard": dashboard,
            "process_cards": process_cards,
            "process_sections": process_sections,
            "whatsapp_cards": whatsapp_cards,
            "sync_overview": sync_overview,
        },
    )


@router.get("/painel/api/snapshot")
def painel_snapshot(
    repository: OrderRepository = Depends(get_order_repository),
    customer_repository: CustomerRepository = Depends(get_customer_repository),
    process_repository: CustomerProcessRepository = Depends(get_customer_process_repository),
):
    dashboard = build_dashboard_context(repository.list_for_main_panel())
    process_cards = build_process_cards(process_repository, customer_repository)
    process_sections = build_process_sections(process_cards)
    whatsapp_cards = build_whatsapp_cards(customer_repository)
    sync_overview = build_sync_overview(
        process_cards,
        whatsapp_cards,
        confirmed_orders_count=len(dashboard["operational_orders"]),
    )
    payload = build_panel_snapshot_payload(
        dashboard=dashboard,
        process_sections=process_sections,
        whatsapp_cards=whatsapp_cards,
        sync_overview=sync_overview,
    )
    return JSONResponse(payload)


@router.post("/painel/encomendas/{id}/status")
def atualizar_status(
    id: int,
    status: str = Form(...),
    repository: OrderRepository = Depends(get_order_repository),
):
    payload = UpdateOrderDeliveryStatus(repository=repository).execute(order_id=id, status=status)
    return JSONResponse(payload)
