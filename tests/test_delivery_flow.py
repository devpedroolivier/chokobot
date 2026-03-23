import os
import unittest
from unittest.mock import AsyncMock

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.application.use_cases.process_delivery_flow import ProcessDeliveryFlow


class DeliveryFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_confirm_entrega_persists_order_only_after_final_confirmation(self):
        responder = AsyncMock(return_value=True)
        order_calls = []
        delivery_calls = []
        process_calls = []

        class _OrderGateway:
            def create_order(self, **kwargs):
                order_calls.append(kwargs)
                return 321

        class _DeliveryGateway:
            def create_delivery(self, **kwargs):
                delivery_calls.append(kwargs)

        class _ProcessRepository:
            def upsert_process(self, **kwargs):
                process_calls.append(kwargs)
                return 1

        state = {
            "etapa": 1,
            "nome": "Cliente Teste",
            "cliente_id": 7,
            "dados": {
                "data": "2026-03-25",
                "pedido": {
                    "categoria": "tradicional",
                    "data_entrega": "2026-03-25",
                    "horario_retirada": "14:00",
                    "valor_total": 130.0,
                    "taxa_entrega": 10.0,
                    "pagamento": {"forma": "PIX", "troco_para": None},
                },
            },
        }

        flow = ProcessDeliveryFlow(
            responder_usuario_fn=responder,
            order_gateway=_OrderGateway(),
            delivery_gateway=_DeliveryGateway(),
            customer_process_repository=_ProcessRepository(),
        )

        result = await flow.execute("5511999999999", "Rua Teste, 123", state)
        self.assertIsNone(result)
        self.assertEqual(state["etapa"], 2)
        self.assertEqual(order_calls, [])
        self.assertEqual(delivery_calls, [])

        result = await flow.execute("5511999999999", "Portao azul", state)
        self.assertIsNone(result)
        self.assertEqual(state["etapa"], "confirmar_entrega")
        self.assertEqual(order_calls, [])
        self.assertEqual(delivery_calls, [])
        self.assertEqual(process_calls[-1]["stage"], "aguardando_confirmacao")

        result = await flow.execute("5511999999999", "1", state)
        self.assertEqual(result, "finalizar")
        self.assertEqual(len(order_calls), 1)
        self.assertEqual(order_calls[0]["phone"], "5511999999999")
        self.assertEqual(order_calls[0]["cliente_id"], 7)
        self.assertEqual(order_calls[0]["dados"]["endereco"], "Rua Teste, 123")
        self.assertEqual(order_calls[0]["dados"]["referencia"], "Portao azul")
        self.assertEqual(len(delivery_calls), 1)
        self.assertEqual(delivery_calls[0]["encomenda_id"], 321)
        self.assertIn("Rua Teste, 123", delivery_calls[0]["endereco"])
        self.assertEqual(process_calls[-1]["status"], "converted")
        self.assertEqual(process_calls[-1]["order_id"], 321)
