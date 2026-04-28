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
from app.welcome_message import HUMAN_HANDOFF_MESSAGE


class AIEasterHandoffTests(unittest.IsolatedAsyncioTestCase):
    """A campanha de Páscoa encerrou. Qualquer menção deve disparar handoff humano."""

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

    async def test_pedido_de_cardapio_de_pascoa_dispara_handoff(self):
        reply, escalate = await self._run("Quero ver o cardápio de Páscoa")
        self.assertEqual(reply, HUMAN_HANDOFF_MESSAGE)
        escalate.assert_called_once()

    async def test_menciona_ovo_de_chocolate_dispara_handoff(self):
        reply, escalate = await self._run("Quero um ovo de chocolate recheado de prestigio")
        self.assertEqual(reply, HUMAN_HANDOFF_MESSAGE)
        escalate.assert_called_once()

    async def test_pergunta_quando_e_a_pascoa_dispara_handoff(self):
        reply, escalate = await self._run("Quando é a Páscoa?")
        self.assertEqual(reply, HUMAN_HANDOFF_MESSAGE)
        escalate.assert_called_once()

    async def test_pascoa_sem_acento_dispara_handoff(self):
        reply, escalate = await self._run("Manda o cardapio de pascoa")
        self.assertEqual(reply, HUMAN_HANDOFF_MESSAGE)
        escalate.assert_called_once()

    async def test_lanche_com_ovo_nao_dispara_handoff(self):
        """Ovo em contexto de cafeteria (lanche/sanduíche) NÃO é Páscoa."""
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=AsyncMock(
                        return_value=SimpleNamespace(
                            choices=[
                                SimpleNamespace(
                                    message=SimpleNamespace(content="Resposta", tool_calls=[])
                                )
                            ],
                            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
                        )
                    )
                )
            )
        )

        with patch.object(runner, "client", fake_client), patch.object(
            runner, "escalate_to_human", return_value="ok"
        ) as mocked_escalate:
            await runner.process_message_with_ai(
                "5516999999999",
                "Quero um misto com ovo",
                "Teste",
                99,
            )

        mocked_escalate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
