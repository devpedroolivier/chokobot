from __future__ import annotations

from typing import Annotated, Any

from pydantic import AfterValidator, BeforeValidator, Field, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


DEFAULT_STORE_CLOSED_NOTICE = (
    "⚠️ *Aviso Importante*\n\n"
    "Loja *FECHADA* devido a manutencao na rede eletrica!\n"
    "Agradecemos a compreensao.\n\n"
    "Retornaremos ao atendimento na segunda-feira, a partir do meio-dia."
)

_TRUTHY = {"1", "true", "yes", "on"}


def _strip(v: Any) -> Any:
    if isinstance(v, str):
        return v.strip()
    return v


def _csv_to_tuple(v: Any) -> Any:
    if v is None:
        return ()
    if isinstance(v, str):
        if not v.strip():
            return ()
        return tuple(item.strip() for item in v.split(",") if item.strip())
    if isinstance(v, (list, tuple)):
        return tuple(item for item in v if item)
    return v


def _truthy(v: Any) -> Any:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in _TRUTHY
    if isinstance(v, (int, float)):
        return bool(v)
    return v


def _clamp_int(min_value: int, max_value: int | None = None):
    def _clamp(v: int) -> int:
        if max_value is not None:
            return max(min_value, min(max_value, v))
        return max(min_value, v)

    return _clamp


def _clamp_float_min(min_value: float):
    def _clamp(v: float) -> float:
        return max(min_value, v)

    return _clamp


def _expand_escapes(v: Any) -> Any:
    if isinstance(v, str):
        return v.replace("\\r\\n", "\n").replace("\\n", "\n")
    return v


def _lower(v: Any) -> Any:
    if isinstance(v, str):
        return v.lower()
    return v


