from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from collections.abc import MutableMapping, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from app.observability import log_event
from app.settings import get_settings

_PROCESSED_MESSAGE_TTL_SECONDS = 60


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
        self.client.ping()

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


class SQLiteStateBackend(StateBackend):
    def __init__(self, sqlite_path: str):
        resolved_path = str(sqlite_path or "").strip() or "dados/state_store.db"
        self.sqlite_path = resolved_path
        self._db_lock = threading.RLock()
        Path(self.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._db_lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS state_kv (
                        namespace TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (namespace, key)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS state_flags (
                        name TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                connection.commit()

    def get(self, namespace: str, key: str):
        with self._db_lock:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT value FROM state_kv WHERE namespace = ? AND key = ?",
                    (namespace, key),
                ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(str(row["value"]))
        except json.JSONDecodeError:
            return None

    def set(self, namespace: str, key: str, value) -> None:
        payload = json.dumps(value, default=str)
        now_iso = datetime.utcnow().isoformat()
        with self._db_lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO state_kv(namespace, key, value, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(namespace, key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (namespace, key, payload, now_iso),
                )
                connection.commit()

    def delete(self, namespace: str, key: str) -> None:
        with self._db_lock:
            with self._connect() as connection:
                connection.execute(
                    "DELETE FROM state_kv WHERE namespace = ? AND key = ?",
                    (namespace, key),
                )
                connection.commit()

    def keys(self, namespace: str) -> list[str]:
        with self._db_lock:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT key FROM state_kv WHERE namespace = ? ORDER BY updated_at ASC",
                    (namespace,),
                ).fetchall()
        return [str(row["key"]) for row in rows]

    def get_flag(self, name: str, default: bool) -> bool:
        with self._db_lock:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT value FROM state_flags WHERE name = ?",
                    (name,),
                ).fetchone()
        if row is None:
            return default
        return str(row["value"]) == "1"

    def set_flag(self, name: str, value: bool) -> None:
        now_iso = datetime.utcnow().isoformat()
        serialized = "1" if value else "0"
        with self._db_lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO state_flags(name, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (name, serialized, now_iso),
                )
                connection.commit()


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
        self.conversation_threads = StateMap("conversation_thread", backend)
        self.processed_messages = StateMap("processed_message", backend)
        self.recent_messages = StateMap("recent_message", backend)
        self.phone_opt_out = StateMap("phone_opt_out", backend)

    def is_bot_ativo(self) -> bool:
        return self.backend.get_flag("bot_ativo", True)

    def set_bot_ativo(self, value: bool) -> None:
        self.backend.set_flag("bot_ativo", value)

    def is_phone_opted_out(self, phone: str | None) -> bool:
        normalized = str(phone or "").strip()
        if not normalized:
            return False
        return self.phone_opt_out.get(normalized) is not None

    def set_phone_opted_out(self, phone: str | None, value: bool) -> None:
        normalized = str(phone or "").strip()
        if not normalized:
            return
        if value:
            self.phone_opt_out[normalized] = {"updated_at": datetime.now(timezone.utc).isoformat()}
            self._trim_namespace(self.phone_opt_out, limit=10000, sort_key="updated_at")
            return
        self.phone_opt_out.pop(normalized, None)

    def get_phone_opted_out_updated_at(self, phone: str | None) -> datetime | None:
        normalized = str(phone or "").strip()
        if not normalized:
            return None
        payload = self.phone_opt_out.get(normalized)
        if payload is None:
            return None
        raw_value = str(payload.get("updated_at") or "").strip()
        if not raw_value:
            return None
        try:
            parsed = datetime.fromisoformat(raw_value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            # Legacy values were persisted as UTC-naive timestamps.
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def has_processed_message(self, message_id: str) -> bool:
        if not message_id:
            return False
        payload = self.processed_messages.get(message_id)
        if payload is None:
            return False

        expires_at_raw = str(payload.get("expires_at") or "").strip()
        if not expires_at_raw:
            seen_at_raw = str(payload.get("seen_at") or "").strip()
            if seen_at_raw:
                try:
                    seen_at = datetime.fromisoformat(seen_at_raw)
                    expires_at_raw = (seen_at + timedelta(seconds=_PROCESSED_MESSAGE_TTL_SECONDS)).isoformat()
                except ValueError:
                    expires_at_raw = ""

        if expires_at_raw:
            try:
                expires_at = datetime.fromisoformat(expires_at_raw)
                if datetime.now(tz=expires_at.tzinfo) >= expires_at:
                    self.processed_messages.pop(message_id, None)
                    return False
            except ValueError:
                pass
        return True

    def mark_processed_message(self, message_id: str, seen_at: datetime, ttl_seconds: int = _PROCESSED_MESSAGE_TTL_SECONDS) -> None:
        if not message_id:
            return
        expires_at = seen_at + timedelta(seconds=max(1, ttl_seconds))
        self.processed_messages[message_id] = {
            "seen_at": seen_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        self._trim_namespace(self.processed_messages, limit=2000, sort_key="seen_at")

    def mark_processed_message_if_new(
        self,
        message_id: str,
        seen_at: datetime,
        ttl_seconds: int = _PROCESSED_MESSAGE_TTL_SECONDS,
    ) -> bool:
        if not message_id:
            return True
        if self.has_processed_message(message_id):
            return False
        self.mark_processed_message(message_id, seen_at, ttl_seconds=ttl_seconds)
        return True

    def get_recent_message(self, phone: str) -> dict | None:
        if not phone:
            return None
        return self.recent_messages.get(phone)

    def set_recent_message(self, phone: str, text: str, seen_at: datetime) -> None:
        if not phone:
            return
        self.recent_messages[phone] = {"texto": text, "hora": seen_at.isoformat()}
        self._trim_namespace(self.recent_messages, limit=5000, sort_key="hora")

    def get_conversation_messages(self, phone: str) -> list[dict]:
        if not phone:
            return []
        thread = self.conversation_threads.get(phone) or {}
        return list(thread.get("messages", []))

    def append_conversation_message(
        self,
        phone: str,
        *,
        role: str,
        actor_label: str,
        content: str,
        seen_at: datetime,
    ) -> None:
        if not phone:
            return
        normalized_content = str(content or "").strip()
        if not normalized_content:
            return

        timestamp = seen_at.isoformat()
        thread = self.conversation_threads.get(phone) or {"messages": [], "updated_at": timestamp}
        messages = list(thread.get("messages", []))
        previous = messages[-1] if messages else None
        if (
            previous is not None
            and previous.get("role") == role
            and previous.get("content") == normalized_content
            and previous.get("timestamp") == timestamp
        ):
            return

        messages.append(
            {
                "role": role,
                "actor_label": actor_label,
                "content": normalized_content,
                "timestamp": timestamp,
            }
        )
        self.conversation_threads[phone] = {
            "messages": messages[-200:],
            "updated_at": timestamp,
        }
        self._trim_namespace(self.conversation_threads, limit=5000, sort_key="updated_at")

    def clear_runtime_state(self) -> None:
        for state_map in (
            self.ai_sessions,
            self.conversation_threads,
            self.processed_messages,
            self.recent_messages,
            self.phone_opt_out,
        ):
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
    settings = get_settings()
    redis_url = settings.redis_url
    if not redis_url:
        try:
            return ConversationStateStore(SQLiteStateBackend(settings.state_sqlite_path))
        except Exception as exc:
            log_event("state_backend_fallback", backend="memory", reason=type(exc).__name__)
            return ConversationStateStore(InMemoryStateBackend())

    try:
        return ConversationStateStore(RedisStateBackend(redis_url))
    except Exception as exc:
        if not settings.state_backend_fallback_enabled:
            raise RuntimeError(
                f"Redis state backend unavailable and fallback is disabled: {type(exc).__name__}"
            ) from exc
        log_event("state_backend_fallback", backend="sqlite", reason=type(exc).__name__)
        try:
            return ConversationStateStore(SQLiteStateBackend(settings.state_sqlite_path))
        except Exception as sqlite_exc:
            log_event("state_backend_fallback", backend="memory", reason=type(sqlite_exc).__name__)
            return ConversationStateStore(InMemoryStateBackend())
