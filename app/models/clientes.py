from sqlite3 import Connection
from app.db.database import get_connection

def criar_tabela_clientes(conn: Connection):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT NOT NULL,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()

def salvar_cliente(telefone: str, nome: str):
    conn = get_connection()
    cursor = conn.cursor()

    # Verifica se já existe o cliente
    cursor.execute("SELECT id FROM clientes WHERE telefone = ?", (telefone,))
    existente = cursor.fetchone()

    if existente:
        cliente_id = existente[0]
        # Atualiza o nome caso tenha mudado
        cursor.execute("UPDATE clientes SET nome = ? WHERE id = ?", (nome, cliente_id))
    else:
        cursor.execute("INSERT INTO clientes (nome, telefone) VALUES (?, ?)", (nome, telefone))
        cliente_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return cliente_id

