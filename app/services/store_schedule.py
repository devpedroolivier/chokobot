from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from datetime import date, datetime, timedelta

from app.db.database import get_connection
from app.services.commercial_rules import STORE_HOURS_SUMMARY, STORE_WINDOWS, SUNDAY_RULE_LINE, SUNDAY_UNAVAILABLE_MESSAGE
from app.services.encomendas_utils import _parse_hora
from app.settings import get_settings
from app.utils.datetime_utils import now_in_bot_timezone

READY_DELIVERY_SUMMARY = "bolo pronta entrega, cafeteria ou ovos pronta entrega"
GIFT_CATALOG_SUMMARY = "presentes regulares: cestas box, caixinha de chocolate e flores"

_DAY_LABELS = {
    0: "segunda-feira",
    1: "terca-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sabado",
    6: "domingo",
}

_DAY_TITLE_LABELS = {
    0: "Segunda",
    1: "Terca",
    2: "Quarta",
    3: "Quinta",
    4: "Sexta",
    5: "Sabado",
    6: "Domingo",
}

_WEEKDAY_ALIASES = {
    "segunda": 0,
    "segunda feira": 0,
    "segunda-feira": 0,
    "terca": 1,
    "terca feira": 1,
    "terca-feira": 1,
    "terça": 1,
    "terça feira": 1,
    "terça-feira": 1,
    "quarta": 2,
    "quarta feira": 2,
    "quarta-feira": 2,
    "quinta": 3,
    "quinta feira": 3,
    "quinta-feira": 3,
    "sexta": 4,
    "sexta feira": 4,
    "sexta-feira": 4,
    "sabado": 5,
    "sabado agora": 5,
    "sabado que vem": 5,
    "sábado": 5,
    "sábado agora": 5,
    "sábado que vem": 5,
    "domingo": 6,
}

_MONTH_ALIASES = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

_DEFAULT_OPERATIONAL_CALENDAR = {
    "blocked_dates": [],
    "date_overrides": [],
    "slot_capacities": [],
    "seasonal_dates": [],
}


def _normalize_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(without_marks.casefold().strip().split())


def _reference_service_date(value: date | datetime | None = None) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return now_in_bot_timezone().date()


def _calendar_path() -> Path:
    return Path(get_settings().operational_calendar_path)


@lru_cache(maxsize=1)
def _load_operational_calendar_cached(path_str: str, modified_ns: int) -> dict:
    path = Path(path_str)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(_DEFAULT_OPERATIONAL_CALENDAR)

    if not isinstance(payload, dict):
        return dict(_DEFAULT_OPERATIONAL_CALENDAR)

    normalized = dict(_DEFAULT_OPERATIONAL_CALENDAR)
    for key in normalized:
        value = payload.get(key)
        normalized[key] = value if isinstance(value, list) else []
    return normalized


def load_operational_calendar() -> dict:
    path = _calendar_path()
    try:
        modified_ns = path.stat().st_mtime_ns
    except OSError:
        return dict(_DEFAULT_OPERATIONAL_CALENDAR)
    return _load_operational_calendar_cached(str(path), modified_ns)


