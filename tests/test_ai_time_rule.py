import json
import os
import sys
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

os.environ.setdefault("OPENAI_API_KEY", "test-key")


class _AsyncOpenAIStub:
    def __init__(self, *args, **kwargs):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=None))


sys.modules.setdefault("openai", SimpleNamespace(AsyncOpenAI=_AsyncOpenAIStub))

from app.ai import runner
from app.ai.order_support import MockOrderSupportAdapter, OrderRecord, OrderSupportService
from app.ai.runner import POST_PURCHASE_MESSAGES
from app.observability import clear_metrics
from app.welcome_message import OPT_OUT_MESSAGE


def _tool_call(name: str, arguments: dict, tool_call_id: str = "tool-1"):
    return SimpleNamespace(
        id=tool_call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _message(content: str | None = None, tool_calls: list | None = None):
    return SimpleNamespace(content=content, tool_calls=tool_calls or [])


def _response(message, prompt_tokens: int = 10, completion_tokens: int = 5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
    )


class AIRunnerTimeRuleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        runner.CONVERSATIONS.clear()
        clear_metrics()

    def test_build_system_time_context_uses_provided_datetime(self):
        now = datetime(2026, 3, 7, 15, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))
        context = runner.build_system_time_context(now)
        self.assertIn("Hoje é 07/03/2026, e agora são 15:30.", context)
        self.assertIn("Horario oficial de Brasilia (America/Sao_Paulo).", context)
        self.assertIn("Status do corte das encomendas para hoje às 11:00: depois do limite.", context)
        self.assertIn("Status do corte das entregas às 17:30: antes do limite.", context)
        self.assertIn("Referencias rapidas de calendario:", context)
        self.assertIn("Calendario operacional especial:", context)
        self.assertIn("sabado = 07/03/2026", context)
        self.assertIn("sabado da semana que vem", context)

    async def test_process_message_injects_time_context_into_system_prompt(self):
        now = datetime(2026, 3, 7, 15, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))
        create_mock = AsyncMock(return_value=_response(_message("Resposta final")))
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                "5516999999999",
                "Oi, quero um bolo para hoje.",
                "Teste",
                99,
                now=now,
            )

        self.assertEqual(reply, "Resposta final")
        messages = create_mock.await_args.kwargs["messages"]
        self.assertIn("Hoje é 07/03/2026, e agora são 15:30.", messages[0]["content"])
        self.assertIn("Status do corte das encomendas para hoje às 11:00: depois do limite.", messages[0]["content"])
        self.assertIn("Status do corte das entregas às 17:30: antes do limite.", messages[0]["content"])
        self.assertIn("Referencias rapidas de calendario:", messages[0]["content"])
        self.assertIn("Calendario operacional especial:", messages[0]["content"])

    async def test_process_message_injects_service_date_memory_into_request(self):
        now = datetime(2026, 3, 24, 17, 23, tzinfo=ZoneInfo("America/Sao_Paulo"))
        create_mock = AsyncMock(return_value=_response(_message("Certo, seguimos com essa data.")))
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                "5516994646910",
                "Data de entrega: sábado",
                "Suzana",
                99,
                now=now,
            )

        self.assertEqual(reply, "Certo, seguimos com essa data.")
        messages = create_mock.await_args.kwargs["messages"]
        self.assertEqual(messages[-1]["role"], "system")
        self.assertIn("MEMORIA DE DATA DA CONVERSA", messages[-1]["content"])
        self.assertIn("28/03/2026 (Sabado)", messages[-1]["content"])

    async def test_process_message_injects_conversation_correction_memory_into_request(self):
        create_mock = AsyncMock(return_value=_response(_message("Perfeito, atualizei o pedido.")))
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                "5516992821034",
                "Entao vou retirar as 17:30 e pagar no cartao sem cereja",
                "Angela",
                99,
            )

        self.assertEqual(reply, "Perfeito, atualizei o pedido.")
        messages = create_mock.await_args.kwargs["messages"]
        self.assertEqual(messages[-1]["role"], "system")
        self.assertIn("MEMORIA DE CORRECOES DA CONVERSA", messages[-1]["content"])
        self.assertIn("modo de recebimento mais recente = retirada", messages[-1]["content"])
        self.assertIn("pagamento mais recente = Cartão (débito/crédito)", messages[-1]["content"])
        self.assertIn("horario mais recente = 17:30", messages[-1]["content"])
        self.assertIn("adicional removido = Cereja", messages[-1]["content"])

    async def test_process_message_updates_agent_after_handoff(self):
        now = datetime(2026, 3, 7, 15, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))
        create_mock = AsyncMock(
            side_effect=[
                _response(
                    _message(
                        tool_calls=[
                            _tool_call("transfer_to_agent", {"agent_name": "CafeteriaAgent"})
                        ]
                    )
                ),
                _response(_message("Temos bolos de pronta entrega e itens de cafeteria disponíveis hoje."))
            ]
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                "5516999999999",
                "Quero um bolo de mesversário pra hoje à tarde.",
                "Teste",
                99,
                now=now,
            )

        self.assertEqual(reply, "Temos bolos de pronta entrega e itens de cafeteria disponíveis hoje.")
        self.assertEqual(runner.CONVERSATIONS["5516999999999"]["current_agent"], "CafeteriaAgent")
        self.assertEqual(create_mock.await_count, 2)
        second_messages = create_mock.await_args_list[1].kwargs["messages"]
        tool_messages = [message for message in second_messages if message["role"] == "tool"]
        self.assertTrue(tool_messages)
        self.assertIn("Transferencia interna concluida para CafeteriaAgent", tool_messages[-1]["content"])

    async def test_process_message_retries_when_model_hallucinates_cutoff_before_1100(self):
        now = datetime(2026, 3, 18, 10, 22, tzinfo=ZoneInfo("America/Sao_Paulo"))
        create_mock = AsyncMock(
            side_effect=[
                _response(_message("Hoje já passou das 11:00, então não conseguimos pegar encomendas para hoje.")),
                _response(_message("Ainda estamos antes das 11:00 em Brasília. Posso seguir com sua encomenda para hoje.")),
            ]
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                "5516991426835",
                "Pra hoje Lu",
                "Teste",
                99,
                now=now,
            )

        self.assertEqual(reply, "Ainda estamos antes das 11:00 em Brasília. Posso seguir com sua encomenda para hoje.")
        self.assertEqual(create_mock.await_count, 2)
        retry_messages = create_mock.await_args_list[1].kwargs["messages"]
        self.assertEqual(retry_messages[-1]["role"], "system")
        self.assertIn("ainda NAO passou das 11:00", retry_messages[-1]["content"])
        session_messages = runner.CONVERSATIONS["5516991426835"]["messages"]
        self.assertFalse(
            any("já passou das 11:00" in (message.get("content") or "") for message in session_messages)
        )

    async def test_process_message_forces_cafeteria_handoff_after_cutoff_for_same_day_order(self):
        now = datetime(2026, 3, 18, 11, 5, tzinfo=ZoneInfo("America/Sao_Paulo"))
        create_mock = AsyncMock(return_value=_response(_message("Posso te mostrar a pronta entrega disponível para hoje.")))
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                "5516991111111",
                "Quero um bolo pra hoje",
                "Teste",
                99,
                now=now,
            )

        self.assertEqual(reply, "Posso te mostrar a pronta entrega disponível para hoje.")
        self.assertEqual(runner.CONVERSATIONS["5516991111111"]["current_agent"], "CafeteriaAgent")
        first_messages = create_mock.await_args.kwargs["messages"]
        self.assertIn("Especialista de Cafeteria", first_messages[0]["content"])
        self.assertIn("Status do corte das encomendas para hoje às 11:00: depois do limite.", first_messages[0]["content"])

    async def test_process_message_retries_when_cafeteria_reply_skips_required_specificity(self):
        telefone = "5516991426835"
        runner.CONVERSATIONS[telefone] = {"messages": [], "current_agent": "CafeteriaAgent"}
        create_mock = AsyncMock(
            side_effect=[
                _response(_message("Temos croissants na nossa cafeteria! O tempo de preparo é de 20 minutos. Você gostaria de pedir um croissant agora?")),
                _response(_message("Temos croissant por R$14,50 e o preparo leva 20 minutos. Qual sabor você quer e quantos croissants deseja?")),
            ]
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                telefone,
                "Queria croissant",
                "Vania",
                99,
            )

        self.assertEqual(
            reply,
            "Temos croissant por R$14,50 e o preparo leva 20 minutos. Qual sabor você quer e quantos croissants deseja?",
        )
        self.assertEqual(create_mock.await_count, 2)
        retry_messages = create_mock.await_args_list[1].kwargs["messages"]
        self.assertEqual(retry_messages[-1]["role"], "system")
        self.assertIn("cliente ainda nao especificou o suficiente para fechar um pedido da cafeteria", retry_messages[-1]["content"])
        session_messages = runner.CONVERSATIONS[telefone]["messages"]
        self.assertFalse(
            any("Você gostaria de pedir um croissant agora?" in (message.get("content") or "") for message in session_messages)
        )

    async def test_process_message_clears_session_when_escalated(self):
        create_mock = AsyncMock(
            return_value=_response(
                _message(tool_calls=[_tool_call("escalate_to_human", {"motivo": "Cliente pediu humano"})])
            )
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )

        with patch.object(runner, "client", fake_client):
            with patch.object(runner, "escalate_to_human", return_value="ok") as mocked_escalate:
                reply = await runner.process_message_with_ai(
                    "5516999999999",
                    "Quero falar com humano",
                    "Teste",
                    99,
                )

        self.assertEqual(
            reply,
            "Um momento! Estou transferindo você para um dos nossos atendentes humanos. 👩‍🍳",
        )
        mocked_escalate.assert_called_once_with("5516999999999", "Cliente pediu humano")
        self.assertEqual(runner.CONVERSATIONS["5516999999999"]["messages"], [])

    async def test_process_message_short_circuits_explicit_human_request(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
        )

        with patch.object(runner, "client", fake_client):
            with patch.object(runner, "escalate_to_human", return_value="ok") as mocked_escalate:
                reply = await runner.process_message_with_ai(
                    "5516997777777",
                    "quero falar com um atendente real agora",
                    "Teste",
                    99,
                )

        self.assertEqual(
            reply,
            "Um momento! Estou transferindo você para um dos nossos atendentes humanos. 👩‍🍳",
        )
        mocked_escalate.assert_called_once_with("5516997777777", "Cliente pediu humano")
        fake_client.chat.completions.create.assert_not_awaited()
        self.assertEqual(runner.CONVERSATIONS["5516997777777"]["messages"], [])

    async def test_process_message_short_circuits_opt_out_without_human_handoff(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
        )
        runner.CONVERSATIONS["5516991212121"] = {
            "current_agent": "CakeOrderAgent",
            "messages": [{"role": "system", "content": "system"}],
            "seasonal_context": "easter",
            "service_date_context": {"date": "2026-03-28"},
            "conversation_correction_context": {"modo_recebimento": "retirada"},
        }

        with patch.object(runner, "client", fake_client):
            with patch.object(runner, "escalate_to_human", return_value="ok") as mocked_escalate:
                reply = await runner.process_message_with_ai(
                    "5516991212121",
                    "quero desativar o bot",
                    "Teste",
                    99,
                )

        self.assertEqual(reply, OPT_OUT_MESSAGE)
        mocked_escalate.assert_not_called()
        fake_client.chat.completions.create.assert_not_awaited()
        self.assertEqual(
            runner.CONVERSATIONS["5516991212121"],
            {"current_agent": "TriageAgent", "messages": []},
        )

    async def test_process_message_switches_from_sweet_to_cake_when_topic_changes(self):
        telefone = "5516995656565"
        runner.CONVERSATIONS[telefone] = {"messages": [], "current_agent": "SweetOrderAgent"}
        create_mock = AsyncMock(return_value=_response(_message("Posso montar seu bolo sob encomenda.")))
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                telefone,
                "Quero um bolo B4 para sábado",
                "Vania",
                99,
            )

        self.assertEqual(reply, "Posso montar seu bolo sob encomenda.")
        self.assertEqual(runner.CONVERSATIONS[telefone]["current_agent"], "CakeOrderAgent")
        first_messages = create_mock.await_args.kwargs["messages"]
        self.assertIn("especialista em Bolos Sob Encomenda", first_messages[0]["content"])

    async def test_process_message_switches_from_cake_to_sweet_when_topic_changes(self):
        telefone = "5516993434343"
        runner.CONVERSATIONS[telefone] = {"messages": [], "current_agent": "CakeOrderAgent"}
        create_mock = AsyncMock(return_value=_response(_message("Posso seguir com os docinhos sob encomenda.")))
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                telefone,
                "Quero 50 brigadeiros para sábado",
                "Vania",
                99,
            )

        self.assertEqual(reply, "Posso seguir com os docinhos sob encomenda.")
        self.assertEqual(runner.CONVERSATIONS[telefone]["current_agent"], "SweetOrderAgent")
        first_messages = create_mock.await_args.kwargs["messages"]
        self.assertIn("especialista em Doces Sob Encomenda", first_messages[0]["content"])

    async def test_process_message_handles_post_purchase_queries(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
        )
        support_service = OrderSupportService(
            MockOrderSupportAdapter(
                [
                    OrderRecord(phone="5516990000001", order_id="1001", status="pendente", pix_confirmed=False, cancelable=True, invoice_email="cliente@example.com"),
                    OrderRecord(phone="5516990000002", order_id="1002", status="em_preparo", pix_confirmed=True, cancelable=False, invoice_email="cliente2@example.com"),
                ]
            ),
        )
        test_cases = [
            (
                "5516990000001",
                "Qual o status do pedido?",
                "O pedido 1001 está com status *pendente*. O painel pode confirmar se já foi preparado.",
            ),
            (
                "5516990000002",
                "Confirma o PIX do pedido 123?",
                "Recebemos e registramos o PIX obrigatório para esse pedido.",
            ),
            (
                "5516990000001",
                "Preciso cancelar a encomenda do sábado",
                "Esse pedido ainda pode ser cancelado pelo painel operacional. Informe o motivo para finalizar o cancelamento.",
            ),
            (
                "5516990000002",
                "Quero a nota fiscal do bolo",
                "A nota fiscal do pedido 1002 será enviada para cliente2@example.com em até um dia útil.",
            ),
        ]

        with patch.object(runner, "client", fake_client):
            for phone, text, expected in test_cases:
                runner.CONVERSATIONS[phone] = {"messages": [], "current_agent": "CakeOrderAgent"}
                reply = await runner.process_message_with_ai(
                    phone,
                    text,
                    "Teste",
                    99,
                    order_support_service=support_service,
                )
                self.assertEqual(reply, expected)

        fake_client.chat.completions.create.assert_not_awaited()

    async def test_process_message_logs_post_purchase_failure_when_support_falls_back(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
        )

        class FakeSupport:
            def handle(self, topic, phone, **_kwargs):
                return False, "", "order_not_found"

        with patch.object(runner, "client", fake_client), patch.object(runner, "increment_counter") as counter_mock:
            reply = await runner.process_message_with_ai(
                "5516990000003",
                "Qual o status do pedido?",
                "Teste",
                99,
                order_support_service=FakeSupport(),
            )

        self.assertEqual(reply, POST_PURCHASE_MESSAGES["status"])
        fake_client.chat.completions.create.assert_not_awaited()
        fallback_calls = [
            call
            for call in counter_mock.call_args_list
            if call.args and call.args[0] == "ai_post_purchase_fallback_total"
        ]
        self.assertTrue(fallback_calls)
        failure_call = next(
            (call for call in fallback_calls if call.kwargs.get("failure_reason") == "order_not_found"), None
        )
        self.assertIsNotNone(failure_call)
        self.assertEqual(failure_call.kwargs.get("outcome"), "failure")

    async def test_process_message_short_circuits_when_order_stays_draft(self):
        create_mock = AsyncMock(
            return_value=_response(
                _message(
                    tool_calls=[
                        _tool_call(
                            "create_cake_order",
                            {
                                "linha": "tradicional",
                                "categoria": "tradicional",
                                "tamanho": "B3",
                                "massa": "Mesclada",
                                "recheio": "Brigadeiro de Nutella",
                                "mousse": "Ninho",
                                "adicional": "Cereja",
                                "descricao": "Bolo B3 mesclado com Brigadeiro de Nutella e mousse de Ninho + Cereja",
                                "data_entrega": "25/03/2026",
                                "horario_retirada": "17:30",
                                "modo_recebimento": "retirada",
                                "pagamento": {"forma": "PIX"},
                            },
                        )
                    ]
                )
            )
        )
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )

        draft_result = (
            "Resumo final do pedido\n\n"
            "Bolo B3 de mesclada\n"
            "Recheio: Brigadeiro de Nutella com Ninho e adicional de cereja\n"
            "Retirada 25/3 Quarta 17:30\n"
            "Valor: R$135,00\n\n"
            "Ainda nao foi salvo como pedido confirmado no sistema.\n"
            "Se estiver tudo certo, me envie uma confirmacao final explicita para concluir."
        )

        with patch.object(runner, "client", fake_client):
            with patch("app.ai.tool_execution.save_cake_order_draft_process", return_value=draft_result):
                reply = await runner.process_message_with_ai(
                    "5516992821034",
                    "quero esse bolo para hoje",
                    "Teste",
                    99,
                    now=datetime(2026, 3, 25, 15, 0, tzinfo=ZoneInfo("America/Sao_Paulo")),
                )

        self.assertEqual(reply, draft_result)
        self.assertEqual(create_mock.await_count, 1)
        tool_messages = [m for m in runner.CONVERSATIONS["5516992821034"]["messages"] if m.get("role") == "tool"]
        self.assertTrue(tool_messages)
        self.assertEqual(tool_messages[-1]["content"], draft_result)

    async def test_process_message_blocks_hallucinated_saved_reply_when_last_truth_is_draft(self):
        phone = "5516992821034"
        draft_result = (
            "Resumo final do pedido\n\n"
            "Bolo B3 de mesclada\n"
            "Recheio: Brigadeiro de Nutella com Ninho e adicional de cereja\n"
            "Retirada 25/3 Quarta 17:30\n"
            "Valor: R$135,00\n\n"
            "Ainda nao foi salvo como pedido confirmado no sistema.\n"
            "Se estiver tudo certo, me envie uma confirmacao final explicita para concluir."
        )
        runner.CONVERSATIONS[phone] = {
            "current_agent": "CakeOrderAgent",
            "messages": [
                {"role": "system", "content": "system"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "tool-1",
                            "type": "function",
                            "function": {"name": "create_cake_order", "arguments": "{}"},
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "tool-1",
                    "name": "create_cake_order",
                    "content": draft_result,
                },
            ],
        }
        create_mock = AsyncMock(return_value=_response(_message("Seu pedido foi salvo!")))
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                phone,
                "pode sim",
                "Teste",
                99,
                now=datetime(2026, 3, 25, 15, 5, tzinfo=ZoneInfo("America/Sao_Paulo")),
            )

        self.assertEqual(reply, draft_result)


if __name__ == "__main__":
    unittest.main()