StrippedStr = Annotated[str, BeforeValidator(_strip)]
CsvTuple = Annotated[tuple[str, ...], NoDecode, BeforeValidator(_csv_to_tuple)]
Truthy = Annotated[bool, BeforeValidator(_truthy)]


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )

    # --- Messaging providers ---------------------------------------------
    zapi_token: StrippedStr = Field(default="", alias="ZAPI_TOKEN")
    zapi_base: StrippedStr = Field(default="", alias="ZAPI_BASE")
    messaging_provider: Annotated[str, BeforeValidator(_strip), AfterValidator(_lower)] = Field(
        default="zapi", alias="MESSAGING_PROVIDER"
    )
    evolution_server_url: StrippedStr = Field(default="", alias="EVOLUTION_SERVER_URL")
    evolution_api_key: StrippedStr = Field(default="", alias="EVOLUTION_API_KEY")
    evolution_instance: StrippedStr = Field(default="", alias="EVOLUTION_INSTANCE")

    # --- AI ---------------------------------------------------------------
    openai_api_key: StrippedStr = Field(default="", alias="OPENAI_API_KEY")

    # --- Persistence ------------------------------------------------------
    db_path: StrippedStr = Field(default="dados/chokobot.db", alias="DB_PATH")
    database_url: StrippedStr = Field(default="", alias="DATABASE_URL")
    redis_url: StrippedStr = Field(default="", alias="REDIS_URL")
    state_sqlite_path: StrippedStr = Field(default="dados/state_store.db", alias="STATE_SQLITE_PATH")
    state_backend_fallback_enabled: Truthy = Field(
        default=True, alias="STATE_BACKEND_FALLBACK_ENABLED"
    )
    outbox_path: StrippedStr = Field(default="dados/outbox.jsonl", alias="OUTBOX_PATH")
    outbox_events_path: StrippedStr = Field(
        default="dados/domain_events.jsonl", alias="OUTBOX_EVENTS_PATH"
    )
    ai_learnings_path: StrippedStr = Field(
        default="app/ai/knowledge/learnings.md", alias="AI_LEARNINGS_PATH"
    )
    operational_calendar_path: StrippedStr = Field(
        default="app/ai/knowledge/operational_calendar.json",
        alias="OPERATIONAL_CALENDAR_PATH",
    )

    # --- Timezone ---------------------------------------------------------
    tz: StrippedStr = Field(default="America/Sao_Paulo", alias="TZ")
    bot_timezone: StrippedStr = Field(default="America/Sao_Paulo", alias="BOT_TIMEZONE")

    # --- Catalog links ----------------------------------------------------
    cafeteria_url: StrippedStr = Field(default="http://bit.ly/44ZlKlZ", alias="CAFETERIA_URL")
    doces_url: StrippedStr = Field(default="https://bit.ly/doceschoko", alias="DOCES_URL")
    catalog_link: StrippedStr = Field(default="https://bit.ly/presenteschoko", alias="CATALOG_LINK")

    # --- Payments / messages ---------------------------------------------
    pix_key: StrippedStr = Field(default="", alias="PIX_KEY")
    store_closed_notice: Annotated[str, BeforeValidator(_expand_escapes), BeforeValidator(_strip)] = (
        Field(default=DEFAULT_STORE_CLOSED_NOTICE, alias="STORE_CLOSED_NOTICE")
    )

    # --- Conversation split deploy ---------------------------------------
    conversation_service_url: StrippedStr = Field(default="", alias="CONVERSATION_SERVICE_URL")
    conversation_service_timeout: float = Field(default=10.0, alias="CONVERSATION_SERVICE_TIMEOUT")

    # --- Webhook security -------------------------------------------------
    webhook_secret: StrippedStr = Field(default="", alias="WEBHOOK_SECRET")
    webhook_secret_header: StrippedStr = Field(
        default="X-Webhook-Secret", alias="WEBHOOK_SECRET_HEADER"
    )
    webhook_verify_enabled: Truthy = Field(default=False, alias="WEBHOOK_VERIFY_ENABLED")
    webhook_replay_window_seconds: Annotated[int, AfterValidator(_clamp_int(1))] = Field(
        default=300, alias="WEBHOOK_REPLAY_WINDOW_SECONDS"
    )

    # --- Phone management -------------------------------------------------
    test_phones: CsvTuple = Field(default=(), alias="TEST_PHONES")
    admin_phones: CsvTuple = Field(default=(), alias="ADMIN_PHONES")
    automation_disabled_phones: CsvTuple = Field(default=(), alias="AUTOMATION_DISABLED_PHONES")
    phone_opt_out_auto_resume_minutes: Annotated[float, AfterValidator(_clamp_float_min(0.0))] = (
        Field(default=30.0, alias="PHONE_OPT_OUT_AUTO_RESUME_MINUTES")
    )
    phone_opt_out_reactivation_delay_seconds: Annotated[
        float, AfterValidator(_clamp_float_min(0.0))
    ] = Field(default=1.5, alias="PHONE_OPT_OUT_REACTIVATION_DELAY_SECONDS")

    # --- Panel auth -------------------------------------------------------
    panel_auth_enabled: Truthy = Field(default=False, alias="PANEL_AUTH_ENABLED")
    panel_auth_username: StrippedStr = Field(default="", alias="PANEL_AUTH_USERNAME")
    panel_auth_password: StrippedStr = Field(default="", alias="PANEL_AUTH_PASSWORD")
    admin_frontend_url: StrippedStr = Field(default="", alias="ADMIN_FRONTEND_URL")

    # --- AI behavior ------------------------------------------------------
    ai_save_learning_enabled: Truthy = Field(default=False, alias="AI_SAVE_LEARNING_ENABLED")
    bot_auto_replies_enabled: Truthy = Field(default=True, alias="BOT_AUTO_REPLIES_ENABLED")

    # --- HTTP client ------------------------------------------------------
    http_timeout_connect: Annotated[int, AfterValidator(_clamp_int(1))] = Field(
        default=5, alias="HTTP_TIMEOUT_CONNECT"
    )
    http_timeout_read: Annotated[int, AfterValidator(_clamp_int(1))] = Field(
        default=20, alias="HTTP_TIMEOUT_READ"
    )
    http_max_retries: Annotated[int, AfterValidator(_clamp_int(1))] = Field(
        default=3, alias="HTTP_MAX_RETRIES"
    )
    http_backoff_factor: Annotated[float, AfterValidator(_clamp_float_min(0.0))] = Field(
        default=1.0, alias="HTTP_BACKOFF_FACTOR"
    )

    # --- Order support ----------------------------------------------------
    order_support_db_path: StrippedStr = Field(default="", alias="ORDER_SUPPORT_DB_PATH")
    order_support_invoice_email: StrippedStr = Field(
        default="financeiro@chokodelicia.com", alias="ORDER_SUPPORT_INVOICE_EMAIL"
    )

    # --- Knowledge alerts -------------------------------------------------
    knowledge_failure_alert_threshold: Annotated[int, AfterValidator(_clamp_int(1))] = Field(
        default=5, alias="KNOWLEDGE_FAILURE_ALERT_THRESHOLD"
    )
    knowledge_failure_alert_window_minutes: Annotated[int, AfterValidator(_clamp_int(1))] = Field(
        default=60, alias="KNOWLEDGE_FAILURE_ALERT_WINDOW_MINUTES"
    )
    knowledge_failure_alert_webhook: StrippedStr = Field(
        default="", alias="KNOWLEDGE_FAILURE_ALERT_WEBHOOK"
    )

    # --- AI auto schedule -------------------------------------------------
    ai_auto_schedule_enabled: Truthy = Field(default=True, alias="AI_AUTO_SCHEDULE_ENABLED")
    ai_auto_off_weekday: Annotated[int, AfterValidator(_clamp_int(0, 6))] = Field(
        default=4, alias="AI_AUTO_OFF_WEEKDAY"
    )
    ai_auto_off_hour: Annotated[int, AfterValidator(_clamp_int(0, 23))] = Field(
        default=19, alias="AI_AUTO_OFF_HOUR"
    )
    ai_auto_off_minute: Annotated[int, AfterValidator(_clamp_int(0, 59))] = Field(
        default=0, alias="AI_AUTO_OFF_MINUTE"
    )
    ai_auto_on_weekday: Annotated[int, AfterValidator(_clamp_int(0, 6))] = Field(
        default=0, alias="AI_AUTO_ON_WEEKDAY"
    )
    ai_auto_on_hour: Annotated[int, AfterValidator(_clamp_int(0, 23))] = Field(
        default=6, alias="AI_AUTO_ON_HOUR"
    )
    ai_auto_on_minute: Annotated[int, AfterValidator(_clamp_int(0, 59))] = Field(
        default=0, alias="AI_AUTO_ON_MINUTE"
    )

    # --- Panel ------------------------------------------------------------
    panel_attendants: CsvTuple = Field(default=("Lu",), alias="PANEL_ATTENDANTS")

    @model_validator(mode="after")
    def _resolve_dependent_defaults(self) -> "AppSettings":
        if not self.database_url:
            object.__setattr__(self, "database_url", f"sqlite:///{self.db_path}")
        if not self.tz:
            object.__setattr__(self, "tz", "America/Sao_Paulo")
        if not self.bot_timezone:
            object.__setattr__(self, "bot_timezone", "America/Sao_Paulo")
        if not self.messaging_provider:
            object.__setattr__(self, "messaging_provider", "zapi")
        if not self.store_closed_notice:
            object.__setattr__(self, "store_closed_notice", DEFAULT_STORE_CLOSED_NOTICE)
        if not self.order_support_db_path:
            object.__setattr__(self, "order_support_db_path", self.db_path)
        if not self.panel_attendants:
            object.__setattr__(self, "panel_attendants", ("Lu",))
        return self

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

    @property
    def evolution_endpoint_text(self) -> str:
        if not self.evolution_server_url or not self.evolution_instance:
            return ""
        base = self.evolution_server_url.rstrip("/")
        return f"{base}/message/sendText/{self.evolution_instance}"


def get_settings() -> AppSettings:
    return AppSettings()
