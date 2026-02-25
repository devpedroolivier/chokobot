from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
import os

from app.api.dependencies import get_order_repository
from app.domain.repositories.order_repository import OrderRepository
from app.infrastructure.web.templates import templates

router = APIRouter()


@router.get("/painel/encomendas", response_class=HTMLResponse)
async def listar_encomendas(
    request: Request,
    repository: OrderRepository = Depends(get_order_repository),
):
    encomendas = repository.list_for_orders_page()
    return templates.TemplateResponse(
        "encomendas.html",
        {"request": request, "encomendas": encomendas},
    )


@router.get("/painel/encomendas/exportar")
async def exportar_encomendas_txt(
    repository: OrderRepository = Depends(get_order_repository),
):
    registros = repository.export_rows()

    os.makedirs("dados", exist_ok=True)
    caminho = "dados/export_encomendas.txt"

    with open(caminho, "w", encoding="utf-8") as f:
        for r in registros:
            cliente, produto, data, valor, status = r
            f.write(f"{cliente} | {produto or '-'} | {data or '-'} | R${valor or '0,00'} | {status}\n")

    return FileResponse(caminho, filename="encomendas.txt", media_type="text/plain")


@router.get("/painel/encomendas/novo", response_class=HTMLResponse)
def novo_encomenda_form(request: Request):
    return templates.TemplateResponse(
        "encomendas_form.html",
        {"request": request, "encomenda": None},
    )


@router.post("/painel/encomendas/novo")
def salvar_encomenda_form(
    nome: str = Form(...),
    telefone: str = Form(...),
    produto: str = Form(""),
    categoria: str = Form(""),
    linha: str = Form(""),
    tamanho: str = Form(""),
    massa: str = Form(""),
    recheio: str = Form(""),
    mousse: str = Form(""),
    adicional: str = Form(""),
    fruta_ou_nozes: str = Form(""),
    valor_total: str = Form("0"),
    data_entrega: str = Form(...),
    horario: str = Form(""),
    horario_retirada: str = Form(""),
    repository: OrderRepository = Depends(get_order_repository),
):
    categoria_final = categoria or linha or "normal"
    adicional_final = adicional or fruta_ou_nozes
    horario_final = horario or horario_retirada

    repository.create_order(
        nome=nome,
        telefone=telefone,
        categoria=categoria_final,
        produto=produto,
        tamanho=tamanho,
        massa=massa,
        recheio=recheio,
        mousse=mousse,
        adicional=adicional_final,
        horario=horario_final,
        valor_total=valor_total,
        data_entrega=data_entrega,
    )
    return RedirectResponse(url="/painel/encomendas", status_code=303)


@router.post("/painel/encomendas/{id}/excluir")
def excluir_encomenda(
    id: int,
    repository: OrderRepository = Depends(get_order_repository),
):
    repository.delete_order(id)
    return RedirectResponse(url="/painel/encomendas", status_code=303)


@router.get("/painel/encomendas/{id}", response_class=HTMLResponse)
async def detalhes_encomenda(
    request: Request,
    id: int,
    repository: OrderRepository = Depends(get_order_repository),
):
    encomenda = repository.get_order_details(id)
    if encomenda is None:
        return HTMLResponse("<h3>Encomenda não encontrada.</h3>", status_code=404)

    return templates.TemplateResponse(
        "encomenda_detalhes.html",
        {"request": request, "encomenda": encomenda},
    )
