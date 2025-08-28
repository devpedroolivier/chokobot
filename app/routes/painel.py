# app/routes/painel.py
import sqlite3
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.db.database import get_connection

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# app/routes/painel.py
@router.get("/painel/encomendas", response_class=HTMLResponse)
def listar_encomendas(request: Request):
    conn = get_connection(); conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            e.id,
            c.nome AS cliente_nome,
            c.telefone AS cliente_telefone,
            e.categoria,
            e.tamanho,
            e.descricao,
            e.fruta_ou_nozes,
            e.valor_total,
            e.data_entrega,
            e.horario_retirada,
            d.status
        FROM encomendas e
        JOIN clientes c ON e.cliente_id = c.id
        LEFT JOIN entregas d ON d.encomenda_id = e.id
        ORDER BY e.id DESC

    """)
    encomendas = [dict(r) for r in cur.fetchall()]
    conn.close()
    return templates.TemplateResponse("encomendas_lista.html",
                                      {"request": request, "encomendas": encomendas})


@router.get("/painel/encomendas/{encomenda_id}", response_class=HTMLResponse)
def detalhar_encomenda(encomenda_id: int, request: Request):
    conn = get_connection(); conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM v_encomendas WHERE id = ?", (encomenda_id,))
    enc = cur.fetchone()
    cur.execute("SELECT * FROM encomenda_doces WHERE encomenda_id = ?", (encomenda_id,))
    doces = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT * FROM v_entregas WHERE encomenda_id = ?", (encomenda_id,))
    entrega = cur.fetchone()
    conn.close()

    return templates.TemplateResponse(
        "encomendas_detalhe.html",
        {
            "request": request,
            "encomenda": dict(enc) if enc else None,
            "doces": doces,
            "entrega": dict(entrega) if entrega else None
        }
    )
