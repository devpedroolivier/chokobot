from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, Request
from pydantic import BaseModel
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.api.dependencies import (
    get_customer_process_repository,
    get_customer_repository,
    get_order_repository,
)
from app.application.use_cases.manage_human_handoff import (
    activate_human_handoff,
    build_reactivation_message,
    deactivate_human_handoff,
)
from app.application.use_cases.panel_dashboard import (
    build_dashboard_context as _build_dashboard_context_impl,
    build_process_cards as _build_process_cards_impl,
    build_process_sections as _build_process_sections_impl,
    build_sync_overview as _build_sync_overview_impl,
    build_today_summary,
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
from app.services.estados import append_conversation_message, estados_atendimento
from app.services.store_schedule import build_store_pulse
from app.settings import get_settings
from app.utils.mensagens import responder_usuario_com_contexto

router = APIRouter(dependencies=[Depends(require_panel_auth)])


class ManualConversationReplyRequest(BaseModel):
    message: str
    disable_ai: bool = True
    notify_handoff: bool = False


class ConversationAutomationRequest(BaseModel):
    enabled: bool
    notify_customer: bool = True


def _resolve_customer_name(customer_repository: CustomerRepository, phone: str) -> str:
    customer = customer_repository.get_customer_by_phone(phone)
    if customer is None:
        return "Cliente"
    return customer.nome or "Cliente"


def _parse_order_date(raw_value: str | None) -> date | None:
    return _parse_order_date_impl(raw_value)


def _normalize_status(raw_status: str | None, raw_type: str | None) -> str:
    return _normalize_status_impl(raw_status, raw_type)


def build_whatsapp_cards(
    process_repository: CustomerProcessRepository,
    customer_repository: CustomerRepository,
    *,
    now: datetime | None = None,
) -> list[dict]:
    return _build_whatsapp_cards_impl(process_repository, customer_repository, now=now)


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
    store_pulse: dict | None = None,
    today_summary: dict | None = None,
) -> dict:
    return _sanitize_snapshot_payload(
        {
            "dashboard": dashboard,
            "process_sections": process_sections,
            "whatsapp_cards": whatsapp_cards,
            "sync_overview": sync_overview,
            "store_pulse": store_pulse if store_pulse is not None else build_store_pulse(),
            "today_summary": today_summary if today_summary is not None else build_today_summary(dashboard),
            "attendants": list(get_settings().panel_attendants),
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
    whatsapp_cards = build_whatsapp_cards(process_repository, customer_repository)
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
    whatsapp_cards = build_whatsapp_cards(process_repository, customer_repository)
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


@router.post("/painel/api/conversas/{phone}/reply")
async def responder_conversa_manual(
    phone: str,
    body: ManualConversationReplyRequest,
    customer_repository: CustomerRepository = Depends(get_customer_repository),
    process_repository: CustomerProcessRepository = Depends(get_customer_process_repository),
):
    message = body.message.strip()
    if not message:
        return JSONResponse({"status": "error", "detail": "message_required"}, status_code=400)

    customer_name = _resolve_customer_name(customer_repository, phone)
    handoff_active = phone in estados_atendimento
    if body.disable_ai:
        handoff_notice = activate_human_handoff(
            phone,
            nome=customer_name,
            motivo="assumido_pelo_painel",
            process_repository=process_repository,
        )
        if body.notify_handoff and not handoff_active:
            await responder_usuario_com_contexto(phone, handoff_notice, role="bot", actor_label="Bot")
        append_conversation_message(
            phone,
            role="contexto",
            actor_label="Painel",
            content="IA pausada no painel. Retorno automatico apos inatividade do cliente ou reativacao manual.",
            seen_at=datetime.now(),
        )

    sent = await responder_usuario_com_contexto(phone, message, role="humano", actor_label="Atendente")
    if not sent:
        return JSONResponse({"status": "error", "detail": "message_send_failed"}, status_code=502)

    return JSONResponse(
        {
            "status": "ok",
            "phone": phone,
            "automation_mode": "manual" if body.disable_ai or phone in estados_atendimento else "ai",
            "auto_resume_hint": "A IA volta automaticamente apos inatividade ou quando o cliente pedir retorno ao bot.",
        }
    )


@router.post("/painel/api/conversas/{phone}/automation")
async def atualizar_automacao_conversa(
    phone: str,
    body: ConversationAutomationRequest,
    customer_repository: CustomerRepository = Depends(get_customer_repository),
    process_repository: CustomerProcessRepository = Depends(get_customer_process_repository),
):
    customer_name = _resolve_customer_name(customer_repository, phone)
    now = datetime.now()

    if body.enabled:
        deactivate_human_handoff(phone, process_repository=process_repository)
        append_conversation_message(
            phone,
            role="contexto",
            actor_label="Painel",
            content="IA reativada pelo painel.",
            seen_at=now,
        )
        if body.notify_customer:
            await responder_usuario_com_contexto(phone, build_reactivation_message(), role="bot", actor_label="Bot")
        return JSONResponse(
            {
                "status": "ok",
                "phone": phone,
                "automation_mode": "ai",
                "auto_resume_hint": "A IA esta ativa e responde normalmente por aqui.",
            }
        )

    already_manual = phone in estados_atendimento
    handoff_notice = activate_human_handoff(
        phone,
        nome=customer_name,
        motivo="assumido_pelo_painel",
        process_repository=process_repository,
    )
    append_conversation_message(
        phone,
        role="contexto",
        actor_label="Painel",
        content="IA pausada no painel. Retorno automatico apos inatividade do cliente ou reativacao manual.",
        seen_at=now,
    )
    if body.notify_customer and not already_manual:
        await responder_usuario_com_contexto(phone, handoff_notice, role="bot", actor_label="Bot")
    return JSONResponse(
        {
            "status": "ok",
            "phone": phone,
            "automation_mode": "manual",
            "auto_resume_hint": "A IA volta automaticamente apos inatividade ou quando o cliente pedir retorno ao bot.",
        }
    )


@router.get("/painel/api/clientes/{phone}/encomendas")
def listar_encomendas_cliente(
    phone: str,
    repository: OrderRepository = Depends(get_order_repository),
    limit: int = 10,
):
    orders = repository.list_by_phone(phone, limit=limit)
    return JSONResponse({"items": orders, "total": len(orders)})


@router.post("/painel/encomendas/{id}/status")
def atualizar_status(
    id: int,
    status: str = Form(...),
    repository: OrderRepository = Depends(get_order_repository),
):
    payload = UpdateOrderDeliveryStatus(repository=repository).execute(order_id=id, status=status)
    return JSONResponse(payload)
