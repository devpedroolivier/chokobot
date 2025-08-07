from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.db.database import get_connection
from app.templates_engine import templates

router = APIRouter()

@router.get("/painel", response_class=HTMLResponse)
def painel_principal(request: Request):
    return templates.TemplateResponse("painel.html", {"request": request})

@router.get("/painel/encomendas", response_class=HTMLResponse)
def painel_encomendas(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            e.id,
            c.nome,
            c.telefone,
            e.linha,
            e.massa,
            e.recheio,
            e.mousse,
            e.adicional,
            e.tamanho,
            e.gourmet,
            e.data_entrega,
            e.criado_em
        FROM encomendas e
        JOIN clientes c ON c.id = e.cliente_id
        ORDER BY e.criado_em DESC
    """)
    encomendas = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse("encomendas.html", {
        "request": request,
        "encomendas": encomendas
    })


@router.get("/painel/clientes", response_class=HTMLResponse)
def painel_clientes(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM clientes ORDER BY criado_em DESC")
    clientes = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse("clientes.html", {"request": request, "clientes": clientes})


@router.get("/painel/entregas", response_class=HTMLResponse)
def painel_entregas(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT e.id, c.nome, e.status, e.atualizado_em
        FROM entregas e
        JOIN encomendas en ON en.id = e.encomenda_id
        JOIN clientes c ON c.id = en.cliente_id
        ORDER BY e.atualizado_em DESC
    """)
    entregas = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse("entregas.html", {"request": request, "entregas": entregas})


@router.get("/painel/cafeteria", response_class=HTMLResponse)
def painel_cafeteria(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.id, c.nome, p.itens, p.criado_em
        FROM pedidos_cafeteria p
        JOIN clientes c ON c.id = p.cliente_id
        ORDER BY p.criado_em DESC
    """)
    pedidos = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse("cafeteria.html", {"request": request, "pedidos": pedidos})


@router.get("/painel/atendimentos", response_class=HTMLResponse)
def painel_atendimentos(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.id, c.nome, a.mensagem, a.criado_em
        FROM atendimentos a
        JOIN clientes c ON c.id = a.cliente_id
        ORDER BY a.criado_em DESC
    """)
    atendimentos = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse("atendimentos.html", {"request": request, "atendimentos": atendimentos})
