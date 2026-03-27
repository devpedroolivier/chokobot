from __future__ import annotations

from app.db.init_db import ensure_views
from app.db.schema_guard import validate_runtime_schema
from app.models import criar_tabelas
from app.observability import log_event
from app.settings import get_settings


def bootstrap_runtime(startup_event: str) -> None:
    criar_tabelas()
    validate_runtime_schema()
    ensure_views()
    settings = get_settings()
    if not (settings.pix_key or "").strip():
        log_event("startup_warning_missing_pix_key", level="WARNING")
    log_event(startup_event)
