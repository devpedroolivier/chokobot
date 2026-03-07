from __future__ import annotations

import json
import os
from datetime import datetime
from collections.abc import MutableMapping, Iterator
from dataclasses import dataclass, field


class StateBackend:
    def get(self, namespace: str, key: str):
        raise NotImplementedError

    def set(self, namespace: str, key: str, value) -> None:
        raise NotImplementedError

    def delete(self, namespace: str, key: str) -> None:
        raise NotImplementedError

    def keys(self, namespace: str) -> list[str]:
        raise NotImplementedError

    def get_flag(self, name: str, default: bool) -> bool:
        raise NotImplementedError

    def set_flag(self, name: str, value: bool) -> None:
        raise NotImplementedError


@dataclass
class InMemoryStateBackend(StateBackend):
    namespaces: dict[str, dict[str, dict]] = field(default_factory=dict)
    flags: dict[str, bool] = field(default_factory=dict)

    def get(self, namespace: str, key: str):
        return self.namespaces.get(namespace, {}).get(key)

    def set(self, namespace: str, key: str, value) -> None:
        self.namespaces.setdefault(namespace, {})[key] = value

    def delete(self, namespace: str, key: str) -> None:
        self.namespaces.get(namespace, {}).pop(key, None)

    def keys(self, namespace: str) -> list[str]:
        return list(self.namespaces.get(namespace, {}).keys())

    def get_flag(self, name: str, default: bool) -> bool:
        return self.flags.get(name, default)

    def set_flag(self, name: str, value: bool) -> None:
        self.flags[name] = value


class RedisStateBackend(StateBackend):
    def __init__(self, redis_url: str):
        import redis

        self.client = redis.Redis.from_url(redis_url, decode_responses=True)

    @staticmethod
    def _key(namespace: str, key: str) -> str:
        return f"chokobot:state:{namespace}:{key}"

    @staticmethod
    def _flag_key(name: str) -> str:
        return f"chokobot:flags:{name}"

    def get(self, namespace: str, key: str):
        raw = self.client.get(self._key(namespace, key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def set(self, namespace: str, key: str, value) -> None:
        self.client.set(self._key(namespace, key), json.dumps(value, default=str))

    def delete(self, namespace: str, key: str) -> None:
        self.client.delete(self._key(namespace, key))

    def keys(self, namespace: str) -> list[str]:
        keys = self.client.keys(self._key(namespace, "*"))
        return [k.rsplit(":", 1)[-1] for k in keys]

    def get_flag(self, name: str, default: bool) -> bool:
        raw = self.client.get(self._flag_key(name))
        if raw is None:
            return default
        return raw == "1"

    def set_flag(self, name: str, value: bool) -> None:
        self.client.set(self._flag_key(name), "1" if value else "0")


class StateMap(MutableMapping[str, dict]):
    def __init__(self, namespace: str, backend: StateBackend):
        self.namespace = namespace
        self.backend = backend

    def __getitem__(self, key: str) -> dict:
        val = self.backend.get(self.namespace, key)
        if val is None:
            raise KeyError(key)
        return val

    def __setitem__(self, key: str, value: dict) -> None:
        self.backend.set(self.namespace, key, value)

    def __delitem__(self, key: str) -> None:
        if key not in self:
            raise KeyError(key)
        self.backend.delete(self.namespace, key)

    def __iter__(self) -> Iterator[str]:
        yield from self.backend.keys(self.namespace)

    def __len__(self) -> int:
        return len(self.backend.keys(self.namespace))


class ConversationStateStore:
    def __init__(self, backend: StateBackend):
        self.backend = backend
        self.estados_encomenda = StateMap("encomenda", backend)
        self.estados_cafeteria = StateMap("cafeteria", backend)
        self.estados_entrega = StateMap("entrega", backend)
        self.estados_cestas_box = StateMap("cestas_box", backend)
        self.estados_atendimento = StateMap("atendimento", backend)
        self.ai_sessions = StateMap("ai_session", backend)
        self.processed_messages = StateMap("processed_message", backend)
        self.recent_messages = StateMap("recent_message", backend)

    def is_bot_ativo(self) -> bool:
        return self.backend.get_flag("bot_ativo", True)

    def set_bot_ativo(self, value: bool) -> None:
        self.backend.set_flag("bot_ativo", value)

    def has_processed_message(self, message_id: str) -> bool:
        if not message_id:
            return False
        return message_id in self.processed_messages

    def mark_processed_message(self, message_id: str, seen_at: datetime) -> None:
        if not message_id:
            return
        self.processed_messages[message_id] = {"seen_at": seen_at.isoformat()}
        self._trim_namespace(self.processed_messages, limit=2000, sort_key="seen_at")

    def get_recent_message(self, phone: str) -> dict | None:
        if not phone:
            return None
        return self.recent_messages.get(phone)

    def set_recent_message(self, phone: str, text: str, seen_at: datetime) -> None:
        if not phone:
            return
        self.recent_messages[phone] = {"texto": text, "hora": seen_at.isoformat()}
        self._trim_namespace(self.recent_messages, limit=5000, sort_key="hora")

    def clear_runtime_state(self) -> None:
        for state_map in (self.ai_sessions, self.processed_messages, self.recent_messages):
            state_map.clear()

    @staticmethod
    def _trim_namespace(state_map: StateMap, *, limit: int, sort_key: str) -> None:
        if len(state_map) <= limit:
            return

        items = []
        for key in list(state_map):
            value = state_map.get(key) or {}
            items.append((key, value.get(sort_key, "")))

        items.sort(key=lambda item: item[1])
        for key, _ in items[:-limit]:
            state_map.pop(key, None)


def build_conversation_state_store() -> ConversationStateStore:
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return ConversationStateStore(InMemoryStateBackend())

    try:
        return ConversationStateStore(RedisStateBackend(redis_url))
    except Exception as exc:
        print(f"[STATE] Redis indisponível ({exc}); usando estado em memória.")
        return ConversationStateStore(InMemoryStateBackend())
