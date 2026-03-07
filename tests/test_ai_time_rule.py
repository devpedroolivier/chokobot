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
        self.assertEqual(context, "Hoje é 07/03/2026, e agora são 15:30.")

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
                _response(_message("Posso te mostrar a pronta entrega de hoje.")),
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

        self.assertEqual(reply, "Posso te mostrar a pronta entrega de hoje.")
        self.assertEqual(runner.CONVERSATIONS["5516999999999"]["current_agent"], "CafeteriaAgent")
        second_messages = create_mock.await_args_list[1].kwargs["messages"]
        self.assertIn("Especialista de Cafeteria", second_messages[0]["content"])

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


if __name__ == "__main__":
    unittest.main()
