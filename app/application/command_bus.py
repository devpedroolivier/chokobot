from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class LocalCommandBus:
    def __init__(self):
        self._handlers: dict[type, Callable[[Any], Awaitable[Any]]] = {}

    def register(self, command_type: type, handler: Callable[[Any], Awaitable[Any]]) -> None:
        self._handlers[command_type] = handler

    async def dispatch(self, command: Any):
        handler = self._handlers.get(type(command))
        if handler is None:
            raise ValueError(f"No handler registered for command type {type(command).__name__}")
        return await handler(command)
