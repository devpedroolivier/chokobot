from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from app.db.database import get_connection
import os

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# 🟦 LISTAGEM VISUAL (com botão de exportar)
@router.get("/painel/encomendas", response_class=HTMLResponse)
async def listar_encomendas(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            e.id,
            c.nome AS cliente_nome,
            c.telefone AS cliente_telefone,
            e.categoria,
            e.produto,
            e.tamanho,
            e.fruta_ou_nozes,
            e.valor_total,
            e.data_entrega,
            e.horario_retirada,
            COALESCE(d.status, 'pendente') AS status
        FROM encomendas e
        JOIN clientes c ON e.cliente_id = c.id
        LEFT JOIN entregas d ON d.encomenda_id = e.id
        ORDER BY e.id DESC
    """)

    rows = cursor.fetchall()
    colunas = [desc[0] for desc in cursor.description]
    encomendas = [dict(zip(colunas, row)) for row in rows]
    conn.close()

    return templates.TemplateResponse(
        "encomendas.html",
        {"request": request, "encomendas": encomendas}
    )


# 🟨 EXPORTAR PARA TXT
@router.get("/painel/encomendas/exportar")
async def exportar_encomendas_txt():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            c.nome AS cliente,
            e.produto,
            e.data_entrega,
            e.valor_total,
            COALESCE(d.status, 'pendente') AS status
        FROM encomendas e
        JOIN clientes c ON e.cliente_id = c.id
        LEFT JOIN entregas d ON d.encomenda_id = e.id
        ORDER BY e.id DESC
    """)
    registros = cursor.fetchall()
    conn.close()

    os.makedirs("dados", exist_ok=True)
    caminho = "dados/export_encomendas.txt"

    with open(caminho, "w", encoding="utf-8") as f:
        for r in registros:
            cliente, produto, data, valor, status = r
            f.write(f"{cliente} | {produto or '-'} | {data or '-'} | R${valor or '0,00'} | {status}\n")

    return FileResponse(caminho, filename="encomendas.txt", media_type="text/plain")


# 🟩 NOVA ENCOMENDA
@router.get("/painel/encomendas/novo", response_class=HTMLResponse)
def novo_encomenda_form(request: Request):
    return templates.TemplateResponse("encomendas_form.html", {
        "request": request,
        "encomenda": None
    })


@router.post("/painel/encomendas/novo")
def salvar_encomenda_form(
    nome: str = Form(...),
    telefone: str = Form(...),
    produto: str = Form(...),
    categoria: str = Form(...),
    tamanho: str = Form(...),
    fruta_ou_nozes: str = Form(...),
    valor_total: str = Form(...),
    data_entrega: str = Form(...),
    horario_retirada: str = Form(...)
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM clientes WHERE telefone = ?", (telefone,))
    cliente = cursor.fetchone()

    if not cliente:
        cursor.execute("INSERT INTO clientes (nome, telefone) VALUES (?, ?)", (nome, telefone))
        cliente_id = cursor.lastrowid
    else:
        cliente_id = cliente["id"]

    cursor.execute("""
        INSERT INTO encomendas (
            cliente_id, produto, categoria, tamanho, fruta_ou_nozes,
            valor_total, data_entrega, horario_retirada
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        cliente_id, produto, categoria, tamanho, fruta_ou_nozes,
        valor_total, data_entrega, horario_retirada
    ))

    conn.commit()
    conn.close()
    return RedirectResponse(url="/painel/encomendas", status_code=303)


# 🟥 EXCLUIR
@router.post("/painel/encomendas/{id}/excluir")
def excluir_encomenda(id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM encomendas WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/painel/encomendas", status_code=303)
