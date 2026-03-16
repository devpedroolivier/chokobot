import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.application.command_bus import LocalCommandBus
from app.application.commands import GenerateAiReplyCommand, HandleInboundMessageCommand
from app.application.service_registry import get_command_bus


class CommandBusTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_command_bus_dispatches_registered_handler(self):
        bus = LocalCommandBus()
        handler = AsyncMock(return_value="ok")
        bus.register(GenerateAiReplyCommand, handler)

        result = await bus.dispatch(
            GenerateAiReplyCommand(
                telefone="5511999999999",
                text="oi",
                nome_cliente="Teste",
                cliente_id=1,
            )
        )

        self.assertEqual(result, "ok")
        handler.assert_awaited_once()

    async def test_service_registry_bus_dispatches_inbound_message_command(self):
        get_command_bus.cache_clear()
        bus = get_command_bus()

        with patch("app.application.handlers.handle_inbound_message.process_inbound_message", AsyncMock()) as mocked:
            await bus.dispatch(HandleInboundMessageCommand(payload={"message": "oi"}))

        mocked.assert_awaited_once_with({"message": "oi"})


if __name__ == "__main__":
    unittest.main()
