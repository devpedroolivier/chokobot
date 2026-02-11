from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.db.database import get_connection
from app.security import require_panel_auth
from app.templates_engine import templates

router = APIRouter(dependencies=[Depends(require_panel_auth)])


@router.get("/painel", response_class=HTMLResponse)
def painel_principal(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            e.id,
            COALESCE(c.nome, '~') AS cliente_nome,
            e.produto,
            e.categoria,
            e.data_entrega,
            e.horario,
            e.valor_total,
            COALESCE(d.status, 'pendente') AS status,
            COALESCE(d.tipo, 'retirada') AS tipo
        FROM encomendas e
        LEFT JOIN clientes c ON e.cliente_id = c.id
        LEFT JOIN entregas d ON d.encomenda_id = e.id
        ORDER BY e.id DESC
        """
    )

    encomendas = [
        dict(zip([col[0] for col in cursor.description], row))
        for row in cursor.fetchall()
    ]
    conn.close()

    return templates.TemplateResponse(
        "painel_principal.html",
        {"request": request, "encomendas": encomendas},
    )


@router.post("/painel/encomendas/{id}/status")
def atualizar_status(id: int, status: str = Form(...)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM entregas WHERE encomenda_id = ?", (id,))
    entrega_existente = cursor.fetchone()

    if entrega_existente:
        cursor.execute(
            "UPDATE entregas SET status = ?, atualizado_em = CURRENT_TIMESTAMP WHERE encomenda_id = ?",
            (status, id),
        )
    else:
        cursor.execute(
            "INSERT INTO entregas (encomenda_id, status, tipo, atualizado_em) VALUES (?, ?, 'entrega', CURRENT_TIMESTAMP)",
            (id, status),
        )

    conn.commit()
    conn.close()

    return JSONResponse({"ok": True, "id": id, "status": status})
