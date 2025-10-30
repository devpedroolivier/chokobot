from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.db.database import get_connection

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/painel", response_class=HTMLResponse)
def painel_principal(request: Request):
    conn = get_connection()
    cursor = conn.cursor()

    # Carrega encomendas + status da entrega + nome do cliente (mesmo se cliente_id estiver nulo)
    cursor.execute("""
        SELECT 
            e.id,
            COALESCE(c.nome, '~') AS cliente_nome,
            e.produto,
            e.categoria,
            e.data_entrega,
            e.horario,
            e.valor_total,
            COALESCE(d.status, 'pendente') AS status,
            COALESCE(d.tipo, 'entrega') AS tipo
        FROM encomendas e
        LEFT JOIN clientes c ON e.cliente_id = c.id
        LEFT JOIN entregas d ON d.encomenda_id = e.id
        ORDER BY e.id DESC
    """)
    
    encomendas = [
        dict(zip([col[0] for col in cursor.description], row))
        for row in cursor.fetchall()
    ]
    conn.close()

    return templates.TemplateResponse("painel_principal.html", {
        "request": request,
        "encomendas": encomendas
    })


@router.post("/painel/encomendas/{id}/status")
def atualizar_status(id: int, status: str = Form(...)):
    """
    Atualiza o status da entrega de uma encomenda.
    Retorna JSON para ser consumido via fetch() no painel.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Verifica se já existe registro na tabela 'entregas'
    cursor.execute("SELECT id FROM entregas WHERE encomenda_id = ?", (id,))
    entrega_existente = cursor.fetchone()

    if entrega_existente:
        cursor.execute(
            "UPDATE entregas SET status = ? WHERE encomenda_id = ?",
            (status, id)
        )
    else:
        # Cria entrega caso ainda não exista
        cursor.execute(
            "INSERT INTO entregas (encomenda_id, status, tipo) VALUES (?, ?, 'entrega')",
            (id, status)
        )

    conn.commit()
    conn.close()

    return JSONResponse({"ok": True, "id": id, "status": status})
