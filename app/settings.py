from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env_str(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env_str(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    fallback = "1" if default else "0"
    return _env_str(name, fallback).lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str) -> tuple[str, ...]:
    raw = _env_str(name)
    if not raw:
        return ()
    return tuple(item.strip() for item in raw.split(",") if item.strip())


DEFAULT_STORE_CLOSED_NOTICE = (
    "⚠️ *Aviso Importante*\n\n"
    "Loja *FECHADA* devido a manutencao na rede eletrica!\n"
    "Agradecemos a compreensao.\n\n"
    "Retornaremos ao atendimento na segunda-feira, a partir do meio-dia."
)


@dataclass(frozen=True)
class AppSettings:
    zapi_token: str
    zapi_base: str
    openai_api_key: str
    db_path: str
    database_url: str
    redis_url: str
    state_sqlite_path: str
    state_backend_fallback_enabled: bool
    outbox_path: str
    outbox_events_path: str
    ai_learnings_path: str
    operational_calendar_path: str
    tz: str
    bot_timezone: str
    cafeteria_url: str
    doces_url: str
    catalog_link: str
    pix_key: str
    store_closed_notice: str
    conversation_service_url: str
    conversation_service_timeout: float
    webhook_secret: str
    webhook_secret_header: str
    webhook_verify_enabled: bool
    webhook_replay_window_seconds: int
    test_phones: tuple[str, ...]
    admin_phones: tuple[str, ...]
    automation_disabled_phones: tuple[str, ...]
    phone_opt_out_auto_resume_minutes: float
    phone_opt_out_reactivation_delay_seconds: float
    panel_auth_enabled: bool
    panel_auth_username: str
    panel_auth_password: str
    admin_frontend_url: str
    ai_save_learning_enabled: bool
    bot_auto_replies_enabled: bool
    http_timeout_connect: int
    http_timeout_read: int
    http_max_retries: int
    http_backoff_factor: float
    order_support_db_path: str
    order_support_invoice_email: str
    knowledge_failure_alert_threshold: int
    knowledge_failure_alert_window_minutes: int
    knowledge_failure_alert_webhook: str
    ai_auto_schedule_enabled: bool
    ai_auto_off_weekday: int
    ai_auto_off_hour: int
    ai_auto_off_minute: int
    ai_auto_on_weekday: int
    ai_auto_on_hour: int
    ai_auto_on_minute: int
    panel_attendants: tuple[str, ...]

    @property
    def zapi_endpoint_text(self) -> str:
        if not self.zapi_base:
            return ""
        return f"{self.zapi_base}/send-text"

    @property
    def zapi_endpoint_image(self) -> str:
        if not self.zapi_base:
            return ""
        return f"{self.zapi_base}/send-image"


def get_settings() -> AppSettings:
    db_path = _env_str("DB_PATH", "dados/chokobot.db")
    database_url = _env_str("DATABASE_URL", f"sqlite:///{db_path}")
    raw_notice = _env_str("STORE_CLOSED_NOTICE", DEFAULT_STORE_CLOSED_NOTICE) or DEFAULT_STORE_CLOSED_NOTICE
    store_closed_notice = raw_notice.replace("\\r\\n", "\n").replace("\\n", "\n")

    return AppSettings(
        zapi_token=_env_str("ZAPI_TOKEN"),
        zapi_base=_env_str("ZAPI_BASE"),
        openai_api_key=_env_str("OPENAI_API_KEY"),
        db_path=db_path,
        database_url=database_url,
        redis_url=_env_str("REDIS_URL"),
        state_sqlite_path=_env_str("STATE_SQLITE_PATH", "dados/state_store.db"),
        state_backend_fallback_enabled=_env_bool("STATE_BACKEND_FALLBACK_ENABLED", True),
        outbox_path=_env_str("OUTBOX_PATH", "dados/outbox.jsonl"),
        outbox_events_path=_env_str("OUTBOX_EVENTS_PATH", "dados/domain_events.jsonl"),
        ai_learnings_path=_env_str("AI_LEARNINGS_PATH", "app/ai/knowledge/learnings.md"),
        operational_calendar_path=_env_str(
            "OPERATIONAL_CALENDAR_PATH",
            "app/ai/knowledge/operational_calendar.json",
        ),
        tz=_env_str("TZ", "America/Sao_Paulo") or "America/Sao_Paulo",
        bot_timezone=_env_str("BOT_TIMEZONE") or "America/Sao_Paulo",
        cafeteria_url=_env_str("CAFETERIA_URL", "http://bit.ly/44ZlKlZ"),
        doces_url=_env_str("DOCES_URL", "https://bit.ly/doceschoko"),
        catalog_link=_env_str("CATALOG_LINK", "https://bit.ly/presenteschoko"),
        pix_key=_env_str("PIX_KEY"),
        store_closed_notice=store_closed_notice,
        conversation_service_url=_env_str("CONVERSATION_SERVICE_URL"),
        conversation_service_timeout=_env_float("CONVERSATION_SERVICE_TIMEOUT", 10.0),
        webhook_secret=_env_str("WEBHOOK_SECRET"),
        webhook_secret_header=_env_str("WEBHOOK_SECRET_HEADER", "X-Webhook-Secret"),
        webhook_verify_enabled=_env_bool("WEBHOOK_VERIFY_ENABLED", False),
        webhook_replay_window_seconds=max(1, _env_int("WEBHOOK_REPLAY_WINDOW_SECONDS", 300)),
        test_phones=_env_csv("TEST_PHONES"),
        admin_phones=_env_csv("ADMIN_PHONES"),
        automation_disabled_phones=_env_csv("AUTOMATION_DISABLED_PHONES"),
        phone_opt_out_auto_resume_minutes=max(
            0.0,
            _env_float("PHONE_OPT_OUT_AUTO_RESUME_MINUTES", 30.0),
        ),
        phone_opt_out_reactivation_delay_seconds=max(
            0.0,
            _env_float("PHONE_OPT_OUT_REACTIVATION_DELAY_SECONDS", 1.5),
        ),
        panel_auth_enabled=_env_bool("PANEL_AUTH_ENABLED", False),
        panel_auth_username=_env_str("PANEL_AUTH_USERNAME"),
        panel_auth_password=_env_str("PANEL_AUTH_PASSWORD"),
        admin_frontend_url=_env_str("ADMIN_FRONTEND_URL"),
        ai_save_learning_enabled=_env_bool("AI_SAVE_LEARNING_ENABLED", False),
        bot_auto_replies_enabled=_env_bool("BOT_AUTO_REPLIES_ENABLED", True),
        http_timeout_connect=max(1, _env_int("HTTP_TIMEOUT_CONNECT", 5)),
        http_timeout_read=max(1, _env_int("HTTP_TIMEOUT_READ", 20)),
        http_max_retries=max(1, _env_int("HTTP_MAX_RETRIES", 3)),
        http_backoff_factor=max(0.0, _env_float("HTTP_BACKOFF_FACTOR", 1.0)),
        order_support_db_path=_env_str("ORDER_SUPPORT_DB_PATH", db_path),
        order_support_invoice_email=_env_str("ORDER_SUPPORT_INVOICE_EMAIL", "financeiro@chokodelicia.com"),
        knowledge_failure_alert_threshold=max(1, _env_int("KNOWLEDGE_FAILURE_ALERT_THRESHOLD", 5)),
        knowledge_failure_alert_window_minutes=max(1, _env_int("KNOWLEDGE_FAILURE_ALERT_WINDOW_MINUTES", 60)),
        knowledge_failure_alert_webhook=_env_str("KNOWLEDGE_FAILURE_ALERT_WEBHOOK"),
        ai_auto_schedule_enabled=_env_bool("AI_AUTO_SCHEDULE_ENABLED", True),
        ai_auto_off_weekday=max(0, min(6, _env_int("AI_AUTO_OFF_WEEKDAY", 4))),
        ai_auto_off_hour=max(0, min(23, _env_int("AI_AUTO_OFF_HOUR", 19))),
        ai_auto_off_minute=max(0, min(59, _env_int("AI_AUTO_OFF_MINUTE", 0))),
        ai_auto_on_weekday=max(0, min(6, _env_int("AI_AUTO_ON_WEEKDAY", 0))),
        ai_auto_on_hour=max(0, min(23, _env_int("AI_AUTO_ON_HOUR", 6))),
        ai_auto_on_minute=max(0, min(59, _env_int("AI_AUTO_ON_MINUTE", 0))),
        panel_attendants=_env_csv("PANEL_ATTENDANTS") or ("Lu",),
    )
