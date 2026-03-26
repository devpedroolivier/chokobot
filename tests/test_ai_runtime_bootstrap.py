import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.ai import runner


class AIRuntimeBootstrapTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        runner.CONVERSATIONS.clear()
        runner.reset_ai_client()

    def tearDown(self):
        runner.CONVERSATIONS.clear()
        runner.reset_ai_client()

    def test_build_ai_client_returns_none_without_api_key(self):
        with patch.object(runner, "AsyncOpenAI", object()):
            client = runner.build_ai_client(api_key="")

        self.assertIsNone(client)

    def test_get_ai_client_initializes_once(self):
        fake_client = object()

        with patch.object(runner, "build_ai_client", return_value=fake_client) as mocked_build:
            first = runner.get_ai_client()
            second = runner.get_ai_client()

        self.assertIs(first, fake_client)
        self.assertIs(second, fake_client)
        mocked_build.assert_called_once_with()

    async def test_process_message_with_ai_uses_runtime_injection(self):
        create_mock = AsyncMock(
            side_effect=[
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content=None,
                                tool_calls=[
                                    SimpleNamespace(
                                        id="tool-1",
                                        function=SimpleNamespace(
                                            name="get_menu",
                                            arguments='{"category": "pronta_entrega"}',
                                        ),
                                    )
                                ],
                            )
                        )
                    ],
                    usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
                ),
                SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="Resposta final", tool_calls=[]))],
                    usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
                ),
            ]
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )
        runtime = runner.AIRuntime(
            get_menu=lambda category="todas": f"menu:{category}",
            get_cake_options=lambda category="tradicional", option_type="recheio": f"cake-options:{category}:{option_type}",
            get_learnings=lambda: "regra de teste",
            save_learning=lambda aprendizado: f"saved:{aprendizado}",
            escalate_to_human=lambda telefone, motivo: "ok",
            create_cake_order=lambda telefone, nome_cliente, cliente_id, order: "pedido",
            create_sweet_order=lambda telefone, nome_cliente, cliente_id, order: "doces",
        )

        reply = await runner.process_message_with_ai(
            "5511999999999",
            "Oi",
            "Teste",
            1,
            ai_client=fake_client,
            runtime=runtime,
        )

        self.assertEqual(reply, "Resposta final")
        first_messages = create_mock.await_args_list[0].kwargs["messages"]
        self.assertIn("REGRAS APRENDIDAS ANTERIORMENTE:\nregra de teste", first_messages[0]["content"])
        self.assertEqual(first_messages[1]["content"], "Oi")
        second_messages = create_mock.await_args_list[1].kwargs["messages"]
        tool_messages = [message for message in second_messages if message["role"] == "tool"]
        self.assertTrue(tool_messages)
        self.assertEqual(tool_messages[-1]["content"], "menu:pronta_entrega")

    async def test_process_message_with_ai_repairs_dangling_tool_call_history(self):
        create_mock = AsyncMock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="Olá! Como posso te ajudar?", tool_calls=[]))],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            )
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )

        runner.CONVERSATIONS["5511999999999"] = {
            "current_agent": "CafeteriaAgent",
            "messages": [
                {"role": "system", "content": "prompt antigo"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "tool-1",
                            "type": "function",
                            "function": {"name": "transfer_to_agent", "arguments": '{"agent_name":"CafeteriaAgent"}'},
                        }
                    ],
                },
            ],
        }

        reply = await runner.process_message_with_ai(
            "5511999999999",
            "oi",
            "Teste",
            1,
            ai_client=fake_client,
            runtime=runner.AIRuntime(
                get_menu=lambda category="todas": "menu",
                get_cake_options=lambda category="tradicional", option_type="recheio": "cake-options",
                get_learnings=lambda: "",
                save_learning=lambda aprendizado: aprendizado,
                escalate_to_human=lambda telefone, motivo: "ok",
                create_cake_order=lambda telefone, nome_cliente, cliente_id, order: "pedido",
                create_sweet_order=lambda telefone, nome_cliente, cliente_id, order: "doces",
            ),
        )

        self.assertEqual(reply, "Olá! Como posso te ajudar?")
        messages = create_mock.await_args.kwargs["messages"]
        self.assertEqual([message["role"] for message in messages], ["system", "user"])
        self.assertEqual(messages[1]["content"], "oi")

    async def test_process_message_with_ai_prompts_caseirinho_clarification_before_ai(self):
        telefone = "5511888888888"
        runtime = runner.AIRuntime(
            get_menu=lambda category="todas": "menu",
            get_cake_options=lambda category="tradicional", option_type="recheio": "cake-options",
            get_learnings=lambda: "",
            save_learning=lambda aprendizado: aprendizado,
            escalate_to_human=lambda telefone, motivo: "ok",
            create_cake_order=lambda telefone, nome_cliente, cliente_id, order: "pedido",
            create_sweet_order=lambda telefone, nome_cliente, cliente_id, order: "doces",
        )

        with patch.object(runner, "request_ai_completion", AsyncMock()) as mocked_completion:
            reply = await runner.process_message_with_ai(
                telefone,
                "quero caseirinho",
                "Cliente Teste",
                1,
                ai_client=object(),
                runtime=runtime,
            )

        self.assertIn("sabor", reply.lower())
        self.assertIn("cobertura", reply.lower())
        self.assertEqual(runner.CONVERSATIONS[telefone]["current_agent"], "CakeOrderAgent")
        mocked_completion.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
