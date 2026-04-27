"""Postgres implementation of OrderRepository (Phase B.8a).

Mirrors ``SQLiteOrderRepository`` but enforces ``tenant_id`` on every
read/write, joining children only within the same tenant. The schema
joined here lives in migration 0003 (encomendas / clientes / entregas
all carry ``tenant_id``).
"""
from __future__ import annotations

from app.db.database import open_postgres_connection, resolve_tenant_pk
from app.domain.repositories.order_repository import OrderPanelItem, OrderRepository


def _open_dict_conn():
    """Open a Postgres connection that returns dict rows."""
    from psycopg.rows import dict_row  # type: ignore[import-not-found]

    conn = open_postgres_connection()
    conn.row_factory = dict_row
    return conn


class PostgresOrderRepository(OrderRepository):
    def list_for_main_panel(
        self, *, tenant_id: str | None = None
    ) -> list[OrderPanelItem]:
        tenant_pk = resolve_tenant_pk(tenant_id)
        with _open_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        e.id,
                        COALESCE(c.nome, '~') AS cliente_nome,
                        e.produto,
                        e.categoria,
                        e.data_entrega,
                        e.horario,
                        e.valor_total,
                        COALESCE(d.status, 'pendente') AS status,
                        COALESCE(d.tipo, 'entrega') AS tipo,
                        e.criado_em
                    FROM encomendas e
                    LEFT JOIN clientes c
                        ON e.cliente_id = c.id AND c.tenant_id = e.tenant_id
                    LEFT JOIN entregas d
                        ON d.encomenda_id = e.id AND d.tenant_id = e.tenant_id
                    WHERE e.tenant_id = %s
                    ORDER BY e.id DESC
                    """,
                    (tenant_pk,),
                )
                rows = cur.fetchall()
        return [
            OrderPanelItem(
                id=row["id"],
                cliente_nome=row["cliente_nome"],
                produto=row["produto"],
                categoria=row["categoria"],
                data_entrega=row["data_entrega"],
                horario=row["horario"],
                valor_total=row["valor_total"],
                status=row["status"],
                tipo=row["tipo"],
                criado_em=row["criado_em"].isoformat() if hasattr(row["criado_em"], "isoformat") else row["criado_em"],
            )
            for row in rows
        ]

    def list_for_orders_page(self, *, tenant_id: str | None = None) -> list[tuple]:
        tenant_pk = resolve_tenant_pk(tenant_id)
        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        e.id,
                        c.nome AS cliente_nome,
                        c.telefone AS cliente_telefone,
                        e.categoria,
                        e.massa,
                        e.recheio,
                        e.mousse,
                        e.adicional,
                        e.tamanho,
                        CASE WHEN e.categoria = 'gourmet' THEN 'sim' ELSE 'nao' END AS gourmet,
                        COALESCE(d.tipo, CASE WHEN e.categoria = 'pronta_entrega'
                                              THEN 'pronta entrega' END) AS entrega,
                        e.criado_em,
                        COALESCE(d.status, 'pendente') AS status,
                        e.produto,
                        e.data_entrega,
                        e.valor_total
                    FROM encomendas e
                    JOIN clientes c
                        ON e.cliente_id = c.id AND c.tenant_id = e.tenant_id
                    LEFT JOIN entregas d
                        ON d.encomenda_id = e.id AND d.tenant_id = e.tenant_id
                    WHERE e.tenant_id = %s
                    ORDER BY e.id DESC
                    """,
                    (tenant_pk,),
                )
                return list(cur.fetchall())

    def export_rows(self, *, tenant_id: str | None = None) -> list[tuple]:
        tenant_pk = resolve_tenant_pk(tenant_id)
        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        c.nome AS cliente,
                        e.produto,
                        e.data_entrega,
                        e.valor_total,
                        COALESCE(d.status, 'pendente') AS status
                    FROM encomendas e
                    JOIN clientes c
                        ON e.cliente_id = c.id AND c.tenant_id = e.tenant_id
                    LEFT JOIN entregas d
                        ON d.encomenda_id = e.id AND d.tenant_id = e.tenant_id
                    WHERE e.tenant_id = %s
                    ORDER BY e.id DESC
                    """,
                    (tenant_pk,),
                )
                return list(cur.fetchall())

    def create_order(
        self,
        *,
        nome: str,
        telefone: str,
        categoria: str,
        produto: str,
        tamanho: str,
        massa: str | None = None,
        recheio: str | None = None,
        mousse: str | None = None,
        adicional: str | None = None,
        horario: str | None = None,
        valor_total: str,
        data_entrega: str,
        tenant_id: str | None = None,
    ) -> int:
        tenant_pk = resolve_tenant_pk(tenant_id)
        valor = 0.0
        if valor_total:
            bruto = str(valor_total).strip().replace("R$", "").replace(" ", "")
            if "," in bruto:
                bruto = bruto.replace(".", "").replace(",", ".")
            valor = float(bruto)

        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM clientes WHERE telefone = %s AND tenant_id = %s",
                    (telefone, tenant_pk),
                )
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        "INSERT INTO clientes (nome, telefone, tenant_id) "
                        "VALUES (%s, %s, %s) RETURNING id",
                        (nome, telefone, tenant_pk),
                    )
                    cliente_id = cur.fetchone()[0]
                else:
                    cliente_id = row[0]

                cur.execute(
                    """
                    INSERT INTO encomendas (
                        cliente_id, categoria, produto, tamanho, massa,
                        recheio, mousse, adicional, data_entrega, horario,
                        valor_total, tenant_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        cliente_id, categoria, produto, tamanho, massa,
                        recheio, mousse, adicional, data_entrega, horario,
                        valor, tenant_pk,
                    ),
                )
                return int(cur.fetchone()[0])

    def delete_order(self, order_id: int, *, tenant_id: str | None = None) -> None:
        tenant_pk = resolve_tenant_pk(tenant_id)
        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM encomenda_doces "
                    "WHERE encomenda_id = %s AND tenant_id = %s",
                    (order_id, tenant_pk),
                )
                cur.execute(
                    "DELETE FROM entregas "
                    "WHERE encomenda_id = %s AND tenant_id = %s",
                    (order_id, tenant_pk),
                )
                cur.execute(
                    "UPDATE customer_processes "
                    "SET order_id = NULL, updated_at = NOW() "
                    "WHERE order_id = %s AND tenant_id = %s",
                    (order_id, tenant_pk),
                )
                cur.execute(
                    "DELETE FROM encomendas "
                    "WHERE id = %s AND tenant_id = %s",
                    (order_id, tenant_pk),
                )

    def get_order_details(
        self, order_id: int, *, tenant_id: str | None = None
    ) -> dict | None:
        tenant_pk = resolve_tenant_pk(tenant_id)
        with _open_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        e.*,
                        COALESCE(c.nome, '~') AS cliente_nome,
                        COALESCE(d.status, 'pendente') AS status
                    FROM encomendas e
                    LEFT JOIN clientes c
                        ON c.id = e.cliente_id AND c.tenant_id = e.tenant_id
                    LEFT JOIN entregas d
                        ON d.encomenda_id = e.id AND d.tenant_id = e.tenant_id
                    WHERE e.id = %s AND e.tenant_id = %s
                    """,
                    (order_id, tenant_pk),
                )
                return cur.fetchone()

    def list_by_phone(
        self, phone: str, *, limit: int = 10, tenant_id: str | None = None
    ) -> list[dict]:
        tenant_pk = resolve_tenant_pk(tenant_id)
        with _open_dict_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        e.id, e.categoria, e.produto, e.tamanho,
                        e.data_entrega, e.horario, e.valor_total, e.criado_em,
                        COALESCE(d.status, 'pendente') AS status,
                        COALESCE(d.tipo, 'entrega') AS tipo
                    FROM encomendas e
                    INNER JOIN clientes c
                        ON c.id = e.cliente_id AND c.tenant_id = e.tenant_id
                    LEFT JOIN entregas d
                        ON d.encomenda_id = e.id AND d.tenant_id = e.tenant_id
                    WHERE c.telefone = %s AND e.tenant_id = %s
                    ORDER BY e.id DESC
                    LIMIT %s
                    """,
                    (phone, tenant_pk, int(limit)),
                )
                return list(cur.fetchall())

    def upsert_delivery_status(
        self, order_id: int, status: str, *, tenant_id: str | None = None
    ) -> None:
        tenant_pk = resolve_tenant_pk(tenant_id)
        with open_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE entregas SET status = %s "
                    "WHERE encomenda_id = %s AND tenant_id = %s",
                    (status, order_id, tenant_pk),
                )
                if cur.rowcount == 0:
                    cur.execute(
                        "INSERT INTO entregas (encomenda_id, status, tipo, tenant_id) "
                        "VALUES (%s, %s, 'entrega', %s)",
                        (order_id, status, tenant_pk),
                    )
