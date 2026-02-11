from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db.database import get_connection
from app.security import require_panel_auth
from app.templates_engine import templates

router = APIRouter(dependencies=[Depends(require_panel_auth)])


@router.get("/painel/clientes", response_class=HTMLResponse)
def listar_clientes(request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clientes ORDER BY criado_em DESC")
    clientes = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("clientes.html", {"request": request, "clientes": clientes})


@router.get("/painel/clientes/novo", response_class=HTMLResponse)
def novo_cliente(request: Request):
    return templates.TemplateResponse("cliente_form.html", {"request": request, "cliente": None})


@router.get("/painel/clientes/{cliente_id}/editar", response_class=HTMLResponse)
def editar_cliente(request: Request, cliente_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,))
    cliente = cursor.fetchone()
    conn.close()

    if cliente:
        return templates.TemplateResponse("cliente_form.html", {"request": request, "cliente": cliente})

    return RedirectResponse(url="/painel/clientes", status_code=302)


@router.post("/painel/clientes/{cliente_id}/editar")
def atualizar_cliente(cliente_id: int, nome: str = Form(...), telefone: str = Form(...)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE clientes SET nome = ?, telefone = ? WHERE id = ?",
        (nome, telefone, cliente_id),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/painel/clientes", status_code=302)


@router.post("/painel/clientes")
def salvar_novo_cliente(nome: str = Form(...), telefone: str = Form(...)):
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO clientes (nome, telefone, criado_em) VALUES (?, ?, ?)",
        (nome, telefone, agora),
    )
    conn.commit()
    conn.close()
    return RedirectResponse(url="/painel/clientes", status_code=302)


@router.post("/painel/clientes/{cliente_id}/excluir")
def excluir_cliente(cliente_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/painel/clientes", status_code=302)
