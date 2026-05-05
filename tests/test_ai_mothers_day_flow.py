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
from app.ai.policies import mentions_mothers_day
from app.observability import clear_metrics
from app.welcome_message import HUMAN_HANDOFF_MESSAGE


class MentionsMothersDayUnitTests(unittest.TestCase):
    def test_dia_das_maes_com_acento(self):
        self.assertTrue(mentions_mothers_day("Quero um presente para o Dia das Mães"))

    def test_dia_das_maes_sem_acento(self):
        self.assertTrue(mentions_mothers_day("tem cesta de dia das maes?"))

    def test_dia_da_mae_singular(self):
        self.assertTrue(mentions_mothers_day("Vai ter promo do dia da mae?"))

    def test_presente_para_mae(self):
        self.assertTrue(mentions_mothers_day("queria um presente para minha mae"))

    def test_mensagem_neutra_nao_dispara(self):
        self.assertFalse(mentions_mothers_day("Quero um bolo de chocolate"))

    def test_palavra_mae_isolada_nao_dispara(self):
        self.assertFalse(mentions_mothers_day("Minha mae adora seu bolo"))


class AIMothersDayHandoffTests(unittest.IsolatedAsyncioTestCase):
    """A campanha de Dia das Mães e tratada manualmente. Toda mencao dispara handoff."""

    def setUp(self):
        runner.CONVERSATIONS.clear()
        clear_metrics()

    async def _run(self, mensagem: str) -> tuple[str, AsyncMock]:
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock()))
        )

        with patch.object(runner, "client", fake_client), patch.object(
            runner, "escalate_to_human", return_value="ok"
        ) as mocked_escalate:
            reply = await runner.process_message_with_ai(
                "5516999999999",
                mensagem,
                "Teste",
                99,
            )

        fake_client.chat.completions.create.assert_not_awaited()
        return reply, mocked_escalate

    async def test_pergunta_sobre_dia_das_maes_dispara_handoff(self):
        reply, escalate = await self._run("Tem alguma coisa para o Dia das Mães?")
        self.assertEqual(reply, HUMAN_HANDOFF_MESSAGE)
        escalate.assert_called_once()

    async def test_dia_das_maes_sem_acento_dispara_handoff(self):
        reply, escalate = await self._run("Quero ver o cardapio de dia das maes")
        self.assertEqual(reply, HUMAN_HANDOFF_MESSAGE)
        escalate.assert_called_once()

    async def test_presente_para_mae_dispara_handoff(self):
        reply, escalate = await self._run("queria um presente para mae")
        self.assertEqual(reply, HUMAN_HANDOFF_MESSAGE)
        escalate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
