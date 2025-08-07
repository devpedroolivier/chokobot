from sqlite3 import Connection
from app.db.database import get_connection

def criar_tabela_atendimentos(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS atendimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            mensagem TEXT NOT NULL,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        );
    """)
    conn.commit()

def salvar_atendimento(cliente_id: int, mensagem: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO atendimentos (cliente_id, mensagem)
        VALUES (?, ?)
    """, (cliente_id, mensagem))

    conn.commit()
    conn.close()
    print("💬 Atendimento registrado no banco.")

