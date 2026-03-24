from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


TEST_NAME_TOKENS = ("teste", "suporte", "pessoal")


def _looks_like_test_customer(name: str | None) -> bool:
    normalized = (name or "").casefold()
    return any(token in normalized for token in TEST_NAME_TOKENS)


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _find_test_customers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    rows = conn.execute("SELECT id, nome, telefone, criado_em FROM clientes ORDER BY id").fetchall()
    return [row for row in rows if _looks_like_test_customer(row["nome"])]


def _find_orders_for_customers(conn: sqlite3.Connection, customer_ids: list[int]) -> list[sqlite3.Row]:
    if not customer_ids:
        return []
    placeholders = ", ".join("?" for _ in customer_ids)
    return conn.execute(
        f"""
        SELECT
            e.id,
            e.cliente_id,
            c.nome AS cliente_nome,
            c.telefone,
            e.categoria,
            e.produto,
            e.data_entrega,
            e.horario,
            e.valor_total,
            e.criado_em
        FROM encomendas e
        JOIN clientes c ON c.id = e.cliente_id
        WHERE e.cliente_id IN ({placeholders})
        ORDER BY e.id
        """,
        customer_ids,
    ).fetchall()


def _delete_test_data(
    conn: sqlite3.Connection,
    *,
    customer_ids: list[int],
    order_ids: list[int],
    phones: list[str],
) -> None:
    cursor = conn.cursor()

    if order_ids:
        placeholders = ", ".join("?" for _ in order_ids)
        cursor.execute(f"DELETE FROM encomenda_doces WHERE encomenda_id IN ({placeholders})", order_ids)
        cursor.execute(f"DELETE FROM entregas WHERE encomenda_id IN ({placeholders})", order_ids)
        cursor.execute(
            f"UPDATE customer_processes SET order_id = NULL, updated_at = CURRENT_TIMESTAMP WHERE order_id IN ({placeholders})",
            order_ids,
        )
        cursor.execute(f"DELETE FROM encomendas WHERE id IN ({placeholders})", order_ids)

    if phones:
        phone_placeholders = ", ".join("?" for _ in phones)
        cursor.execute(f"DELETE FROM customer_processes WHERE phone IN ({phone_placeholders})", phones)

    if customer_ids:
        customer_placeholders = ", ".join("?" for _ in customer_ids)
        cursor.execute(f"DELETE FROM clientes WHERE id IN ({customer_placeholders})", customer_ids)

    conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove clientes e encomendas de teste explicitos do banco SQLite da Chokobot."
    )
    parser.add_argument("--db-path", default="dados/chokobot.db", help="Caminho para o banco SQLite.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica a limpeza. Sem esta flag, o script apenas mostra o que seria removido.",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        raise SystemExit(f"Banco nao encontrado: {db_path}")

    conn = _connect(db_path)
    try:
        customers = _find_test_customers(conn)
        customer_ids = [int(row["id"]) for row in customers]
        orders = _find_orders_for_customers(conn, customer_ids)
        order_ids = [int(row["id"]) for row in orders]
        phones = [str(row["telefone"]) for row in customers if row["telefone"]]

        print(f"Banco: {db_path}")
        print(f"Clientes de teste explicitos: {len(customers)}")
        print(f"Encomendas ligadas a esses clientes: {len(orders)}")

        if customers:
            print("\nClientes:")
            for row in customers:
                print(f"- #{row['id']} | {row['nome']} | {row['telefone']} | criado em {row['criado_em']}")

        if orders:
            print("\nEncomendas:")
            for row in orders:
                produto = row["produto"] or row["categoria"] or "-"
                print(
                    f"- pedido #{row['id']} | cliente #{row['cliente_id']} | {row['cliente_nome']} | "
                    f"{produto} | data {row['data_entrega'] or '-'} | valor {row['valor_total'] or 0}"
                )

        if not args.apply:
            print("\nDry-run concluido. Use --apply para remover os registros listados acima.")
            return 0

        _delete_test_data(
            conn,
            customer_ids=customer_ids,
            order_ids=order_ids,
            phones=phones,
        )
        print("\nLimpeza aplicada com sucesso.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
