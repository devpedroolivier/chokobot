from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.api.dependencies import get_order_repository
from app.application.use_cases.panel_dashboard import classify_order_visibility
from app.application.use_cases.panel_orders import build_create_order_payload, export_orders_txt
from app.domain.repositories.order_repository import OrderRepository
from app.infrastructure.web.admin_frontend import resolve_admin_frontend_url
from app.infrastructure.web.templates import templates
from app.security import require_panel_auth

router = APIRouter(dependencies=[Depends(require_panel_auth)])


class OrderCreatePayload(BaseModel):
    nome: str
    telefone: str
    produto: str = ""
    categoria: str = ""
    linha: str = ""
    tamanho: str = ""
    massa: str = ""
    recheio: str = ""
    mousse: str = ""
    adicional: str = ""
    fruta_ou_nozes: str = ""
    valor_total: str = "0"
    data_entrega: str
    horario: str = ""
    horario_retirada: str = ""


def build_orders_snapshot_payload(
    rows: list[tuple],
    *,
    statuses_by_id: dict[int, str] | None = None,
) -> dict:
    items = []
    for row in rows:
        order_id = int(row[0])
        delivery_date_raw = row[14] if len(row) > 14 else None
        value = row[15] if len(row) > 15 else None
        should_filter_visibility = len(row) > 15 or delivery_date_raw is not None or value is not None
        visibility = classify_order_visibility(
            customer_name=row[1],
            delivery_date_raw=delivery_date_raw,
            created_at_raw=row[11],
            value=value,
        )
        if should_filter_visibility and visibility["hide_from_views"]:
            continue
        items.append(
            {
                "id": order_id,
                "cliente_nome": row[1],
                "cliente_telefone": row[2],
                "categoria": row[3],
                "massa": row[4],
                "recheio": row[5],
                "mousse": row[6],
                "adicional": row[7],
                "tamanho": row[8],
                "gourmet": row[9],
                "entrega": row[10],
                "criado_em": row[11],
                "status": (statuses_by_id or {}).get(order_id, row[12] if len(row) > 12 and row[12] else "pendente"),
            }
        )
    return {"items": items, "count": len(items)}


def build_order_details_snapshot_payload(order_details: dict | None) -> dict:
    if order_details is None:
        return {"item": None}

    return {
        "item": {
            "id": order_details.get("id"),
            "cliente_nome": order_details.get("cliente_nome"),
            "categoria": order_details.get("categoria"),
            "produto": order_details.get("produto"),
            "tamanho": order_details.get("tamanho"),
            "massa": order_details.get("massa"),
            "recheio": order_details.get("recheio"),
            "mousse": order_details.get("mousse"),
            "adicional": order_details.get("adicional"),
            "descricao": order_details.get("descricao"),
            "fruta_ou_nozes": order_details.get("fruta_ou_nozes"),
            "kit_festou": order_details.get("kit_festou"),
            "quantidade": order_details.get("quantidade"),
            "serve_pessoas": order_details.get("serve_pessoas"),
            "data_entrega": order_details.get("data_entrega"),
            "horario": order_details.get("horario"),
            "horario_retirada": order_details.get("horario_retirada"),
            "valor_total": order_details.get("valor_total"),
            "status": order_details.get("status"),
            "criado_em": order_details.get("criado_em"),
        }
    }


@router.get("/painel/encomendas", response_class=HTMLResponse)
async def listar_encomendas(
    request: Request,
    repository: OrderRepository = Depends(get_order_repository),
):
    frontend_url = resolve_admin_frontend_url("/encomendas")
    if frontend_url:
        return RedirectResponse(url=frontend_url, status_code=302)

    encomendas = repository.list_for_orders_page()
    return templates.TemplateResponse(
        "encomendas.html",
        {"request": request, "encomendas": encomendas},
    )


@router.get("/painel/api/encomendas")
async def listar_encomendas_snapshot(
    repository: OrderRepository = Depends(get_order_repository),
):
    payload = build_orders_snapshot_payload(repository.list_for_orders_page())
    return JSONResponse(payload)


@router.get("/painel/encomendas/exportar")
async def exportar_encomendas_txt(
    repository: OrderRepository = Depends(get_order_repository),
):
    caminho = export_orders_txt(repository, "dados/export_encomendas.txt")
    return FileResponse(str(caminho), filename="encomendas.txt", media_type="text/plain")


@router.get("/painel/encomendas/novo", response_class=HTMLResponse)
def novo_encomenda_form(request: Request):
    frontend_url = resolve_admin_frontend_url("/encomendas/nova")
    if frontend_url:
        return RedirectResponse(url=frontend_url, status_code=302)
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
    repository.create_order(
        **build_create_order_payload(
            nome=nome,
            telefone=telefone,
            produto=produto,
            categoria=categoria,
            linha=linha,
            tamanho=tamanho,
            massa=massa,
            recheio=recheio,
            mousse=mousse,
            adicional=adicional,
            fruta_ou_nozes=fruta_ou_nozes,
            valor_total=valor_total,
            data_entrega=data_entrega,
            horario=horario,
            horario_retirada=horario_retirada,
        )
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
    frontend_url = resolve_admin_frontend_url(f"/encomendas/{id}")
    if frontend_url:
        return RedirectResponse(url=frontend_url, status_code=302)

    encomenda = repository.get_order_details(id)
    if encomenda is None:
        return HTMLResponse("<h3>Encomenda não encontrada.</h3>", status_code=404)

    return templates.TemplateResponse(
        "encomenda_detalhes.html",
        {"request": request, "encomenda": encomenda},
    )


@router.get("/painel/api/encomendas/{id}")
async def detalhes_encomenda_snapshot(
    id: int,
    repository: OrderRepository = Depends(get_order_repository),
):
    payload = build_order_details_snapshot_payload(repository.get_order_details(id))
    status_code = 404 if payload["item"] is None else 200
    return JSONResponse(payload, status_code=status_code)


@router.post("/painel/api/encomendas")
def criar_encomenda_snapshot(
    payload: OrderCreatePayload,
    repository: OrderRepository = Depends(get_order_repository),
):
    if not payload.nome.strip() or not payload.telefone.strip() or not payload.data_entrega.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_order_payload")

    order_id = repository.create_order(
        **build_create_order_payload(
            nome=payload.nome,
            telefone=payload.telefone,
            produto=payload.produto,
            categoria=payload.categoria,
            linha=payload.linha,
            tamanho=payload.tamanho,
            massa=payload.massa,
            recheio=payload.recheio,
            mousse=payload.mousse,
            adicional=payload.adicional,
            fruta_ou_nozes=payload.fruta_ou_nozes,
            valor_total=payload.valor_total,
            data_entrega=payload.data_entrega,
            horario=payload.horario,
            horario_retirada=payload.horario_retirada,
        )
    )
    return JSONResponse(
        {
            "ok": True,
            "id": order_id,
            "item": build_order_details_snapshot_payload(repository.get_order_details(order_id))["item"],
        },
        status_code=201,
    )


@router.delete("/painel/api/encomendas/{id}")
def excluir_encomenda_snapshot(
    id: int,
    repository: OrderRepository = Depends(get_order_repository),
):
    if repository.get_order_details(id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order_not_found")
    repository.delete_order(id)
    return JSONResponse({"ok": True, "id": id})
