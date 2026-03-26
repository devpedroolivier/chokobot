from __future__ import annotations

import contextvars
import json
import sys
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone


_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_metrics_lock = threading.Lock()
_counter_metrics: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
_histogram_metrics: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, float]] = defaultdict(
    lambda: {"count": 0.0, "sum": 0.0}
)

_TEST_PHONE_VARIANTS = frozenset({"5511888888888", "11888888888"})


def normalize_tracking_phone(phone: str | None) -> str:
    raw_value = str(phone or "").strip()
    if not raw_value:
        return ""
    return "".join(char for char in raw_value if char.isdigit())


def should_track_phone(phone: str | None) -> bool:
    normalized = normalize_tracking_phone(phone)
    return not normalized or normalized not in _TEST_PHONE_VARIANTS


def normalize_reason_label(value: str | None, default: str = "unknown") -> str:
    normalized = (value or "").strip()
    if normalized:
        return normalized
    return default


def set_request_id(request_id: str | None = None) -> str:
    value = request_id or uuid.uuid4().hex[:12]
    _request_id.set(value)
    return value


def clear_request_id() -> None:
    _request_id.set("-")


def get_request_id() -> str:
    return _request_id.get()


def _normalize_labels(labels: dict | None) -> tuple[tuple[str, str], ...]:
    if not labels:
        return ()
    normalized = []
    for key, value in sorted(labels.items()):
        normalized.append((str(key), str(value)))
    return tuple(normalized)


def increment_counter(name: str, value: float = 1.0, **labels) -> None:
    key = (name, _normalize_labels(labels))
    with _metrics_lock:
        _counter_metrics[key] += value


def observe_duration(name: str, seconds: float, **labels) -> None:
    key = (name, _normalize_labels(labels))
    with _metrics_lock:
        metric = _histogram_metrics[key]
        metric["count"] += 1.0
        metric["sum"] += max(0.0, float(seconds))


def snapshot_metrics() -> tuple[dict, dict]:
    with _metrics_lock:
        counters = dict(_counter_metrics)
        histograms = {key: value.copy() for key, value in _histogram_metrics.items()}
    return counters, histograms


def clear_metrics() -> None:
    with _metrics_lock:
        _counter_metrics.clear()
        _histogram_metrics.clear()


def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{key}="{value}"' for key, value in labels)
    return f"{{{inner}}}"


def render_metrics() -> str:
    counters, histograms = snapshot_metrics()
    lines: list[str] = []

    for (name, labels), value in sorted(counters.items()):
        lines.append(f"{name}{_format_labels(labels)} {value}")

    for (name, labels), values in sorted(histograms.items()):
        lines.append(f"{name}_count{_format_labels(labels)} {values['count']}")
        lines.append(f"{name}_sum{_format_labels(labels)} {values['sum']}")

    return "\n".join(lines) + ("\n" if lines else "")


def log_event(event: str, **fields) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": "INFO",
        "event": event,
        "request_id": get_request_id(),
    }
    payload.update({key: value for key, value in fields.items() if value is not None})
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


def now_monotonic() -> float:
    return time.monotonic()
