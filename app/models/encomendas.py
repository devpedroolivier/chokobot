# app/models/encomendas.py
from typing import Dict, Any
from sqlite3 import Connection
from app.db.database import get_connection

# ————————————————————————————————————
# Criação da tabela (com massa, recheio, mousse, adicional)
# ————————————————————————————————————
def criar_ou_atualizar_tabela_encomendas(conn: Connection):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS encomendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            produto TEXT,
            tamanho TEXT,
            massa TEXT,
            recheio TEXT,
            mousse TEXT,
            adicional TEXT,
            kit_festou INTEGER DEFAULT 0,
            quantidade INTEGER DEFAULT 1,
            data_entrega TEXT,
            horario TEXT,
            valor_total REAL,
            serve_pessoas INTEGER,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_encomendas_cliente ON encomendas(cliente_id, criado_em)")
    conn.commit()

# ————————————————————————————————————
# Insert com novos campos
# ————————————————————————————————————
def salvar_encomenda_dict(cliente_id: int, pedido: Dict[str, Any]) -> int:
    """
    Espera um 'pedido' no formato já usado nos services,
    contendo pelo menos:
      categoria, produto(opcional), tamanho(opcional),
      massa, recheio, mousse, adicional (opcionais para tradicionais),
      kit_festou(bool), quantidade(int),
      data_entrega, horario, valor_total, serve_pessoas
    Retorna o encomenda_id gerado.
    """
    conn = get_connection()
    criar_ou_atualizar_tabela_encomendas(conn)

    campos = [
        "cliente_id","categoria","produto","tamanho",
        "massa","recheio","mousse","adicional",
        "kit_festou","quantidade","data_entrega","horario",
        "valor_total","serve_pessoas"
    ]
    vals = (
        cliente_id,
        pedido.get("categoria"),
        pedido.get("produto"),
        pedido.get("tamanho"),
        pedido.get("massa"),
        pedido.get("recheio"),
        pedido.get("mousse"),
        pedido.get("adicional"),
        int(bool(pedido.get("kit_festou"))),
        int(pedido.get("quantidade", 1)),
        pedido.get("data_entrega"),
        pedido.get("horario"),
        float(pedido.get("valor_total") or 0.0),
        int(pedido.get("serve_pessoas") or 0),
    )

    placeholders = ",".join("?" for _ in campos)
    sql = f"INSERT INTO encomendas ({','.join(campos)}) VALUES ({placeholders})"
    cur = conn.cursor()
    cur.execute(sql, vals)
    encomenda_id = cur.lastrowid
    conn.commit()
    conn.close()
    return encomenda_id
