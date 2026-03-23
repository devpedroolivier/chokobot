from __future__ import annotations

from app.settings import get_settings


def resolve_admin_frontend_url(path: str) -> str | None:
    base_url = get_settings().admin_frontend_url.rstrip("/")
    if not base_url:
        return None

    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{base_url}{normalized_path}"
