# app/utils/banco.py
from datetime import datetime
from typing import List, Optional

from app.db.database import get_connection
from app.infrastructure.repositories.sqlite_order_write_repository import SQLiteOrderWriteRepository


def salvar_pedido_cafeteria_sqlite(phone: str, itens: List[str], nome: str = "Nome não informado"):
    SQLiteOrderWriteRepository().save_cafeteria_items(
        phone=phone,
        itens=itens,
        nome_cliente=nome,
    )


def salvar_encomenda_sqlite(
    phone: str,
    dados: dict,
    nome: str = "Nome não informado",
    cliente_id: int | None = None
) -> int:
    """
    Salva encomenda no SQLite (com suporte a forma_pagamento e troco_para).
    - Se cliente_id for informado, usa diretamente.
    - Caso contrário, localiza ou cria o cliente pelo telefone.
    Somente as colunas existentes são usadas, então não quebra o banco.
    """
    return SQLiteOrderWriteRepository().save_order_payload(
        phone=phone,
        dados=dados,
        nome_cliente=nome,
        cliente_id=cliente_id,
    )


def salvar_entrega(
    encomenda_id: int,
    tipo: str = "entrega",
    endereco: Optional[str] = None,
    data_agendada: Optional[str] = None,
    status: str = "pendente",
):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    candidate_cols = ["encomenda_id", "tipo", "endereco", "data_agendada", "status", "criado_em"]
    cols = _existing_columns(conn, "entregas", candidate_cols)

    values_map = {
        "encomenda_id": encomenda_id,
        "tipo": tipo,
        "endereco": endereco,
        "data_agendada": data_agendada,
        "status": status,
        "criado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO entregas ({', '.join(cols)}) VALUES ({placeholders})"

    try:
        cur.execute(sql, [values_map.get(c) for c in cols])
        conn.commit()
        print(f"📦 Entrega registrada no banco - Tipo: {tipo}, Status: {status}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao salvar entrega: {e}")
    finally:
        conn.close()
