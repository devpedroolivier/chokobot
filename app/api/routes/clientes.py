from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api.dependencies import get_customer_repository
from app.domain.repositories.customer_repository import CustomerRepository
from app.infrastructure.web.templates import templates
from app.security import require_panel_auth

router = APIRouter(dependencies=[Depends(require_panel_auth)])


@router.get("/painel/clientes", response_class=HTMLResponse)
def listar_clientes(
    request: Request,
    repository: CustomerRepository = Depends(get_customer_repository),
):
    clientes = repository.list_customers()
    return templates.TemplateResponse("clientes.html", {"request": request, "clientes": clientes})


@router.get("/painel/clientes/novo", response_class=HTMLResponse)
def novo_cliente(request: Request):
    return templates.TemplateResponse("cliente_form.html", {"request": request, "cliente": None})


@router.get("/painel/clientes/{cliente_id}/editar", response_class=HTMLResponse)
def editar_cliente(
    request: Request,
    cliente_id: int,
    repository: CustomerRepository = Depends(get_customer_repository),
):
    cliente = repository.get_customer(cliente_id)
    if cliente:
        return templates.TemplateResponse("cliente_form.html", {"request": request, "cliente": cliente})
    return RedirectResponse(url="/painel/clientes", status_code=302)


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
