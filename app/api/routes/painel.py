from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.dependencies import get_order_repository
from app.application.use_cases.update_order_delivery_status import UpdateOrderDeliveryStatus
from app.domain.repositories.order_repository import OrderRepository
from app.infrastructure.web.templates import templates

router = APIRouter()


@router.get("/painel", response_class=HTMLResponse)
def painel_principal(
    request: Request,
    repository: OrderRepository = Depends(get_order_repository),
):
    encomendas = [item.__dict__ for item in repository.list_for_main_panel()]

    return templates.TemplateResponse("painel_principal.html", {
        "request": request,
        "encomendas": encomendas
    })


@router.post("/painel/encomendas/{id}/status")
def atualizar_status(
    id: int,
    status: str = Form(...),
    repository: OrderRepository = Depends(get_order_repository),
):
    payload = UpdateOrderDeliveryStatus(repository=repository).execute(order_id=id, status=status)
    return JSONResponse(payload)
