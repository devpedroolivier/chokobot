from __future__ import annotations

from app.db.database import get_connection
from app.domain.repositories.order_repository import OrderPanelItem, OrderRepository


class SQLiteOrderRepository(OrderRepository):
    def list_for_main_panel(self) -> list[OrderPanelItem]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
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
                LEFT JOIN clientes c ON e.cliente_id = c.id
                LEFT JOIN entregas d ON d.encomenda_id = e.id
                ORDER BY e.id DESC
                """
            )
            rows = cursor.fetchall()
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
                    criado_em=row["criado_em"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def list_for_orders_page(self) -> list[tuple]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
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
                    COALESCE(d.tipo, CASE WHEN e.categoria = 'pronta_entrega' THEN 'pronta entrega' END) AS entrega,
                    e.criado_em,
                    COALESCE(d.status, 'pendente') AS status
                FROM encomendas e
                JOIN clientes c ON e.cliente_id = c.id
                LEFT JOIN entregas d ON d.encomenda_id = e.id
                ORDER BY e.id DESC
                """
            )
            return cursor.fetchall()
        finally:
            conn.close()

    def export_rows(self) -> list[tuple]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    c.nome AS cliente,
                    e.produto,
                    e.data_entrega,
                    e.valor_total,
                    COALESCE(d.status, 'pendente') AS status
                FROM encomendas e
                JOIN clientes c ON e.cliente_id = c.id
                LEFT JOIN entregas d ON d.encomenda_id = e.id
                ORDER BY e.id DESC
                """
            )
            return cursor.fetchall()
        finally:
            conn.close()

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
    ) -> int:
        conn = get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM clientes WHERE telefone = ?", (telefone,))
            cliente = cursor.fetchone()
            if not cliente:
                cursor.execute(
                    "INSERT INTO clientes (nome, telefone) VALUES (?, ?)",
                    (nome, telefone),
                )
                cliente_id = cursor.lastrowid
            else:
                cliente_id = cliente["id"]

            valor = 0.0
            if valor_total:
                bruto = str(valor_total).strip().replace("R$", "").replace(" ", "")
                if "," in bruto:
                    bruto = bruto.replace(".", "").replace(",", ".")
                valor = float(bruto)

            cursor.execute(
                """
                INSERT INTO encomendas (
                    cliente_id, categoria, produto, tamanho, massa, recheio, mousse, adicional,
                    data_entrega, horario, valor_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cliente_id,
                    categoria,
                    produto,
                    tamanho,
                    massa,
                    recheio,
                    mousse,
                    adicional,
                    data_entrega,
                    horario,
                    valor,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def delete_order(self, order_id: int) -> None:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM encomendas WHERE id = ?", (order_id,))
            conn.commit()
        finally:
            conn.close()

    def get_order_details(self, order_id: int) -> dict | None:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    e.*,
                    COALESCE(c.nome, '~') AS cliente_nome,
                    COALESCE(d.status, 'pendente') AS status
                FROM encomendas e
                LEFT JOIN clientes c ON c.id = e.cliente_id
                LEFT JOIN entregas d ON d.encomenda_id = e.id
                WHERE e.id = ?
                """,
                (order_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return dict(row)
        finally:
            conn.close()

    def upsert_delivery_status(self, order_id: int, status: str) -> None:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE entregas SET status = ? WHERE encomenda_id = ?",
                (status, order_id),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "INSERT INTO entregas (encomenda_id, status, tipo) VALUES (?, ?, 'entrega')",
                    (order_id, status),
                )
            conn.commit()
        finally:
            conn.close()
