from __future__ import annotations

from app.db.init_db import ensure_views
from app.models import criar_tabelas
from app.observability import log_event


def bootstrap_runtime(startup_event: str) -> None:
    criar_tabelas()
    ensure_views()
    log_event(startup_event)
