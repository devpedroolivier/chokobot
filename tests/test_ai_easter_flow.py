import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")


class _AsyncOpenAIStub:
    def __init__(self, *args, **kwargs):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=None))


sys.modules.setdefault("openai", SimpleNamespace(AsyncOpenAI=_AsyncOpenAIStub))

from app.ai import runner
from app.observability import clear_metrics
from app.welcome_message import EASTER_CATALOG_MESSAGE, HUMAN_HANDOFF_MESSAGE


def _message(content: str):
    return SimpleNamespace(content=content, tool_calls=[])


def _response(message):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


class AIEasterFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        runner.CONVERSATIONS.clear()
        clear_metrics()

    async def test_process_message_returns_easter_link_without_calling_ai(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                "5516999999999",
                "Quero ver o cardápio de Páscoa",
                "Teste",
                99,
            )

        self.assertEqual(reply, EASTER_CATALOG_MESSAGE)
        fake_client.chat.completions.create.assert_not_awaited()

    async def test_process_message_handles_pascoa_without_accent(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                "5516999999999",
                "Tem ovo de pascoa disponivel?",
                "Teste",
                99,
            )

        self.assertEqual(reply, EASTER_CATALOG_MESSAGE)
        fake_client.chat.completions.create.assert_not_awaited()

    async def test_process_message_handles_ovo_recheado_de_prestigio_via_ai_flow(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=AsyncMock(return_value=_response(_message("Resposta catalogada"))))
            )
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                "5516999999999",
                "Quero um ovo de chocolate recheado de prestigio",
                "Teste",
                99,
            )

        self.assertEqual(reply, "Resposta catalogada")
        fake_client.chat.completions.create.assert_awaited_once()

    async def test_process_message_handles_generic_ovo_request_as_easter(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                "5516999999999",
                "Eu gostaria de encomendar um ovo",
                "Teste",
                99,
            )

        self.assertEqual(reply, EASTER_CATALOG_MESSAGE)
        fake_client.chat.completions.create.assert_not_awaited()

    async def test_process_message_handles_ovo_pronta_entrega_via_human_handoff(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
        )

        with patch.object(runner, "client", fake_client):
            with patch.object(runner, "escalate_to_human", return_value="ok") as mocked_escalate:
                reply = await runner.process_message_with_ai(
                    "5516999999999",
                    "Oi tem ovo pronta entrega?",
                    "Teste",
                    99,
                )

        self.assertEqual(reply, HUMAN_HANDOFF_MESSAGE)
        mocked_escalate.assert_called_once_with("5516999999999", "Ovos pronta entrega exigem atendimento humano")
        fake_client.chat.completions.create.assert_not_awaited()

    async def test_process_message_handles_quero_pronta_entrega_de_ovo_via_human_handoff(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
        )

        with patch.object(runner, "client", fake_client):
            with patch.object(runner, "escalate_to_human", return_value="ok") as mocked_escalate:
                reply = await runner.process_message_with_ai(
                    "5516999999999",
                    "Quero pronta entrega de ovo",
                    "Teste",
                    99,
                )

        self.assertEqual(reply, HUMAN_HANDOFF_MESSAGE)
        mocked_escalate.assert_called_once_with("5516999999999", "Ovos pronta entrega exigem atendimento humano")
        fake_client.chat.completions.create.assert_not_awaited()

    async def test_process_message_keeps_specific_easter_item_query_in_ai_flow(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=_response(_message("Consulta específica")))))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                "5516999999999",
                "Tem ovo cookie nutella?",
                "Teste",
                99,
            )

        self.assertEqual(reply, "Consulta específica")
        fake_client.chat.completions.create.assert_awaited_once()

    async def test_process_message_handles_ovo_pacoca_via_ai_flow(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=AsyncMock(return_value=_response(_message("Consulta específica"))))
            )
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                "5516999999999",
                "Tem ovo de pacoca?",
                "Teste",
                99,
            )

        self.assertEqual(reply, "Consulta específica")
        fake_client.chat.completions.create.assert_awaited_once()

    async def test_process_message_does_not_loop_easter_link_on_specific_follow_up(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=AsyncMock(return_value=_response(_message("Temos consulta específica"))))
            )
        )

        with patch.object(runner, "client", fake_client):
            first_reply = await runner.process_message_with_ai(
                "5516999999999",
                "Quero ver o cardapio de pascoa",
                "Teste",
                99,
            )
            second_reply = await runner.process_message_with_ai(
                "5516999999999",
                "tem de prestigio?",
                "Teste",
                99,
            )

        self.assertEqual(first_reply, EASTER_CATALOG_MESSAGE)
        self.assertEqual(second_reply, "Temos consulta específica")
        fake_client.chat.completions.create.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
