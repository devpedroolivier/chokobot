import os

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.db.database import get_connection
from app.security import require_panel_auth
from app.templates_engine import templates

router = APIRouter(dependencies=[Depends(require_panel_auth)])


@router.get("/painel/encomendas", response_class=HTMLResponse)
async def listar_encomendas(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            e.id,
            c.nome AS cliente_nome,
            c.telefone AS cliente_telefone,
            COALESCE(NULLIF(e.linha, ''), e.categoria) AS linha,
            e.categoria,
            e.produto,
            e.massa,
            e.recheio,
            e.mousse,
            COALESCE(e.adicional, e.fruta_ou_nozes) AS adicional,
            e.tamanho,
            e.data_entrega,
            e.horario,
            e.valor_total,
            e.criado_em,
            COALESCE(d.status, 'pendente') AS status,
            COALESCE(d.tipo, 'retirada') AS tipo_entrega
        FROM encomendas e
        JOIN clientes c ON e.cliente_id = c.id
        LEFT JOIN entregas d ON d.encomenda_id = e.id
        ORDER BY e.id DESC
        """
    )

    rows = cursor.fetchall()
    colunas = [desc[0] for desc in cursor.description]
    encomendas = [dict(zip(colunas, row)) for row in rows]
    conn.close()

    return templates.TemplateResponse(
        "encomendas.html",
        {"request": request, "encomendas": encomendas},
    )


@router.get("/painel/encomendas/exportar")
async def exportar_encomendas_txt():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            c.nome AS cliente,
            COALESCE(e.produto, e.descricao, '-') AS produto,
            e.data_entrega,
            e.valor_total,
            COALESCE(d.status, 'pendente') AS status
        FROM encomendas e
        JOIN clientes c ON e.cliente_id = c.id
        LEFT JOIN entregas d ON d.encomenda_id = e.id
        ORDER BY e.id DESC
        """
    )
    registros = cursor.fetchall()
    conn.close()

    os.makedirs("dados", exist_ok=True)
    caminho = "dados/export_encomendas.txt"

    with open(caminho, "w", encoding="utf-8") as f:
        for cliente, produto, data, valor, status in registros:
            f.write(f"{cliente} | {produto or '-'} | {data or '-'} | R${valor or '0.00'} | {status}\n")

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
    linha: str = Form(""),
    categoria: str = Form(""),
    produto: str = Form(""),
    massa: str = Form(""),
    recheio: str = Form(""),
    mousse: str = Form(""),
    adicional: str = Form(""),
    tamanho: str = Form(""),
    data_entrega: str = Form(...),
    horario: str = Form(""),
    horario_retirada: str = Form(""),
    valor_total: float = Form(0.0),
    quantidade: int = Form(1),
    kit_festou: int = Form(0),
    entrega: str = Form(""),
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

    categoria_final = (categoria or linha or "tradicional").strip().lower()
    adicional_final = (adicional or "").strip() or None
    horario_final = (horario or horario_retirada or "").strip() or None

    descricao = " | ".join(
        p.strip() for p in [massa, recheio, mousse] if (p or "").strip()
    )
    if not descricao:
        descricao = produto or categoria_final

    cursor.execute(
        """
        INSERT INTO encomendas (
            cliente_id, categoria, linha, produto, tamanho,
            massa, recheio, mousse,
            adicional, fruta_ou_nozes, descricao,
            kit_festou, quantidade, data_entrega, horario, valor_total
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cliente_id,
            categoria_final,
            (linha or "").strip() or None,
            (produto or "").strip() or None,
            (tamanho or "").strip() or None,
            (massa or "").strip() or None,
            (recheio or "").strip() or None,
            (mousse or "").strip() or None,
            adicional_final,
            adicional_final,
            descricao,
            int(bool(kit_festou)),
            max(1, int(quantidade or 1)),
            data_entrega,
            horario_final,
            float(valor_total or 0.0),
        ),
    )
    encomenda_id = cursor.lastrowid

    entrega_txt = (entrega or "").strip().lower()
    if entrega_txt:
        tipo = "entrega" if entrega_txt in {"sim", "entrega", "delivery", "casa"} else "retirada"
        status = "pendente" if tipo == "entrega" else "Retirar na loja"
        cursor.execute(
            "INSERT INTO entregas (encomenda_id, tipo, status) VALUES (?, ?, ?)",
            (encomenda_id, tipo, status),
        )

    conn.commit()
    conn.close()
    return RedirectResponse(url="/painel/encomendas", status_code=303)


@router.post("/painel/encomendas/{id}/excluir")
def excluir_encomenda(id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM encomendas WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/painel/encomendas", status_code=303)


@router.get("/painel/encomendas/{id}", response_class=HTMLResponse)
async def detalhes_encomenda(request: Request, id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            e.*,
            c.nome AS cliente_nome,
            c.telefone AS cliente_telefone,
            COALESCE(d.status, 'pendente') AS status,
            COALESCE(d.tipo, 'retirada') AS tipo_entrega
        FROM encomendas e
        LEFT JOIN clientes c ON c.id = e.cliente_id
        LEFT JOIN entregas d ON d.encomenda_id = e.id
        WHERE e.id = ?
        ORDER BY d.id DESC
        LIMIT 1
        """,
        (id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return HTMLResponse("<h3>Encomenda nao encontrada.</h3>", status_code=404)

    return templates.TemplateResponse(
        "encomenda_detalhes.html",
        {"request": request, "encomenda": dict(row)},
    )
