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

def salvar_cliente(phone: str, nome: str = "Nome não informado"):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM clientes WHERE telefone = ?", (phone,))
    cliente = cursor.fetchone()

    if not cliente:
        cursor.execute("INSERT INTO clientes (nome, telefone) VALUES (?, ?)", (nome, phone))
        conn.commit()
        print(f"📝 Novo cliente salvo: {nome} | {phone}")
    else:
        print(f"🔁 Cliente já cadastrado: {phone}")

    conn.close()

