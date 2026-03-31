from sqlite3 import Connection

from app.db.database import get_connection


def _table_exists(conn: Connection, table_name: str) -> bool:
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table_name,))
    return cursor.fetchone() is not None


def _dedupe_clientes_por_telefone(conn: Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT telefone, MIN(id) AS canonical_id, GROUP_CONCAT(id) AS all_ids
        FROM clientes
        WHERE COALESCE(TRIM(telefone), '') <> ''
        GROUP BY telefone
        HAVING COUNT(*) > 1
        """
    )
    duplicates = cursor.fetchall()
    if not duplicates:
        return

    has_encomendas = _table_exists(conn, "encomendas")
    has_atendimentos = _table_exists(conn, "atendimentos")
    has_cafeteria = _table_exists(conn, "pedidos_cafeteria")
    has_processes = _table_exists(conn, "customer_processes")

    for row in duplicates:
        canonical_id = int(row[1])
        all_ids = [int(token) for token in str(row[2] or "").split(",") if token]
        duplicate_ids = [customer_id for customer_id in all_ids if customer_id != canonical_id]
        if not duplicate_ids:
            continue

        placeholders = ",".join("?" for _ in duplicate_ids)
        params = [canonical_id, *duplicate_ids]

        if has_encomendas:
            cursor.execute(
                f"UPDATE encomendas SET cliente_id = ? WHERE cliente_id IN ({placeholders})",
                params,
            )
        if has_atendimentos:
            cursor.execute(
                f"UPDATE atendimentos SET cliente_id = ? WHERE cliente_id IN ({placeholders})",
                params,
            )
        if has_cafeteria:
            cursor.execute(
                f"UPDATE pedidos_cafeteria SET cliente_id = ? WHERE cliente_id IN ({placeholders})",
                params,
            )
        if has_processes:
            cursor.execute(
                f"UPDATE customer_processes SET customer_id = ? WHERE customer_id IN ({placeholders})",
                params,
            )

        cursor.execute(
            f"DELETE FROM clientes WHERE id IN ({placeholders})",
            duplicate_ids,
        )


def criar_tabela_clientes(conn: Connection):
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT NOT NULL,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    _dedupe_clientes_por_telefone(conn)
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_clientes_telefone
        ON clientes(telefone)
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_clientes_telefone
        ON clientes(telefone)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_clientes_criado_em
        ON clientes(criado_em)
        """
    )
    conn.commit()


def salvar_cliente(telefone: str, nome: str):
    conn = get_connection()
    cursor = conn.cursor()

    # Verifica se já existe o cliente
    cursor.execute("SELECT id FROM clientes WHERE telefone = ?", (telefone,))
    existente = cursor.fetchone()

    if existente:
        cliente_id = existente[0]
        # Atualiza o nome caso tenha mudado
        cursor.execute("UPDATE clientes SET nome = ? WHERE id = ?", (nome, cliente_id))
    else:
        cursor.execute("INSERT INTO clientes (nome, telefone) VALUES (?, ?)", (nome, telefone))
        cliente_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return cliente_id
