import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo
from datetime import datetime

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.ai import runner
from app.ai.policies import should_force_basic_context_switch
from app.ai.tool_execution import handle_tool_call
from app.observability import clear_metrics


def _message(content: str):
    return SimpleNamespace(content=content, tool_calls=[])


def _response(message):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


class Sprint5RegressionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        runner.CONVERSATIONS.clear()
        clear_metrics()

    def test_bolo_confirmation_flow_returns_protocol(self):
        session = {
            "messages": [{"role": "user", "content": "sim, pode confirmar"}],
            "current_agent": "CakeOrderAgent",
        }
        runtime = runner.AIRuntime(
            get_menu=lambda category="todas": "menu",
            get_cake_options=lambda category="tradicional", option_type="recheio": "cake-options",
            get_learnings=lambda: "",
            save_learning=lambda aprendizado: aprendizado,
            escalate_to_human=lambda telefone, motivo: "ok",
            create_cake_order=lambda telefone, nome_cliente, cliente_id, order: "Pedido salvo com sucesso! ID da Encomenda: 123",
            create_sweet_order=lambda telefone, nome_cliente, cliente_id, order: "doces",
        )

        should_return, tool_result = handle_tool_call(
            runtime=runtime,
            function_name="create_cake_order",
            arguments={
                "linha": "tradicional",
                "categoria": "tradicional",
                "descricao": "Bolo B3 de chocolate",
                "data_entrega": "10/10/2030",
                "horario_retirada": "15:00",
                "modo_recebimento": "retirada",
                "pagamento": {"forma": "PIX"},
                "massa": "Chocolate",
                "recheio": "Brigadeiro",
                "mousse": "Ninho",
                "tamanho": "B3",
            },
            telefone="5511999999999",
            nome_cliente="Cliente",
            cliente_id=1,
            session=session,
            save_session_fn=lambda telefone, state: None,
            now=datetime(2026, 3, 27, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo")),
        )

        self.assertTrue(should_return)
        self.assertIn("Protocolo: CHK-000123", tool_result)

    def test_cafeteria_combo_confirmation_flow_closes_order(self):
        session = {
            "messages": [{"role": "user", "content": "confirmo"}],
            "current_agent": "CafeteriaAgent",
        }
        runtime = runner.AIRuntime(
            get_menu=lambda category="todas": "menu",
            get_cake_options=lambda category="tradicional", option_type="recheio": "cake-options",
            get_learnings=lambda: "",
            save_learning=lambda aprendizado: aprendizado,
            escalate_to_human=lambda telefone, motivo: "ok",
            create_cake_order=lambda telefone, nome_cliente, cliente_id, order: "pedido",
            create_sweet_order=lambda telefone, nome_cliente, cliente_id, order: "doces",
            create_cafeteria_order=lambda telefone, nome_cliente, cliente_id, order: (
                "Pedido cafeteria salvo com sucesso!\n"
                "Itens: 2x Croissant (Peito de peru e provolone), 2x Refrigerante Lata\n"
                "Total final: R$42,00\n"
                "Protocolo: CAF-9999-1015"
            ),
        )

        should_return, tool_result = handle_tool_call(
            runtime=runtime,
            function_name="create_cafeteria_order",
            arguments={
                "itens": [
                    {"nome": "Croissant", "variante": "Peito de peru e provolone", "quantidade": 2},
                    {"nome": "Refrigerante Lata", "quantidade": 2},
                ],
                "modo_recebimento": "retirada",
                "pagamento": {"forma": "PIX"},
            },
            telefone="5511999999999",
            nome_cliente="Cliente",
            cliente_id=1,
            session=session,
            save_session_fn=lambda telefone, state: None,
            now=datetime(2026, 3, 27, 10, 15, tzinfo=ZoneInfo("America/Sao_Paulo")),
        )

        self.assertTrue(should_return)
        self.assertIn("Pedido Anotado✅️", tool_result)
        self.assertIn("Agradecemos a preferência 🥰", tool_result)
        self.assertIn("CAF-9999-1015", tool_result)

    def test_routing_for_easter_and_gift_topics(self):
        self.assertEqual(
            should_force_basic_context_switch({"current_agent": "TriageAgent"}, "Quero um ovo de páscoa"),
            "GiftOrderAgent",
        )
        self.assertEqual(
            should_force_basic_context_switch({"current_agent": "TriageAgent"}, "Vocês fazem cesta box com flores?"),
            "GiftOrderAgent",
        )

    async def test_context_is_kept_between_messages(self):
        create_mock = AsyncMock(
            side_effect=[
                _response(_message("Perfeito, me diga a data da retirada.")),
                _response(_message("Anotei: retiro amanhã às 17h.")),
            ]
        )
        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock)))

        first = await runner.process_message_with_ai(
            "5511888877777",
            "quero 10 brigadeiros",
            "Cliente",
            1,
            ai_client=fake_client,
        )
        second = await runner.process_message_with_ai(
            "5511888877777",
            "amanha as 17h",
            "Cliente",
            1,
            ai_client=fake_client,
        )

        self.assertIn("data", first.casefold())
        self.assertIn("anotei", second.casefold())
        second_messages = create_mock.await_args_list[1].kwargs["messages"]
        rendered = "\n".join(str(message.get("content") or "") for message in second_messages)
        self.assertIn("quero 10 brigadeiros", rendered)
        self.assertIn("Perfeito, me diga a data da retirada.", rendered)

    async def test_photo_request_returns_catalog_link_without_ai_call(self):
        fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock())))
        with patch.dict(os.environ, {"CATALOG_LINK": "https://catalogo.exemplo/fotos"}, clear=False):
            reply = await runner.process_message_with_ai(
                "5511777766666",
                "tem foto dos doces?",
                "Cliente",
                1,
                ai_client=fake_client,
            )

        self.assertIn("https://catalogo.exemplo/fotos", reply)
        fake_client.chat.completions.create.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
