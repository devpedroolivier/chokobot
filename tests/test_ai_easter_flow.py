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
from app.welcome_message import EASTER_CATALOG_MESSAGE


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

    async def test_process_message_handles_ovo_recheado_de_prestigio(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                "5516999999999",
                "Quero um ovo de chocolate recheado de prestigio",
                "Teste",
                99,
            )

        self.assertEqual(reply, EASTER_CATALOG_MESSAGE)
        fake_client.chat.completions.create.assert_not_awaited()

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

    async def test_process_message_handles_ovo_pronta_entrega_via_ai_flow(self):
        ai_reply = "Posso te ajudar com pronta entrega. Voce quer bolo, Kit Festou ou ovos pronta entrega?"
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=_response(_message(ai_reply)))))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                "5516999999999",
                "Oi tem ovo pronta entrega?",
                "Teste",
                99,
            )

        self.assertEqual(reply, ai_reply)
        fake_client.chat.completions.create.assert_awaited_once()

    async def test_process_message_handles_ovo_pacoca_as_easter(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
        )

        with patch.object(runner, "client", fake_client):
            reply = await runner.process_message_with_ai(
                "5516999999999",
                "Tem ovo de pacoca?",
                "Teste",
                99,
            )

        self.assertEqual(reply, EASTER_CATALOG_MESSAGE)
        fake_client.chat.completions.create.assert_not_awaited()

    async def test_process_message_keeps_easter_context_for_follow_up(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
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
        self.assertEqual(second_reply, EASTER_CATALOG_MESSAGE)
        fake_client.chat.completions.create.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
