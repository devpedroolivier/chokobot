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


if __name__ == "__main__":
    unittest.main()
