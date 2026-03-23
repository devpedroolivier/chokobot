import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.models import criar_tabelas
from app.db.init_db import ensure_views
from app.db.database import get_connection
from app.infrastructure.gateways.local_order_gateway import LocalOrderGateway
from app.infrastructure.repositories.sqlite_order_write_repository import SQLiteOrderWriteRepository
from app.infrastructure.repositories.sqlite_delivery_write_repository import SQLiteDeliveryWriteRepository


class OrderWriteRepositoryTests(unittest.TestCase):
    def test_save_order_payload_creates_customer_and_order(self):
        repository = SQLiteOrderWriteRepository()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "chokobot.db")
            with patch.dict(os.environ, {"DB_PATH": db_path}, clear=False):
                criar_tabelas()
                ensure_views()

                order_id = repository.save_order_payload(
                    phone="5511999999999",
                    nome_cliente="Cliente Teste",
                    cliente_id=None,
                    dados={
                        "categoria": "tradicional",
                        "linha": "tradicional",
                        "massa": "Chocolate",
                        "recheio": "Brigadeiro",
                        "mousse": "Ninho",
                        "tamanho": "B3",
                        "data_entrega": "08/03/2026",
                        "horario_retirada": "14:00",
                        "descricao": "Bolo tradicional",
                        "valor_total": 120.0,
                        "pagamento": {"forma": "PIX"},
                    },
                )

                conn = get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT nome FROM clientes WHERE telefone = ?", ("5511999999999",))
                    cliente = cur.fetchone()
                    cur.execute("SELECT categoria, tamanho, valor_total FROM encomendas WHERE id = ?", (order_id,))
                    encomenda = cur.fetchone()
                finally:
                    conn.close()

        self.assertGreater(order_id, 0)
        self.assertEqual(cliente["nome"], "Cliente Teste")
        self.assertEqual(encomenda["categoria"], "tradicional")
        self.assertEqual(encomenda["tamanho"], "B3")
        self.assertEqual(float(encomenda["valor_total"]), 120.0)

    def test_local_order_gateway_saves_cafeteria_order(self):
        gateway = LocalOrderGateway()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "chokobot.db")
            with patch.dict(os.environ, {"DB_PATH": db_path}, clear=False):
                criar_tabelas()
                ensure_views()

                gateway.save_cafeteria_order(
                    phone="5511888888888",
                    itens=["cafe", "bolo"],
                    nome_cliente="Cliente Cafe",
                )

                conn = get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        SELECT p.pedido, c.nome
                        FROM pedidos_cafeteria p
                        JOIN clientes c ON c.id = p.cliente_id
                        WHERE c.telefone = ?
                        """,
                        ("5511888888888",),
                    )
                    pedido = cur.fetchone()
                finally:
                    conn.close()

        self.assertIsNotNone(pedido)
        self.assertEqual(pedido["nome"], "Cliente Cafe")
        self.assertIn("cafe", pedido["pedido"])
        self.assertIn("bolo", pedido["pedido"])

    def test_save_order_payload_fails_fast_on_incompatible_schema(self):
        repository = SQLiteOrderWriteRepository()
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                telefone TEXT NOT NULL
            );
            CREATE TABLE encomendas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER NOT NULL,
                produto TEXT,
                data_entrega TEXT
            );
            """
        )

        with patch("app.infrastructure.repositories.sqlite_order_write_repository.get_connection", return_value=conn):
            order_id = repository.save_order_payload(
                phone="5511999999999",
                nome_cliente="Cliente Teste",
                cliente_id=None,
                dados={
                    "categoria": "tradicional",
                    "linha": "tradicional",
                    "massa": "Chocolate",
                    "recheio": "Brigadeiro",
                    "mousse": "Ninho",
                    "tamanho": "B3",
                    "data_entrega": "08/03/2026",
                    "horario_retirada": "14:00",
                    "descricao": "Bolo tradicional",
                    "valor_total": 120.0,
                    "pagamento": {"forma": "PIX"},
                },
            )

        self.assertEqual(order_id, -1)

    def test_save_delivery_raises_on_incompatible_schema(self):
        repository = SQLiteDeliveryWriteRepository()
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE entregas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                encomenda_id INTEGER NOT NULL,
                status TEXT
            );
            """
        )

        with patch("app.infrastructure.repositories.sqlite_delivery_write_repository.get_connection", return_value=conn):
            with self.assertRaises(sqlite3.OperationalError):
                repository.save_delivery(
                    encomenda_id=1,
                    tipo="entrega",
                    endereco="Rua Teste, 123",
                    data_agendada="2026-03-20",
                    status="pendente",
                )


if __name__ == "__main__":
    unittest.main()
