from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse

from app.db.database import get_connection
from app.observability import increment_counter, render_metrics

router = APIRouter()


def liveness_payload() -> dict:
    return {"status": "ok"}


def readiness_payload() -> tuple[dict, int]:
    db_path = os.getenv("DB_PATH", "dados/chokobot.db")
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
        finally:
            conn.close()
    except Exception as exc:
        return (
            {
                "status": "error",
                "checks": {"database": "down"},
                "detail": type(exc).__name__,
                "db_path": db_path,
            },
            503,
        )

    return (
        {
            "status": "ok",
            "checks": {"database": "up"},
            "db_path": db_path,
        },
        200,
    )


@router.get("/healthz")
def healthz():
    increment_counter("ops_health_requests_total", endpoint="healthz")
    return liveness_payload()


@router.get("/readyz")
def readyz():
    increment_counter("ops_health_requests_total", endpoint="readyz")
    payload, status_code = readiness_payload()
    return JSONResponse(content=payload, status_code=status_code)


@router.get("/metrics", response_class=PlainTextResponse)
def metrics():
    increment_counter("ops_health_requests_total", endpoint="metrics")
    return PlainTextResponse(render_metrics(), media_type="text/plain; version=0.0.4")
