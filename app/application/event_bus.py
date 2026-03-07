from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any


class LocalEventBus:
    def __init__(self):
        self._handlers: dict[type, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Callable[[Any], None]) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: Any) -> None:
        for handler in self._handlers.get(type(event), []):
            handler(event)
