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

    # garante colunas existentes
    cols = _existing_columns(conn, "pedidos_cafeteria", ["cliente_id", "itens", "criado_em"])
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO pedidos_cafeteria ({', '.join(cols)}) VALUES ({placeholders})"

    values_map = {
        "cliente_id": cliente_id,
        "itens": itens_str,
        "criado_em": data_hora,
    }
    cur.execute(sql, [values_map.get(c) for c in cols])

    conn.commit()
    conn.close()
    print("☕ Pedido da cafeteria salvo no banco com sucesso.")


def salvar_encomenda_sqlite(phone: str, dados: dict, nome: str = "Nome não informado") -> int:
    """
    Salva encomenda usando SOMENTE as colunas que existem na tabela.
    Preenche 'categoria' (NOT NULL) com default seguro se não vier no fluxo.
    """
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

    # monta payload com chaves do fluxo (usa defaults seguros)
    payload = {
        "cliente_id":       cliente_id,
        "categoria":        dados.get("categoria") or dados.get("linha") or "tradicional",
        "linha":            dados.get("linha"),
        "massa":            dados.get("massa"),
        "recheio":          dados.get("recheio"),
        "mousse":           dados.get("mousse"),
        "adicional":        dados.get("adicional") or dados.get("fruta_ou_nozes"),
        "tamanho":          dados.get("tamanho"),
        "data_entrega":     dados.get("data_entrega") or dados.get("data") or dados.get("pronta_entrega"),
        "horario_retirada": dados.get("hora_entrega") or dados.get("horario_retirada"),
        "descricao":        dados.get("descricao") or dados.get("resumo"),
        "valor_total":      dados.get("valor_total") or dados.get("valor"),
        "serve_pessoas":    dados.get("serve_pessoas"),
        # opcionais (só entram se existirem na tabela)
        "gourmet":          1 if str(dados.get("gourmet", "")).lower() in ("1","true","sim","yes","gourmet") else 0,
        "entrega":          dados.get("tipo_entrega") or dados.get("entrega"),
        "produto":          dados.get("produto"),
        "quantidade":       dados.get("quantidade"),
        "kit_festou":       1 if str(dados.get("kit_festou", "")).lower() in ("1","true","sim","yes") else 0,
        "fruta_ou_nozes":   dados.get("fruta_ou_nozes"),
        "serve_pessoas":    dados.get("serve_pessoas"),
    }

    # define a ordem preferida de colunas; serão filtradas pelas que existem de verdade
    candidate_cols = [
        "cliente_id", "categoria", "linha", "massa", "recheio", "mousse",
        "adicional", "tamanho", "gourmet", "entrega", "data_entrega", "horario_retirada",
        "descricao", "valor_total", "serve_pessoas", "produto", "quantidade", "kit_festou", "fruta_ou_nozes"
    ]
    cols = _existing_columns(conn, "encomendas", candidate_cols)

    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO encomendas ({', '.join(cols)}) VALUES ({placeholders})"
    cur.execute(sql, [payload.get(c) for c in cols])

    encomenda_id = cur.lastrowid
    conn.commit()
    conn.close()
    print(f"📝 Encomenda salva com sucesso. ID: {encomenda_id}")
    return encomenda_id


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

    # colunas reais da tabela entregas
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
    cur.execute(sql, [values_map.get(c) for c in cols])

    conn.commit()
    conn.close()
    print(f"📦 Entrega registrada no banco - Tipo: {tipo}, Status: {status}")
