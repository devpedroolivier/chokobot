from datetime import datetime
from app.db.database import get_connection

def salvar_pedido_cafeteria_sqlite(phone: str, itens: list[str], nome: str = "Nome não informado"):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM clientes WHERE telefone = ?", (phone,))
    cliente = cursor.fetchone()

    if not cliente:
        cursor.execute("INSERT INTO clientes (nome, telefone) VALUES (?, ?)", (nome, phone))
        cliente_id = cursor.lastrowid
    else:
        cliente_id = cliente["id"]

    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    itens_str = ", ".join(itens)

    cursor.execute("""
        INSERT INTO pedidos_cafeteria (cliente_id, itens, criado_em)
        VALUES (?, ?, ?)
    """, (cliente_id, itens_str, data_hora))

    conn.commit()
    conn.close()
    print("☕ Pedido da cafeteria salvo no banco com sucesso.")


def salvar_encomenda_sqlite(phone: str, dados: dict, nome: str = "Nome não informado"):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM clientes WHERE telefone = ?", (phone,))
    cliente = cursor.fetchone()

    if not cliente:
        cursor.execute("INSERT INTO clientes (nome, telefone) VALUES (?, ?)", (nome, phone))
        cliente_id = cursor.lastrowid
    else:
        cliente_id = cliente["id"]

    cursor.execute("""
        INSERT INTO encomendas (
            cliente_id, linha, massa, recheio, mousse,
            adicional, tamanho, gourmet, data_entrega
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        cliente_id,
        dados.get("linha"),
        dados.get("massa"),
        dados.get("recheio"),
        dados.get("mousse"),
        dados.get("adicional"),
        dados.get("tamanho"),
        dados.get("gourmet"),
        dados.get("data", dados.get("pronta_entrega"))
    ))

    encomenda_id = cursor.lastrowid  # <-- Pega o ID gerado da encomenda

    conn.commit()
    conn.close()
    print(f"📝 Encomenda salva com sucesso. ID: {encomenda_id}")
    return encomenda_id


def salvar_entrega(
    encomenda_id: int,
    tipo: str = "entrega",
    endereco: str = None,
    data_agendada: str = None,
    status: str = "pendente"
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO entregas (encomenda_id, tipo, endereco, data_agendada, status)
        VALUES (?, ?, ?, ?, ?)
    """, (encomenda_id, tipo, endereco, data_agendada, status))

    conn.commit()
    conn.close()
    print(f"📦 Entrega registrada no banco - Tipo: {tipo}, Status: {status}")
