from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.settings import get_settings


SAME_DAY_CAKE_ORDER_CUTOFF = (11, 0)
DELIVERY_CUTOFF = (17, 30)
DELIVERY_FEE_STANDARD = 10.0
DELIVERY_FEE_CAFETERIA = 5.0
CROISSANT_PREP_MINUTES = 20
CARD_INSTALLMENT_MIN_TOTAL = 100.0
CARD_INSTALLMENT_MAX = 2

_DEFAULT_STORE_WINDOWS = {
    0: ("12:00", "18:00"),
    1: ("09:00", "18:00"),
    2: ("09:00", "18:00"),
    3: ("09:00", "18:00"),
    4: ("09:00", "18:00"),
    5: ("09:00", "18:00"),
}


def _format_brl(value: float) -> str:
    return f"R${value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_hhmm(parts: tuple[int, int]) -> str:
    hour, minute = parts
    return f"{hour:02d}:{minute:02d}"


def _normalize_clock(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.strptime(raw, "%H:%M")
    except ValueError:
        return None
    return parsed.strftime("%H:%M")


def _human_clock_label(value: str | None) -> str:
    normalized = _normalize_clock(value)
    if not normalized:
        return ""
    hour, minute = normalized.split(":")
    if minute == "00":
        return f"{int(hour)}h"
    return f"{int(hour)}h{minute}"


def _calendar_display_date(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(raw, fmt)
            return parsed.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return None


def _load_operational_calendar() -> dict:
    path = Path(get_settings().operational_calendar_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _build_store_windows(calendar: dict) -> dict[int, tuple[str, str]]:
    weekly = calendar.get("weekly_windows")
    if not isinstance(weekly, dict):
        return dict(_DEFAULT_STORE_WINDOWS)

    resolved: dict[int, tuple[str, str]] = {}
    for weekday in range(7):
        entry = weekly.get(str(weekday))
        if not isinstance(entry, dict):
            continue
        if str(entry.get("closed") or "").strip().lower() in {"1", "true", "sim", "yes"}:
            continue

        opening = _normalize_clock(entry.get("open"))
        closing = _normalize_clock(entry.get("close"))
        if opening and closing:
            resolved[weekday] = (opening, closing)

    if not resolved:
        return dict(_DEFAULT_STORE_WINDOWS)
    return resolved


def _open_sunday_exceptions(calendar: dict) -> list[dict]:
    entries = calendar.get("date_overrides")
    if not isinstance(entries, list):
        return []

    exceptions: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        display_date = _calendar_display_date(entry.get("date"))
        if not display_date:
            continue

        try:
            weekday = datetime.strptime(display_date, "%d/%m/%Y").weekday()
        except ValueError:
            continue
        if weekday != 6:
            continue

        if str(entry.get("closed") or "").strip().lower() in {"1", "true", "sim", "yes"}:
            continue

        opening = _normalize_clock(entry.get("open"))
        closing = _normalize_clock(entry.get("close"))
        if not (opening and closing):
            continue

        exceptions.append(
            {
                "date": display_date,
                "label": str(entry.get("label") or "domingo com funcionamento especial").strip(),
                "open": opening,
                "close": closing,
            }
        )

    exceptions.sort(key=lambda item: datetime.strptime(item["date"], "%d/%m/%Y"))
    return exceptions


def _build_store_hours_summary(store_windows: dict[int, tuple[str, str]], sunday_exceptions: list[dict]) -> str:
    weekday_labels = {
        0: "Segunda",
        1: "Terca",
        2: "Quarta",
        3: "Quinta",
        4: "Sexta",
        5: "Sabado",
        6: "Domingo",
    }

    parts: list[str] = []
    for weekday in range(7):
        window = store_windows.get(weekday)
        if window is None:
            parts.append(f"{weekday_labels[weekday]}: fechado")
            continue
        open_label = _human_clock_label(window[0])
        close_label = _human_clock_label(window[1])
        parts.append(f"{weekday_labels[weekday]}: {open_label}-{close_label}")

    summary = " | ".join(parts)
    if not sunday_exceptions:
        return summary

    first = sunday_exceptions[0]
    summary += (
        f" (excecao: {first['label']} em {first['date']}, "
        f"aberto das {_human_clock_label(first['open'])} as {_human_clock_label(first['close'])})."
    )
    return summary


def _build_sunday_rule(sunday_exceptions: list[dict]) -> str:
    base = "Nao fazemos pedidos, retiradas ou encomendas para domingo regular."
    if not sunday_exceptions:
        return base

    first = sunday_exceptions[0]
    return (
        f"{base} Excecao operacional cadastrada: {first['label']} ({first['date']}), "
        f"das {_human_clock_label(first['open'])} as {_human_clock_label(first['close'])}."
    )


_CALENDAR_RULES = _load_operational_calendar()
STORE_WINDOWS = _build_store_windows(_CALENDAR_RULES)
_SUNDAY_EXCEPTIONS = _open_sunday_exceptions(_CALENDAR_RULES)

SAME_DAY_CAKE_ORDER_CUTOFF_LABEL = _format_hhmm(SAME_DAY_CAKE_ORDER_CUTOFF)
DELIVERY_CUTOFF_LABEL = _format_hhmm(DELIVERY_CUTOFF)
DELIVERY_FEE_STANDARD_LABEL = _format_brl(DELIVERY_FEE_STANDARD)
DELIVERY_FEE_CAFETERIA_LABEL = _format_brl(DELIVERY_FEE_CAFETERIA)
STORE_HOURS_SUMMARY = _build_store_hours_summary(STORE_WINDOWS, _SUNDAY_EXCEPTIONS)
STORE_OPERATION_RULE_LINE = f"Horario de funcionamento: {STORE_HOURS_SUMMARY}"
SUNDAY_RULE_LINE = _build_sunday_rule(_SUNDAY_EXCEPTIONS)
SUNDAY_UNAVAILABLE_MESSAGE = f"{SUNDAY_RULE_LINE} Horario de funcionamento: {STORE_HOURS_SUMMARY}"
DELIVERY_RULE_LINE = (
    f"A Chokodelícia FAZ entregas! Taxa para bolos/encomendas/presentes: {DELIVERY_FEE_STANDARD_LABEL}. "
    f"Taxa para itens da cafeteria: {DELIVERY_FEE_CAFETERIA_LABEL}. "
    f"Horário limite: até {DELIVERY_CUTOFF_LABEL}."
)
PAYMENT_CHANGE_RULE_LINE = (
    "Regras de pagamento: troco so existe para Dinheiro. "
    "Se for Dinheiro, pergunte se o cliente precisa de troco (use troco_para=0 quando nao precisar). "
    "PIX e Cartao nao usam troco."
)
SIMPLE_PAYMENT_CHANGE_RULE_LINE = (
    "Troco so existe para Dinheiro. "
    "Se for Dinheiro, pergunte se o cliente precisa de troco (use troco_para=0 quando nao precisar). "
    "PIX e Cartao nao usam troco."
)
PAYMENT_INSTALLMENT_RULE_LINE = (
    f"Parcelamento so no Cartao e somente acima de {_format_brl(CARD_INSTALLMENT_MIN_TOTAL)}, em ate {CARD_INSTALLMENT_MAX}x."
)
CROISSANT_PREP_RULE_LINE = f"Se o cliente perguntar tempo de preparo do croissant, informe {CROISSANT_PREP_MINUTES} minutos."
