from app.db.database import get_connection

def criar_tabelas():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        telefone TEXT,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS encomendas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER,
        produto TEXT,
        detalhes TEXT,
        data_entrega TEXT,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(cliente_id) REFERENCES clientes(id)
    );

    CREATE TABLE IF NOT EXISTS entregas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        encomenda_id INTEGER,
        status TEXT,
        atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(encomenda_id) REFERENCES encomendas(id)
    );

    CREATE TABLE IF NOT EXISTS atendimentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER,
        mensagem TEXT,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(cliente_id) REFERENCES clientes(id)
    );

    CREATE TABLE IF NOT EXISTS pedidos_cafeteria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER,
        pedido TEXT,
        criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(cliente_id) REFERENCES clientes(id)
    );
    """)

    conn.commit()
    conn.close()
