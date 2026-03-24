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
from app.observability import clear_metrics


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
        self.assertEqual(
            context,
            "Hoje é 07/03/2026, e agora são 15:30. "
            "Horario oficial de Brasilia (America/Sao_Paulo). "
            "Status do corte das 17:30: antes do limite.",
        )

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
        self.assertIn("Status do corte das 17:30: antes do limite.", messages[0]["content"])

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
                )
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

        self.assertIn("Transferindo", reply)
        self.assertEqual(runner.CONVERSATIONS["5516999999999"]["current_agent"], "CafeteriaAgent")
        self.assertEqual(create_mock.await_count, 1)

    async def test_process_message_retries_when_model_hallucinates_cutoff_before_1730(self):
        now = datetime(2026, 3, 18, 13, 22, tzinfo=ZoneInfo("America/Sao_Paulo"))
        create_mock = AsyncMock(
            side_effect=[
                _response(_message("Hoje já passou das 17:30, então não conseguimos fazer a entrega.")),
                _response(_message("Ainda estamos antes das 17:30 em Brasília. Posso seguir com seu pedido para hoje.")),
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

        self.assertEqual(reply, "Ainda estamos antes das 17:30 em Brasília. Posso seguir com seu pedido para hoje.")
        self.assertEqual(create_mock.await_count, 2)
        retry_messages = create_mock.await_args_list[1].kwargs["messages"]
        self.assertEqual(retry_messages[-1]["role"], "system")
        self.assertIn("ainda NAO passou das 17:30", retry_messages[-1]["content"])
        session_messages = runner.CONVERSATIONS["5516991426835"]["messages"]
        self.assertFalse(
            any("já passou das 17:30" in (message.get("content") or "") for message in session_messages)
        )

    async def test_process_message_forces_cafeteria_handoff_after_cutoff_for_same_day_order(self):
        now = datetime(2026, 3, 18, 18, 5, tzinfo=ZoneInfo("America/Sao_Paulo"))
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
        self.assertIn("Status do corte das 17:30: depois do limite.", first_messages[0]["content"])

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


if __name__ == "__main__":
    unittest.main()