def format_service_date(value: date | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%d/%m/%Y")


def format_service_date_with_weekday(value: date | None) -> str:
    if value is None:
        return ""
    return f"{value.strftime('%d/%m/%Y')} ({_DAY_TITLE_LABELS[value.weekday()]})"


def _build_future_date(day: int, month: int, reference: date, year: int | None = None) -> date | None:
    candidate_years = [year] if year is not None else [reference.year, reference.year + 1]
    for candidate_year in candidate_years:
        if candidate_year is None:
            continue
        try:
            candidate = date(candidate_year, month, day)
        except ValueError:
            continue
        if candidate >= reference or year is not None:
            return candidate
    return None


def _resolve_day_of_month(day: int, reference: date) -> date | None:
    month = reference.month
    year = reference.year
    for _ in range(24):
        try:
            candidate = date(year, month, day)
        except ValueError:
            candidate = None
        if candidate and candidate >= reference:
            return candidate
        month += 1
        if month > 12:
            month = 1
            year += 1
    return None


def _next_or_same_weekday(reference: date, weekday: int) -> date:
    delta = (weekday - reference.weekday()) % 7
    return reference + timedelta(days=delta)


def upcoming_weekday_dates(reference: date | datetime | None = None) -> dict[int, date]:
    base_date = _reference_service_date(reference)
    return {weekday: _next_or_same_weekday(base_date, weekday) for weekday in range(7)}


def resolve_service_date_reference(text: str | None, reference: date | datetime | None = None) -> date | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None

    base_date = _reference_service_date(reference)

    if re.search(r"\b(hoje|hj)\b", normalized):
        return base_date
    if re.search(r"\bamanha\b", normalized):
        return base_date + timedelta(days=1)

    explicit_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", normalized)
    if explicit_match:
        day = int(explicit_match.group(1))
        month = int(explicit_match.group(2))
        year_token = explicit_match.group(3)
        year = None
        if year_token:
            year = int(year_token)
            if year < 100:
                year += 2000
        candidate = _build_future_date(day, month, base_date, year)
        if candidate:
            return candidate

    month_match = re.search(
        r"\b(?:dia\s+)?(\d{1,2})\s+de\s+([a-zç]+)(?:\s+de\s+(\d{2,4}))?\b",
        normalized,
    )
    if month_match:
        day = int(month_match.group(1))
        month = _MONTH_ALIASES.get(month_match.group(2))
        year_token = month_match.group(3)
        year = None
        if year_token:
            year = int(year_token)
            if year < 100:
                year += 2000
        if month:
            candidate = _build_future_date(day, month, base_date, year)
            if candidate:
                return candidate

    day_only_match = re.search(r"\bdia\s+(\d{1,2})\b", normalized)
    if day_only_match:
        candidate = _resolve_day_of_month(int(day_only_match.group(1)), base_date)
        if candidate:
            return candidate

    matched_weekday = None
    for alias, weekday in sorted(_WEEKDAY_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            matched_weekday = weekday
            break

    if matched_weekday is None:
        return None

    candidate = _next_or_same_weekday(base_date, matched_weekday)
    next_week_patterns = (
        rf"\b(?:proximo|proxima|pr[oó]ximo|pr[oó]xima)\s+.*\b{re.escape(_DAY_LABELS[matched_weekday].split('-')[0])}\b",
        rf"\b{re.escape(_DAY_LABELS[matched_weekday].split('-')[0])}(?:-feira| feira)?\s+que\s+vem\b",
        rf"\b{re.escape(_DAY_LABELS[matched_weekday].split('-')[0])}(?:-feira| feira)?\s+da\s+semana\s+que\s+vem\b",
        rf"\b{re.escape(_DAY_LABELS[matched_weekday].split('-')[0])}(?:-feira| feira)?\s+na\s+semana\s+que\s+vem\b",
    )
    if "semana que vem" in normalized or any(re.search(pattern, normalized) for pattern in next_week_patterns):
        candidate += timedelta(days=7)
    return candidate


def resolve_service_date_context(text: str | None, reference: date | datetime | None = None) -> dict | None:
    resolved_date = resolve_service_date_reference(text, reference)
    if resolved_date is None:
        return None
    return {
        "date": format_service_date(resolved_date),
        "weekday": _DAY_TITLE_LABELS[resolved_date.weekday()],
        "display": format_service_date_with_weekday(resolved_date),
        "source_text": (text or "").strip(),
    }


def build_calendar_reference_context(reference: date | datetime | None = None) -> str:
    base_date = _reference_service_date(reference)
    upcoming = upcoming_weekday_dates(base_date)
    weekday_parts = [
        f"{_DAY_LABELS[index]} = {format_service_date(upcoming[index])}"
        for index in range(7)
    ]
    next_week_saturday = upcoming[5] + timedelta(days=7)
    return (
        "Referencias rapidas de calendario: "
        f"hoje = {format_service_date(base_date)} ({_DAY_TITLE_LABELS[base_date.weekday()]}), "
        f"amanha = {format_service_date(base_date + timedelta(days=1))} "
        f"({_DAY_TITLE_LABELS[(base_date + timedelta(days=1)).weekday()]}). "
        "Proximas ocorrencias por dia da semana: "
        + ", ".join(weekday_parts)
        + ". "
        + f"Se o cliente disser 'sabado da semana que vem' ou 'sabado que vem', use {format_service_date(next_week_saturday)} (Sabado)."
    )


def build_operational_calendar_context(reference: date | datetime | None = None) -> str:
    base_date = _reference_service_date(reference)
    calendar = load_operational_calendar()
    notes: list[str] = []

    for entry in calendar.get("blocked_dates", []):
        target = _calendar_date(entry)
        if target is None or target < base_date:
            continue
        reason = str(entry.get("reason") or entry.get("label") or "data bloqueada").strip()
        notes.append(f"{format_service_date(target)} bloqueado ({reason})")

    for entry in calendar.get("date_overrides", []):
        target = _calendar_date(entry)
        if target is None or target < base_date:
            continue
        if str(entry.get("closed") or "").lower() in {"1", "true", "sim", "yes"}:
            reason = str(entry.get("reason") or entry.get("label") or "fechado").strip()
            notes.append(f"{format_service_date(target)} fechado ({reason})")
            continue
        opening = _parse_hora(str(entry.get("open") or ""))
        closing = _parse_hora(str(entry.get("close") or ""))
        if opening and closing:
            label = str(entry.get("label") or "horario especial").strip()
            notes.append(f"{format_service_date(target)} horario especial {opening}-{closing} ({label})")

    if not notes:
        return "Calendario operacional especial: sem bloqueios ou excecoes configurados no momento."
    return "Calendario operacional especial: " + "; ".join(notes[:6]) + "."


def parse_service_date(value: str | None) -> date | None:
    raw = (value or "").strip()
    if not raw:
        return None

    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _calendar_date(entry: dict) -> date | None:
    return parse_service_date(str(entry.get("date") or ""))


def _match_calendar_entry(entries: list[dict], target_date: date) -> dict | None:
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if _calendar_date(entry) == target_date:
            return entry
    return None


def seasonal_date_entry(name: str, *, reference: date | datetime | None = None) -> dict | None:
    target = _normalize_text(name)
    if not target:
        return None
    base_date = _reference_service_date(reference)
    entries = [
        entry
        for entry in load_operational_calendar().get("seasonal_dates", [])
        if isinstance(entry, dict) and _normalize_text(str(entry.get("name") or "")) == target
    ]
    if not entries:
        return None

    parsed: list[tuple[date, dict]] = []
    for entry in entries:
        parsed_date = _calendar_date(entry)
        if parsed_date is None:
            continue
        parsed.append((parsed_date, entry))
    if not parsed:
        return None

    future = [item for item in parsed if item[0] >= base_date]
    if future:
        future.sort(key=lambda item: item[0])
        return future[0][1]
    parsed.sort(key=lambda item: item[0], reverse=True)
    return parsed[0][1]


def easter_date_message(reference: date | datetime | None = None) -> str:
    entry = seasonal_date_entry("pascoa", reference=reference)
    if entry is None:
        return "A data da Páscoa varia por ano. Posso confirmar para você com a equipe em instantes."

    target = _calendar_date(entry)
    if target is None:
        return "A data da Páscoa varia por ano. Posso confirmar para você com a equipe em instantes."
    label = str(entry.get("label") or "Páscoa").strip()
    return (
        f"{label}: {format_service_date_with_weekday(target)}. "
        "Se quiser, eu já te ajudo a escolher os itens do pedido."
    )


def _slot_time_bounds(entry: dict) -> tuple[str | None, str | None]:
    time_from = _parse_hora(str(entry.get("time_from") or ""))
    time_to = _parse_hora(str(entry.get("time_to") or ""))
    return time_from, time_to


def _normalize_capacity_mode(value: str | None) -> str:
    normalized = _normalize_text(value)
    aliases = {
        "": "all",
        "all": "all",
        "todos": "all",
        "geral": "all",
        "retirada": "retirada",
        "entrega": "entrega",
    }
    return aliases.get(normalized, "all")


def operational_day_override(value: str | date | None) -> dict | None:
    parsed = value if isinstance(value, date) else parse_service_date(value)
    if not parsed:
        return None
    return _match_calendar_entry(load_operational_calendar().get("date_overrides", []), parsed)


def blocked_service_date_entry(value: str | date | None) -> dict | None:
    parsed = value if isinstance(value, date) else parse_service_date(value)
    if not parsed:
        return None
    return _match_calendar_entry(load_operational_calendar().get("blocked_dates", []), parsed)


def _capacity_entries_for_date(value: str | date | None) -> list[dict]:
    parsed = value if isinstance(value, date) else parse_service_date(value)
    if not parsed:
        return []
    return [
        entry
        for entry in load_operational_calendar().get("slot_capacities", [])
        if isinstance(entry, dict) and _calendar_date(entry) == parsed
    ]


def _count_scheduled_orders_for_capacity(
    target_date: date,
    *,
    time_from: str | None = None,
    time_to: str | None = None,
    mode: str = "all",
) -> int:
    params: list[object] = [target_date.isoformat()]
    query = [
        "SELECT COUNT(*) AS total",
        "FROM encomendas e",
        "LEFT JOIN entregas d ON d.encomenda_id = e.id",
        "WHERE e.data_entrega = ?",
    ]

    if mode in {"retirada", "entrega"}:
        query.append("AND COALESCE(d.tipo, 'retirada') = ?")
        params.append(mode)

    if time_from is not None:
        query.append("AND COALESCE(e.horario, '') >= ?")
        params.append(time_from)
    if time_to is not None:
        query.append("AND COALESCE(e.horario, '') <= ?")
        params.append(time_to)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("\n".join(query), params)
        row = cursor.fetchone()
        return int(row["total"] if row is not None else 0)
    finally:
        conn.close()


def _capacity_violation(
    value: str | date | None,
    horario: str | None,
    *,
    mode: str | None = None,
) -> dict | None:
    parsed = value if isinstance(value, date) else parse_service_date(value)
    if not parsed:
        return None

    parsed_time = _parse_hora(horario or "")
    requested_mode = _normalize_capacity_mode(mode)

    for entry in _capacity_entries_for_date(parsed):
        time_from, time_to = _slot_time_bounds(entry)
        entry_mode = _normalize_capacity_mode(str(entry.get("mode") or "all"))

        if requested_mode != "all" and entry_mode not in {"all", requested_mode}:
            continue
        if parsed_time and time_from and parsed_time < time_from:
            continue
        if parsed_time and time_to and parsed_time > time_to:
            continue
        if not parsed_time and (time_from or time_to):
            continue

        max_orders_raw = entry.get("max_orders")
        try:
            max_orders = int(max_orders_raw)
        except (TypeError, ValueError):
            continue
        if max_orders < 0:
            continue

        scheduled_total = _count_scheduled_orders_for_capacity(
            parsed,
            time_from=time_from,
            time_to=time_to,
            mode=entry_mode,
        )
        if scheduled_total >= max_orders:
            return {
                "entry": entry,
                "scheduled_total": scheduled_total,
                "max_orders": max_orders,
                "time_from": time_from,
                "time_to": time_to,
                "mode": entry_mode,
            }
    return None


def _format_capacity_message(target_date: date, violation: dict) -> str:
    entry = violation.get("entry") or {}
    label = str(entry.get("label") or entry.get("reason") or "capacidade operacional").strip()
    time_from = violation.get("time_from")
    time_to = violation.get("time_to")
    mode = violation.get("mode")

    scope = format_service_date_with_weekday(target_date)
    if time_from and time_to:
        scope += f", das {time_from} as {time_to}"
    elif time_from:
        scope += f", a partir de {time_from}"
    elif time_to:
        scope += f", ate {time_to}"

    if mode == "retirada":
        scope += " para retirada"
    elif mode == "entrega":
        scope += " para entrega"

    return (
        f"Nao temos mais vaga para {scope} por {label}. "
        "Me passe outro horario ou outra data para eu seguir certinho."
    )


def _format_blocked_date_message(target_date: date, entry: dict | None = None) -> str:
    details = entry or {}
    reason = str(details.get("reason") or details.get("label") or "indisponibilidade operacional").strip()
    return (
        f"Nao estamos atendendo em {format_service_date_with_weekday(target_date)} por {reason}. "
        f"Horario de funcionamento: {STORE_HOURS_SUMMARY}"
    )


def _format_closed_override_message(target_date: date, entry: dict | None = None) -> str:
    details = entry or {}
    reason = str(details.get("reason") or details.get("label") or "fechamento operacional").strip()
    return (
        f"Nao estamos atendendo em {format_service_date_with_weekday(target_date)} por {reason}. "
        f"Horario de funcionamento: {STORE_HOURS_SUMMARY}"
    )


def is_sunday_service_date(value: str | None) -> bool:
    parsed = parse_service_date(value)
    return parsed.weekday() == 6 if parsed else False


def store_window_for_date(value: str | date | None) -> tuple[str, str] | None:
    if isinstance(value, date):
        parsed = value
    else:
        parsed = parse_service_date(value)
    if not parsed:
        return None
    override = operational_day_override(parsed)
    if override:
        if str(override.get("closed") or "").lower() in {"1", "true", "sim", "yes"}:
            return None
        opening = _parse_hora(str(override.get("open") or ""))
        closing = _parse_hora(str(override.get("close") or ""))
        if opening and closing:
            return opening, closing
    return STORE_WINDOWS.get(parsed.weekday())


def validate_service_date(value: str | None) -> str | None:
    parsed = parse_service_date(value)
    if not parsed:
        return None
    if parsed.weekday() == 6:
        return SUNDAY_UNAVAILABLE_MESSAGE
    blocked_entry = blocked_service_date_entry(parsed)
    if blocked_entry:
        return _format_blocked_date_message(parsed, blocked_entry)
    override = operational_day_override(parsed)
    if override and str(override.get("closed") or "").lower() in {"1", "true", "sim", "yes"}:
        return _format_closed_override_message(parsed, override)
    capacity_error = _capacity_violation(parsed, None)
    if capacity_error:
        return _format_capacity_message(parsed, capacity_error)
    return None


def validate_service_schedule(value: str | None, horario: str | None) -> str | None:
    date_error = validate_service_date(value)
    if date_error:
        return date_error

    parsed_date = parse_service_date(value)
    parsed_time = _parse_hora(horario or "")
    if not parsed_date or not parsed_time:
        return None

    window = store_window_for_date(parsed_date)
    if not window:
        override = operational_day_override(parsed_date)
        if override and str(override.get("closed") or "").lower() in {"1", "true", "sim", "yes"}:
            return _format_closed_override_message(parsed_date, override)
        return validate_service_date(format_service_date(parsed_date))

    opening, closing = window
    if opening <= parsed_time <= closing:
        capacity_error = _capacity_violation(parsed_date, parsed_time)
        if capacity_error:
            return _format_capacity_message(parsed_date, capacity_error)
        return None

    weekday = _DAY_LABELS[parsed_date.weekday()]
    opening_txt = opening.replace(":00", "h")
    closing_txt = closing.replace(":00", "h")
    return (
        f"Para {weekday}, atendemos das {opening_txt} as {closing_txt}. "
        f"Horario de funcionamento: {STORE_HOURS_SUMMARY}"
    )


__all__ = [
    "GIFT_CATALOG_SUMMARY",
    "READY_DELIVERY_SUMMARY",
    "STORE_HOURS_SUMMARY",
    "SUNDAY_UNAVAILABLE_MESSAGE",
    "build_calendar_reference_context",
    "build_operational_calendar_context",
    "easter_date_message",
    "format_service_date",
    "format_service_date_with_weekday",
    "is_sunday_service_date",
    "load_operational_calendar",
    "operational_day_override",
    "parse_service_date",
    "seasonal_date_entry",
    "resolve_service_date_context",
    "resolve_service_date_reference",
    "store_window_for_date",
    "upcoming_weekday_dates",
    "validate_service_date",
    "validate_service_schedule",
]
