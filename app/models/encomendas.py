from sqlite3 import Connection
from app.db.database import get_connection

def criar_tabela_encomendas(conn: Connection):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS encomendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            produto TEXT NOT NULL,
            detalhes TEXT,
            data_entrega TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        );
    """)
    conn.commit()

def salvar_encomenda(cliente_id: int, produto: str, detalhes: str, data_entrega: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO encomendas (cliente_id, produto, detalhes, data_entrega)
        VALUES (?, ?, ?, ?)
    """, (cliente_id, produto, detalhes, data_entrega))

    conn.commit()
    conn.close()
    print("✅ Encomenda salva no banco de dados.")
