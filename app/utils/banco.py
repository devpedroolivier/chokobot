# app/utils/banco.py
from datetime import datetime
from typing import List, Optional
import sqlite3
from app.db.database import get_connection


def _get_id_from_row(row):
    # row pode ser sqlite3.Row (suporta ["id"]) ou tupla
    if row is None:
        return None
    try:
        return row["id"]
    except Exception:
        return row[0] if len(row) else None


def _existing_columns(conn: sqlite3.Connection, table: str, candidates: List[str]) -> List[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table});")
    existing = {r[1] for r in cur.fetchall()}  # nome da coluna = índice 1
    return [c for c in candidates if c in existing]


def salvar_pedido_cafeteria_sqlite(phone: str, itens: List[str], nome: str = "Nome não informado"):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # garante cliente
    cur.execute("SELECT id FROM clientes WHERE telefone = ?", (phone,))
    row = cur.fetchone()
    cliente_id = _get_id_from_row(row)
    if not cliente_id:
        cur.execute("INSERT INTO clientes (nome, telefone) VALUES (?, ?)", (nome, phone))
        cliente_id = cur.lastrowid

    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    itens_str = ", ".join(itens or [])

    cols = _existing_columns(conn, "pedidos_cafeteria", ["cliente_id", "itens", "criado_em"])
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO pedidos_cafeteria ({', '.join(cols)}) VALUES ({placeholders})"

    values_map = {
        "cliente_id": cliente_id,
        "itens": itens_str,
        "criado_em": data_hora,
    }

    try:
        cur.execute(sql, [values_map.get(c) for c in cols])
        conn.commit()
        print(f"☕ Pedido cafeteria salvo — Cliente: {nome} ({phone}), Itens: {itens_str}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao salvar pedido cafeteria: {e}")
    finally:
        conn.close()


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
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 🔹 Se não vier cliente_id, busca ou cria o cliente
    if not cliente_id:
        print(f"⚠️ cliente_id não informado — criando/recuperando pelo telefone {phone}")
        cur.execute("SELECT id FROM clientes WHERE telefone = ?", (phone,))
        row = cur.fetchone()
        cliente_id = _get_id_from_row(row)
        if not cliente_id:
            cur.execute("INSERT INTO clientes (nome, telefone) VALUES (?, ?)", (nome, phone))
            cliente_id = cur.lastrowid

    # 🔹 Coleta info de pagamento
    pagamento = dados.get("pagamento", {}) or {}
    forma_pagamento = pagamento.get("forma")
    troco_para = pagamento.get("troco_para")

    # 🔹 Monta payload principal
    payload = {
        "cliente_id": cliente_id,
        "categoria": dados.get("categoria") or dados.get("linha") or "tradicional",
        "linha": dados.get("linha"),
        "massa": dados.get("massa"),
        "recheio": dados.get("recheio"),
        "mousse": dados.get("mousse"),
        # garante que adicional e fruta_ou_nozes fiquem sincronizados
        "adicional": dados.get("fruta_ou_nozes") or dados.get("adicional"),
        "tamanho": dados.get("tamanho"),
        "data_entrega": dados.get("data_entrega") or dados.get("data") or dados.get("pronta_entrega"),
        "horario_retirada": dados.get("hora_entrega") or dados.get("horario_retirada"),
        "descricao": (dados.get("descricao") or dados.get("resumo") or "Bolo personalizado").strip(),
        "valor_total": dados.get("valor_total") or dados.get("valor") or 0,
        "serve_pessoas": dados.get("serve_pessoas"),
        "gourmet": 1 if str(dados.get("gourmet", "")).lower() in ("1", "true", "sim", "yes", "gourmet") else 0,
        "entrega": dados.get("tipo_entrega") or dados.get("entrega"),
        "produto": dados.get("produto"),
        "quantidade": dados.get("quantidade") or 1,
        "kit_festou": 1 if str(dados.get("kit_festou", "")).lower() in ("1", "true", "sim", "yes") else 0,
        "fruta_ou_nozes": dados.get("fruta_ou_nozes") or dados.get("adicional"),
        # novos campos de pagamento
        "forma_pagamento": forma_pagamento or "Pendente",
        "troco_para": troco_para,
    }

    # 🔹 Verifica colunas existentes (flexível)
    candidate_cols = [
        "cliente_id", "categoria", "linha", "massa", "recheio", "mousse",
        "adicional", "tamanho", "gourmet", "entrega", "data_entrega",
        "horario_retirada", "descricao", "valor_total", "serve_pessoas",
        "produto", "quantidade", "kit_festou", "fruta_ou_nozes",
        "forma_pagamento", "troco_para"
    ]
    cols = _existing_columns(conn, "encomendas", candidate_cols)

    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO encomendas ({', '.join(cols)}) VALUES ({placeholders})"

    try:
        cur.execute(sql, [payload.get(c) for c in cols])
        encomenda_id = cur.lastrowid
        conn.commit()
        print(
            f"📝 Encomenda salva com sucesso — ID {encomenda_id}, "
            f"Cliente: {nome} ({phone}), Categoria: {payload.get('categoria', 'n/d')}, "
            f"Valor: R${payload.get('valor_total', 0):.2f}"
        )
        return encomenda_id
    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao salvar encomenda: {e}")
        return -1
    finally:
        conn.close()


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
