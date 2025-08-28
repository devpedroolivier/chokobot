# app/models/encomendas.py
from typing import Dict, Any, Iterable, Tuple
from sqlite3 import Connection
from app.db.database import get_connection

# ————————————————————————————————————
# Criação + upgrade idempotente da tabela
# ————————————————————————————————————
def _colunas_existentes(conn: Connection, tabela: str) -> set:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({tabela})")
    return {r[1] for r in cur.fetchall()}

def criar_ou_atualizar_tabela_encomendas(conn: Connection):
    cur = conn.cursor()
    # cria se não existir
    cur.execute("""
        CREATE TABLE IF NOT EXISTS encomendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            produto TEXT,
            tamanho TEXT,
            descricao TEXT,
            fruta_ou_nozes TEXT,
            kit_festou INTEGER DEFAULT 0,
            quantidade INTEGER DEFAULT 1,
            data_entrega TEXT,
            horario_retirada TEXT,
            valor_total REAL,
            serve_pessoas INTEGER,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    """)
    # upgrade: adiciona colunas ausentes (para bases antigas)
    cols = _colunas_existentes(conn, "encomendas")
    add_cols = []
    if "categoria" not in cols:        add_cols.append(("categoria",        "TEXT"))
    if "produto" not in cols:          add_cols.append(("produto",          "TEXT"))
    if "tamanho" not in cols:          add_cols.append(("tamanho",          "TEXT"))
    if "descricao" not in cols:        add_cols.append(("descricao",        "TEXT"))
    if "fruta_ou_nozes" not in cols:   add_cols.append(("fruta_ou_nozes",   "TEXT"))
    if "kit_festou" not in cols:       add_cols.append(("kit_festou",       "INTEGER DEFAULT 0"))
    if "quantidade" not in cols:       add_cols.append(("quantidade",       "INTEGER DEFAULT 1"))
    if "horario_retirada" not in cols: add_cols.append(("horario_retirada", "TEXT"))
    if "valor_total" not in cols:      add_cols.append(("valor_total",      "REAL"))
    if "serve_pessoas" not in cols:    add_cols.append(("serve_pessoas",    "INTEGER"))
    for nome, tipo in add_cols:
        cur.execute(f"ALTER TABLE encomendas ADD COLUMN {nome} {tipo}")
    # índices
    cur.execute("CREATE INDEX IF NOT EXISTS ix_encomendas_cliente ON encomendas(cliente_id, criado_em)")
    conn.commit()

# ————————————————————————————————————
# Inserts
# ————————————————————————————————————
def salvar_encomenda_dict(cliente_id: int, pedido: Dict[str, Any]) -> int:
    """
    Espera um 'pedido' no formato já usado nos services (tradicional/ingles/redondo/torta/pronta),
    contendo pelo menos:
      categoria, produto(opcional), tamanho(opcional), descricao(opcional), fruta_ou_nozes(opcional),
      kit_festou(bool), quantidade(int), data_entrega, horario_retirada, valor_total, serve_pessoas
    Retorna o encomenda_id gerado.
    """
    conn = get_connection()
    criar_ou_atualizar_tabela_encomendas(conn)

    campos = [
        "cliente_id","categoria","produto","tamanho","descricao","fruta_ou_nozes",
        "kit_festou","quantidade","data_entrega","horario_retirada","valor_total","serve_pessoas"
    ]
    vals = (
        cliente_id,
        pedido.get("categoria"),
        pedido.get("produto"),
        pedido.get("tamanho"),
        pedido.get("descricao"),
        pedido.get("fruta_ou_nozes"),
        int(bool(pedido.get("kit_festou"))),
        int(pedido.get("quantidade", 1)),
        pedido.get("data_entrega"),
        pedido.get("horario_retirada"),
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
