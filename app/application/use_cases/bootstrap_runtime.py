from __future__ import annotations

from app.db.init_db import ensure_views
from app.db.schema_guard import validate_runtime_schema
from app.models import criar_tabelas
from app.observability import log_event


def bootstrap_runtime(startup_event: str) -> None:
    criar_tabelas()
    validate_runtime_schema()
    ensure_views()
    log_event(startup_event)
