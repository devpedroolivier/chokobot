from sqlite3 import Connection
from typing import Any, Dict

from app.db.database import get_connection


def _colunas_existentes(conn: Connection, tabela: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({tabela})")
    return {row[1] for row in cur.fetchall()}


def _migrar_colunas_encomendas(conn: Connection) -> None:
    cur = conn.cursor()
    existentes = _colunas_existentes(conn, "encomendas")

    faltantes = {
        "linha": "TEXT",
        "descricao": "TEXT",
        "fruta_ou_nozes": "TEXT",
        "forma_pagamento": "TEXT",
        "troco_para": "REAL",
    }

    for coluna, tipo in faltantes.items():
        if coluna not in existentes:
            cur.execute(f"ALTER TABLE encomendas ADD COLUMN {coluna} {tipo}")

    conn.commit()


def criar_ou_atualizar_tabela_encomendas(conn: Connection):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS encomendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            linha TEXT,
            produto TEXT,
            tamanho TEXT,
            massa TEXT,
            recheio TEXT,
            mousse TEXT,
            adicional TEXT,
            fruta_ou_nozes TEXT,
            descricao TEXT,
            kit_festou INTEGER DEFAULT 0,
            quantidade INTEGER DEFAULT 1,
            data_entrega TEXT,
            horario TEXT,
            valor_total REAL,
            serve_pessoas INTEGER,
            forma_pagamento TEXT,
            troco_para REAL,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
        """
    )
    _migrar_colunas_encomendas(conn)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_encomendas_cliente ON encomendas(cliente_id, criado_em)")
    conn.commit()


def salvar_encomenda_dict(cliente_id: int, pedido: Dict[str, Any]) -> int:
    """
    Salva um pedido na tabela encomendas com os campos canonicos do projeto.
    """
    conn = get_connection()
    criar_ou_atualizar_tabela_encomendas(conn)

    pagamento = pedido.get("pagamento") or {}
    adicional = pedido.get("adicional") or pedido.get("fruta_ou_nozes")

    campos = [
        "cliente_id",
        "categoria",
        "linha",
        "produto",
        "tamanho",
        "massa",
        "recheio",
        "mousse",
        "adicional",
        "fruta_ou_nozes",
        "descricao",
        "kit_festou",
        "quantidade",
        "data_entrega",
        "horario",
        "valor_total",
        "serve_pessoas",
        "forma_pagamento",
        "troco_para",
    ]
    vals = (
        cliente_id,
        pedido.get("categoria") or "tradicional",
        pedido.get("linha"),
        pedido.get("produto"),
        pedido.get("tamanho"),
        pedido.get("massa"),
        pedido.get("recheio"),
        pedido.get("mousse"),
        adicional,
        adicional,
        pedido.get("descricao"),
        int(bool(pedido.get("kit_festou"))),
        int(pedido.get("quantidade", 1)),
        pedido.get("data_entrega"),
        pedido.get("horario") or pedido.get("horario_retirada"),
        float(pedido.get("valor_total") or 0.0),
        int(pedido.get("serve_pessoas") or 0),
        pagamento.get("forma") or pedido.get("forma_pagamento") or "Pendente",
        pagamento.get("troco_para") if pagamento else pedido.get("troco_para"),
    )

    placeholders = ",".join("?" for _ in campos)
    sql = f"INSERT INTO encomendas ({','.join(campos)}) VALUES ({placeholders})"
    cur = conn.cursor()
    cur.execute(sql, vals)
    encomenda_id = cur.lastrowid
    conn.commit()
    conn.close()
    return encomenda_id
