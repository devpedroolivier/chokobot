from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.settings import get_settings


DEFAULT_BOT_TIMEZONE = "America/Sao_Paulo"


def get_bot_timezone() -> ZoneInfo:
    timezone_name = get_settings().bot_timezone or DEFAULT_BOT_TIMEZONE
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_BOT_TIMEZONE)


def now_in_bot_timezone() -> datetime:
    return datetime.now(get_bot_timezone())


def normalize_to_bot_timezone(value: datetime | None = None) -> datetime:
    current = value or now_in_bot_timezone()
    timezone = get_bot_timezone()
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone)
    return current.astimezone(timezone)
