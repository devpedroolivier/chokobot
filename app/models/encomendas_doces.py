# app/models/encomenda_doces.py
from typing import Iterable, Dict, Any
from sqlite3 import Connection
from app.db.database import get_connection

def criar_tabela_encomenda_doces(conn: Connection):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS encomenda_doces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            encomenda_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            qtd INTEGER NOT NULL,
            preco REAL,
            unit REAL,
            FOREIGN KEY (encomenda_id) REFERENCES encomendas(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_doces_encomenda ON encomenda_doces(encomenda_id)")
    conn.commit()

def salvar_doce_encomenda(encomenda_id: int, nome: str, qtd: int, preco: float | None, unit: float | None):
    conn = get_connection()
    criar_tabela_encomenda_doces(conn)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO encomenda_doces (encomenda_id, nome, qtd, preco, unit)
        VALUES (?, ?, ?, ?, ?)
    """, (encomenda_id, nome, int(qtd), None if preco is None else float(preco), None if unit is None else float(unit)))
    conn.commit()
    conn.close()

def salvar_varios_doces(encomenda_id: int, itens: Iterable[Dict[str, Any]]):
    for d in itens or []:
        salvar_doce_encomenda(
            encomenda_id,
            d.get("nome",""),
            int(d.get("qtd", 1)),
            d.get("preco"),
            d.get("unit"),
        )
