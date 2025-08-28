from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from app.db.database import get_connection
from fastapi.responses import HTMLResponse
router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.filters["str"] = str  # permite usar |str no Jinja

# 🟦 LISTAGEM VISUAL
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
            e.descricao,
            e.tamanho,
            e.fruta_ou_nozes,
            e.valor_total,       -- 👈 valor total garantido
            e.data_entrega,
            e.horario_retirada,
            d.status
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
        {
            "request": request,
            "encomendas": encomendas
        }
    )


# 🟩 NOVA ENCOMENDA - FORMULÁRIO
@router.get("/painel/encomendas/novo")
def novo_encomenda_form(request: Request):
    return templates.TemplateResponse("encomendas_form.html", {
        "request": request,
        "encomenda": None
    })


# 🟩 NOVA ENCOMENDA - SALVAR
@router.post("/painel/encomendas/novo")
def salvar_encomenda_form(
    request: Request,
    nome: str = Form(...),
    telefone: str = Form(...),
    linha: str = Form(...),
    massa: str = Form(...),
    recheio: str = Form(...),
    mousse: str = Form(...),
    adicional: str = Form(...),
    tamanho: str = Form(...),
    gourmet: str = Form(...),
    entrega: str = Form(...),
    data_entrega: str = Form(...)
):
    conn = get_connection()
    cursor = conn.cursor()

    # verifica se o cliente já existe
    cursor.execute("SELECT id FROM clientes WHERE telefone = ?", (telefone,))
    cliente = cursor.fetchone()

    if not cliente:
        cursor.execute("INSERT INTO clientes (nome, telefone) VALUES (?, ?)", (nome, telefone))
        cliente_id = cursor.lastrowid
    else:
        cliente_id = cliente["id"]

    # insere a encomenda
    cursor.execute("""
        INSERT INTO encomendas (
            cliente_id, linha, massa, recheio, mousse,
            adicional, tamanho, gourmet, entrega, data_entrega
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        cliente_id, linha, massa, recheio, mousse,
        adicional, tamanho, gourmet, entrega, data_entrega
    ))

    conn.commit()
    conn.close()
    return RedirectResponse(url="/painel/encomendas", status_code=303)


# 🟨 EDITAR - FORMULÁRIO
@router.get("/painel/encomendas/{id}/editar")
def editar_encomenda_form(id: int, request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.id, c.nome, c.telefone,
            e.linha, e.massa, e.recheio, e.mousse,
            e.adicional, e.tamanho, e.gourmet,
            e.data_entrega, e.entrega
        FROM encomendas e
        JOIN clientes c ON e.cliente_id = c.id
        WHERE e.id = ?
    """, (id,))
    encomenda = cursor.fetchone()

    if not encomenda:
        return RedirectResponse(url="/painel/encomendas", status_code=302)

    return templates.TemplateResponse("encomendas_form.html", {
        "request": request,
        "encomenda": encomenda
    })


# 🟨 EDITAR - SALVAR
@router.post("/painel/encomendas/{id}/editar")
def atualizar_encomenda_form(
    id: int,
    nome: str = Form(...),
    telefone: str = Form(...),
    linha: str = Form(...),
    massa: str = Form(...),
    recheio: str = Form(...),
    mousse: str = Form(...),
    adicional: str = Form(...),
    tamanho: str = Form(...),
    gourmet: str = Form(...),
    entrega: str = Form(...),
    data_entrega: str = Form(...)
):
    conn = get_connection()
    cursor = conn.cursor()

    # busca cliente atual da encomenda
    cursor.execute("SELECT cliente_id FROM encomendas WHERE id = ?", (id,))
    encomenda = cursor.fetchone()
    if not encomenda:
        conn.close()
        return RedirectResponse(url="/painel/encomendas", status_code=302)

    # atualiza cliente
    cursor.execute("UPDATE clientes SET nome = ?, telefone = ? WHERE id = ?", (nome, telefone, encomenda["cliente_id"]))

    # atualiza encomenda
    cursor.execute("""
        UPDATE encomendas
        SET linha = ?, massa = ?, recheio = ?, mousse = ?,
            adicional = ?, tamanho = ?, gourmet = ?, entrega = ?, data_entrega = ?
        WHERE id = ?
    """, (
        linha, massa, recheio, mousse,
        adicional, tamanho, gourmet, entrega, data_entrega, id
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
