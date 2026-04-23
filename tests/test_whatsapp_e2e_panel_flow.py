import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.api.routes.painel import painel_snapshot
from app.application.use_cases.process_delivery_flow import ProcessDeliveryFlow
from app.application.use_cases.process_inbound_message import process_inbound_message
from app.infrastructure.gateways.local_delivery_gateway import LocalDeliveryGateway
from app.infrastructure.gateways.local_order_gateway import LocalOrderGateway
from app.infrastructure.repositories.sqlite_customer_process_repository import SQLiteCustomerProcessRepository
from app.infrastructure.repositories.sqlite_customer_repository import SQLiteCustomerRepository
from app.infrastructure.repositories.sqlite_order_repository import SQLiteOrderRepository
from app.models import criar_tabelas
from app.db.init_db import ensure_views
from app.services.estados import (
    ai_sessions,
    clear_runtime_state,
    estados_atendimento,
    estados_cafeteria,
    estados_cestas_box,
    estados_encomenda,
    estados_entrega,
    recent_messages,
    set_bot_ativo,
)


class _EventBusStub:
    def __init__(self):
        self.events = []

    def publish(self, event) -> None:
        self.events.append(event)


class WhatsAppE2EPanelFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        clear_runtime_state()
        set_bot_ativo(True)
        for state_map in (
            estados_atendimento,
            estados_encomenda,
            estados_cafeteria,
            estados_entrega,
            estados_cestas_box,
            ai_sessions,
            recent_messages,
        ):
            state_map.clear()

    async def test_contact_to_confirmation_moves_from_whatsapp_flow_to_panel_order(self):
        phone = "5511999999999"
        event_bus = _EventBusStub()

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "e2e.db")
            with patch.dict(
                os.environ,
                {
                    "DB_PATH": db_path,
                    "OUTBOX_EVENTS_PATH": os.path.join(temp_dir, "domain_events.jsonl"),
                },
                clear=False,
            ):
                criar_tabelas()
                ensure_views()

                customer_repository = SQLiteCustomerRepository()
                process_repository = SQLiteCustomerProcessRepository()
                order_repository = SQLiteOrderRepository()

                with (
                    patch("app.application.use_cases.process_inbound_message.get_event_bus", return_value=event_bus),
                    patch("app.application.use_cases.persist_order_payload.get_event_bus", return_value=event_bus),
                ):
                    responder = AsyncMock(return_value=True)

                    await process_inbound_message(
                        {
                            "phone": phone,
                            "chatName": "Ana",
                            "message": "Oi, quero um bolo com entrega",
                            "id": "msg-1",
                            "type": "text",
                        },
                        responder_usuario_fn=responder,
                        gerar_resposta_ia_fn=AsyncMock(return_value="Posso ajudar com o seu pedido."),
                        save_customer_fn=lambda telefone, nome: customer_repository.upsert_customer(nome, telefone),
                    )

                    customer = customer_repository.get_customer_by_phone(phone)
                    self.assertIsNotNone(customer)
                    self.assertEqual(customer.nome, "Ana")

                    state = {
                        "etapa": 1,
                        "nome": "Ana",
                        "cliente_id": customer.id,
                        "dados": {
                            "data": "2026-03-25",
                            "pedido": {
                                "categoria": "tradicional",
                                "produto": "Bolo de chocolate",
                                "descricao": "Bolo de chocolate",
                                "data_entrega": "2026-03-25",
                                "horario_retirada": "14:00",
                                "valor_total": 130.0,
                                "taxa_entrega": 10.0,
                                "pagamento": {"forma": "PIX"},
                            },
                        },
                    }

                    flow = ProcessDeliveryFlow(
                        responder_usuario_fn=responder,
                        order_gateway=LocalOrderGateway(),
                        delivery_gateway=LocalDeliveryGateway(),
                        customer_process_repository=process_repository,
                    )

                    await flow.execute(phone, "Rua Teste, 123", state)
                    await flow.execute(phone, "Portão azul", state)

                    response_before = painel_snapshot(
                        repository=order_repository,
                        customer_repository=customer_repository,
                        process_repository=process_repository,
                    )
                    payload_before = json.loads(response_before.body)

                    self.assertEqual(payload_before["dashboard"]["operational_orders"], [])
                    self.assertTrue(
                        any(card["phone"] == phone for card in payload_before["whatsapp_cards"])
                    )
                    self.assertTrue(
                        any(
                            card["phone"] == phone
                            for section in payload_before["process_sections"]
                            for card in section["cards"]
                        )
                    )

                    whatsapp_card = next(
                        card for card in payload_before["whatsapp_cards"] if card["phone"] == phone
                    )
                    self.assertEqual(whatsapp_card["cliente_nome"], "Ana")
                    self.assertEqual(whatsapp_card["stage_label"], "Entrega / endereço")
                    self.assertIn("oi, quero um bolo com entrega", whatsapp_card["last_message"])

                    result = await flow.execute(phone, "confirmo", state)
                    self.assertEqual(result, "finalizar")

                process = process_repository.get_process(phone, "delivery_order")
                self.assertIsNotNone(process)
                self.assertEqual(process.status, "converted")
                self.assertEqual(process.stage, "pedido_confirmado")
                self.assertIsNotNone(process.order_id)

                response_after = painel_snapshot(
                    repository=order_repository,
                    customer_repository=customer_repository,
                    process_repository=process_repository,
                )
                payload_after = json.loads(response_after.body)

                # Depois da conversao o processo sai do board, mas a conversa
                # segue visivel no inbox (origem conversation_only) para que o
                # painel mantenha historico das mensagens trocadas.
                whatsapp_cards_after = payload_after["whatsapp_cards"]
                conversation_card = next(
                    (card for card in whatsapp_cards_after if card["phone"] == phone),
                    None,
                )
                self.assertIsNotNone(conversation_card)
                self.assertEqual(conversation_card["stage_label"], "Conversa aberta")
                self.assertFalse(
                    any(
                        card["phone"] == phone
                        for section in payload_after["process_sections"]
                        for card in section["cards"]
                    )
                )
                self.assertEqual(len(payload_after["dashboard"]["operational_orders"]), 1)
                self.assertEqual(payload_after["dashboard"]["operational_orders"][0]["cliente_nome"], "Ana")
                self.assertEqual(payload_after["dashboard"]["operational_orders"][0]["id"], process.order_id)
                self.assertTrue(
                    any(
                        item["id"] == process.order_id
                        for column in payload_after["dashboard"]["kanban_columns"]
                        for item in column["items"]
                    )
                )


if __name__ == "__main__":
    unittest.main()
