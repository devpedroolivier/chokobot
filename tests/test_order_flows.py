import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.db.database import get_connection
from app.db.init_db import ensure_views
from app.models import criar_tabelas
from app.application.use_cases.process_cafeteria_flow import process_cafeteria_flow
from app.application.use_cases.process_cesta_box_flow import process_cesta_box_flow, salvar_pedido_cesta
from app.infrastructure.gateways.local_delivery_gateway import LocalDeliveryGateway
from app.infrastructure.repositories.sqlite_order_write_repository import SQLiteOrderWriteRepository


class OrderFlowsTests(unittest.IsolatedAsyncioTestCase):
    async def test_process_cafeteria_flow_finalizes_order_via_gateway(self):
        responder = AsyncMock(return_value=True)
        order_gateway = SimpleNamespace(save_cafeteria_order=lambda **kwargs: self.calls.append(kwargs))
        process_calls = []
        process_repository = SimpleNamespace(upsert_process=lambda **kwargs: process_calls.append(kwargs) or 1)
        self.calls = []

        estado = {"nome": "Cliente Cafe", "itens": ["cafe", "bolo"]}
        result = await process_cafeteria_flow(
            "5511888888888",
            "finalizar",
            estado,
            responder_usuario_fn=responder,
            order_gateway=order_gateway,
            customer_process_repository=process_repository,
        )

        self.assertEqual(result, "finalizar")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0]["nome_cliente"], "Cliente Cafe")
        self.assertEqual(process_calls[-1]["process_type"], "cafeteria_order")
        self.assertEqual(process_calls[-1]["status"], "converted")
        responder.assert_awaited_once()

    async def test_process_cesta_box_flow_blocks_delivery_after_cutoff(self):
        responder = AsyncMock(return_value=True)
        estado = {
            "etapa": "modo_recebimento",
            "dados": {"horario_retirada": "20:30"},
        }

        result = await process_cesta_box_flow(
            "5511999999999",
            "2",
            estado,
            "Cliente Box",
            10,
            responder_usuario_fn=responder,
        )

        self.assertIsNone(result)
        self.assertEqual(estado["etapa"], "hora_retirada")
        responder.assert_awaited_once()
        self.assertIn("entregas são realizadas até", responder.await_args.args[1].lower())

    async def test_process_cesta_box_flow_blocks_sunday_date(self):
        responder = AsyncMock(return_value=True)
        estado = {"etapa": "data_entrega", "dados": {}}

        result = await process_cesta_box_flow(
            "5511999999999",
            "29/03/2026",
            estado,
            "Cliente Box",
            10,
            responder_usuario_fn=responder,
        )

        self.assertIsNone(result)
        self.assertEqual(estado["etapa"], "data_entrega")
        responder.assert_awaited_once()
        self.assertIn("domingo", responder.await_args.args[1].lower())

    async def test_salvar_pedido_cesta_dispatches_order_and_delivery(self):
        responder = AsyncMock(return_value=True)
        order_calls = []
        delivery_calls = []
        process_calls = []

        class _OrderGateway:
            def create_order(self, **kwargs):
                order_calls.append(kwargs)
                return 42

        class _DeliveryGateway:
            def create_delivery(self, **kwargs):
                delivery_calls.append(kwargs)

        class _ProcessRepository:
            def upsert_process(self, **kwargs):
                process_calls.append(kwargs)
                return 1

        dados = {
            "cesta_nome": "BOX M CAFÉ",
            "cesta_preco": 179.90,
            "cesta_descricao": "Cafe da manha",
            "data_entrega": "20/03/2026",
            "horario_retirada": "10:00",
            "modo_recebimento": "entrega",
            "endereco": "Rua Teste, 123",
            "taxa_entrega": 10.0,
            "pagamento": {"forma": "PIX"},
        }

        await salvar_pedido_cesta(
            "5511777777777",
            {"etapa": "finalizar_venda"},
            dados,
            "Cliente Box",
            7,
            responder_usuario_fn=responder,
            order_gateway=_OrderGateway(),
            delivery_gateway=_DeliveryGateway(),
            customer_process_repository=_ProcessRepository(),
        )

        self.assertEqual(order_calls[0]["cliente_id"], 7)
        self.assertEqual(order_calls[0]["dados"]["categoria"], "cesta_box")
        self.assertEqual(delivery_calls[0]["encomenda_id"], 42)
        self.assertEqual(process_calls[-1]["process_type"], "cesta_box_order")
        self.assertEqual(process_calls[-1]["status"], "converted")
        responder.assert_awaited()

    async def test_local_delivery_gateway_persists_delivery_record(self):
        gateway = LocalDeliveryGateway()

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "chokobot.db")
            previous_db_path = os.environ.get("DB_PATH")
            os.environ["DB_PATH"] = db_path
            try:
                criar_tabelas()
                ensure_views()
                conn = get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO clientes (nome, telefone) VALUES (?, ?)", ("Cliente", "5511666666666"))
                    cliente_id = cur.lastrowid
                    conn.commit()
                finally:
                    conn.close()

                encomenda_id = SQLiteOrderWriteRepository().save_order_payload(
                    phone="5511666666666",
                    nome_cliente="Cliente",
                    cliente_id=cliente_id,
                    dados={
                        "categoria": "tradicional",
                        "linha": "tradicional",
                        "massa": "Chocolate",
                        "recheio": "Brigadeiro",
                        "mousse": "Ninho",
                        "tamanho": "B3",
                        "data_entrega": "20/03/2026",
                        "horario_retirada": "14:00",
                        "descricao": "Bolo teste",
                        "valor_total": 120.0,
                        "pagamento": {"forma": "PIX"},
                    },
                )

                gateway.create_delivery(
                    encomenda_id=encomenda_id,
                    tipo="entrega",
                    endereco="Rua Teste, 123",
                    data_agendada="2026-03-20",
                    status="pendente",
                )

                conn = get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        SELECT encomenda_id, tipo, endereco, status
                        FROM entregas
                        WHERE encomenda_id = ?
                        """,
                        (encomenda_id,),
                    )
                    entrega = cur.fetchone()
                finally:
                    conn.close()
            finally:
                if previous_db_path is None:
                    os.environ.pop("DB_PATH", None)
                else:
                    os.environ["DB_PATH"] = previous_db_path

        self.assertIsNotNone(entrega)
        self.assertEqual(entrega["tipo"], "entrega")
        self.assertEqual(entrega["endereco"], "Rua Teste, 123")
        self.assertEqual(entrega["status"], "pendente")


if __name__ == "__main__":
    unittest.main()
