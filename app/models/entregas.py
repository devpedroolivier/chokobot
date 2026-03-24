from sqlite3 import Connection
from app.db.database import get_connection


# 🔧 Criar tabela se não existir
def criar_tabela_entregas(conn: Connection):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entregas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            encomenda_id INTEGER NOT NULL,
            tipo TEXT DEFAULT 'entrega',
            endereco TEXT,
            data_agendada TEXT,
            status TEXT DEFAULT 'pendente',
            atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (encomenda_id) REFERENCES encomendas(id)
        );
    """)
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_entregas_encomenda_id
        ON entregas(encomenda_id)
        """
    )
    conn.commit()

# 💾 Salvar entrega no banco SQLite
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
