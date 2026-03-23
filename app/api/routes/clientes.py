from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.api.dependencies import get_customer_repository
from app.domain.repositories.customer_repository import CustomerRecord, CustomerRepository
from app.infrastructure.web.admin_frontend import resolve_admin_frontend_url
from app.infrastructure.web.templates import templates
from app.security import require_panel_auth

router = APIRouter(dependencies=[Depends(require_panel_auth)])


class CustomerPayload(BaseModel):
    nome: str
    telefone: str


def build_customers_snapshot_payload(customers: list) -> dict:
    return {
        "items": [
            {
                "id": customer.id,
                "nome": customer.nome,
                "telefone": customer.telefone,
                "criado_em": customer.criado_em,
            }
            for customer in customers
        ],
        "count": len(customers),
    }


def build_customer_details_snapshot_payload(customer: CustomerRecord | None) -> dict:
    if customer is None:
        return {"item": None}
    return {
        "item": {
            "id": customer.id,
            "nome": customer.nome,
            "telefone": customer.telefone,
            "criado_em": customer.criado_em,
        }
    }


@router.get("/painel/clientes", response_class=HTMLResponse)
def listar_clientes(
    request: Request,
    repository: CustomerRepository = Depends(get_customer_repository),
):
    frontend_url = resolve_admin_frontend_url("/clientes")
    if frontend_url:
        return RedirectResponse(url=frontend_url, status_code=302)

    clientes = repository.list_customers()
    return templates.TemplateResponse("clientes.html", {"request": request, "clientes": clientes})


@router.get("/painel/api/clientes")
def listar_clientes_snapshot(
    repository: CustomerRepository = Depends(get_customer_repository),
):
    payload = build_customers_snapshot_payload(repository.list_customers())
    return JSONResponse(payload)


@router.get("/painel/api/clientes/{cliente_id}")
def detalhes_cliente_snapshot(
    cliente_id: int,
    repository: CustomerRepository = Depends(get_customer_repository),
):
    payload = build_customer_details_snapshot_payload(repository.get_customer(cliente_id))
    status_code = 404 if payload["item"] is None else 200
    return JSONResponse(payload, status_code=status_code)


@router.get("/painel/clientes/novo", response_class=HTMLResponse)
def novo_cliente(request: Request):
    frontend_url = resolve_admin_frontend_url("/clientes/novo")
    if frontend_url:
        return RedirectResponse(url=frontend_url, status_code=302)
    return templates.TemplateResponse("cliente_form.html", {"request": request, "cliente": None})


@router.get("/painel/clientes/{cliente_id}/editar", response_class=HTMLResponse)
def editar_cliente(
    request: Request,
    cliente_id: int,
    repository: CustomerRepository = Depends(get_customer_repository),
):
    frontend_url = resolve_admin_frontend_url(f"/clientes/{cliente_id}")
    if frontend_url:
        return RedirectResponse(url=frontend_url, status_code=302)

    cliente = repository.get_customer(cliente_id)
    if cliente:
        return templates.TemplateResponse("cliente_form.html", {"request": request, "cliente": cliente})
    return RedirectResponse(url="/painel/clientes", status_code=302)


@router.post("/painel/api/clientes")
def criar_cliente_snapshot(
    payload: CustomerPayload,
    repository: CustomerRepository = Depends(get_customer_repository),
):
    nome = payload.nome.strip()
    telefone = payload.telefone.strip()
    if not nome or not telefone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_customer_payload")

    repository.create_customer(nome, telefone)
    customer = repository.get_customer_by_phone(telefone)
    return JSONResponse(
        {"ok": True, "item": build_customer_details_snapshot_payload(customer)["item"]},
        status_code=201,
    )


@router.put("/painel/api/clientes/{cliente_id}")
def atualizar_cliente_snapshot(
    cliente_id: int,
    payload: CustomerPayload,
    repository: CustomerRepository = Depends(get_customer_repository),
):
    if repository.get_customer(cliente_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer_not_found")

    nome = payload.nome.strip()
    telefone = payload.telefone.strip()
    if not nome or not telefone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_customer_payload")

    repository.update_customer(cliente_id, nome, telefone)
    return JSONResponse(
        {"ok": True, "item": build_customer_details_snapshot_payload(repository.get_customer(cliente_id))["item"]}
    )


@router.delete("/painel/api/clientes/{cliente_id}")
def excluir_cliente_snapshot(
    cliente_id: int,
    repository: CustomerRepository = Depends(get_customer_repository),
):
    if repository.get_customer(cliente_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer_not_found")
    repository.delete_customer(cliente_id)
    return JSONResponse({"ok": True, "id": cliente_id})


@router.post("/painel/clientes/{cliente_id}/editar")
def atualizar_cliente(
    cliente_id: int,
    nome: str = Form(...),
    telefone: str = Form(...),
    repository: CustomerRepository = Depends(get_customer_repository),
):
    repository.update_customer(cliente_id, nome, telefone)
    return RedirectResponse(url="/painel/clientes", status_code=302)


@router.post("/painel/clientes", response_class=HTMLResponse)
def salvar_novo_cliente(
    nome: str = Form(...),
    telefone: str = Form(...),
    repository: CustomerRepository = Depends(get_customer_repository),
):
    repository.create_customer(nome, telefone)
    return RedirectResponse(url="/painel/clientes", status_code=302)


@router.post("/painel/clientes/{cliente_id}/excluir")
def excluir_cliente(
    cliente_id: int,
    repository: CustomerRepository = Depends(get_customer_repository),
):
    repository.delete_customer(cliente_id)
    return RedirectResponse(url="/painel/clientes", status_code=302)
