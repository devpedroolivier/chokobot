from sqlite3 import Connection
from app.db.database import get_connection

def criar_tabela_pedidos_cafeteria(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos_cafeteria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            pedido TEXT NOT NULL,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        );
    """)
    conn.commit()

def salvar_pedido_cafeteria(cliente_id: int, pedido: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO pedidos_cafeteria (cliente_id, pedido)
        VALUES (?, ?)
    """, (cliente_id, pedido))

    conn.commit()
    conn.close()
    print("☕ Pedido da cafeteria salvo com sucesso.")

