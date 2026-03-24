from __future__ import annotations

from datetime import date, datetime

from app.services.encomendas_utils import _parse_hora

STORE_HOURS_SUMMARY = "Segunda: 12h-18h | Terca a sabado: 9h-18h | Domingo: fechado."
SUNDAY_UNAVAILABLE_MESSAGE = (
    "Nao fazemos pedidos, retiradas ou encomendas para domingo. "
    f"Horario de funcionamento: {STORE_HOURS_SUMMARY}"
)
READY_DELIVERY_SUMMARY = "bolo pronta entrega, Kit Festou ou ovos pronta entrega"
GIFT_CATALOG_SUMMARY = "cestas (Box Cafe ou Chocolate), caixinha de chocolate e flores"

_STORE_WINDOWS = {
    0: ("12:00", "18:00"),
    1: ("09:00", "18:00"),
    2: ("09:00", "18:00"),
    3: ("09:00", "18:00"),
    4: ("09:00", "18:00"),
    5: ("09:00", "18:00"),
}

_DAY_LABELS = {
    0: "segunda-feira",
    1: "terca-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sabado",
    6: "domingo",
}


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
    return _STORE_WINDOWS.get(parsed.weekday())


def validate_service_date(value: str | None) -> str | None:
    if is_sunday_service_date(value):
        return SUNDAY_UNAVAILABLE_MESSAGE
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
        return None

    opening, closing = window
    if opening <= parsed_time <= closing:
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
    "is_sunday_service_date",
    "parse_service_date",
    "store_window_for_date",
    "validate_service_date",
    "validate_service_schedule",
]
