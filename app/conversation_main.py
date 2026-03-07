import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.conversation_router import router
from app.db.init_db import ensure_views
from app.models import criar_tabelas
from app.observability import (
    clear_request_id,
    increment_counter,
    log_event,
    now_monotonic,
    observe_duration,
    set_request_id,
)

app = FastAPI(title="Chokobot Conversation Service")
app.include_router(router)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or set_request_id()
    set_request_id(request_id)
    start = now_monotonic()
    status_code = 500
    response = None

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        raise
    finally:
        elapsed = now_monotonic() - start
        increment_counter(
            "http_requests_total",
            method=request.method,
            path=request.url.path,
            status_code=status_code,
        )
        observe_duration(
            "http_request_duration_seconds",
            elapsed,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
        )
        log_event(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            latency_ms=round(elapsed * 1000, 2),
        )
        if response is not None:
            response.headers["X-Request-ID"] = request_id
        clear_request_id()

    return response


@app.on_event("startup")
def on_startup():
    criar_tabelas()
    ensure_views()
    log_event("conversation_startup_complete")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    increment_counter("app_exceptions_total", path=request.url.path, error_type=type(exc).__name__)
    log_event("unhandled_exception", path=request.url.path, error_type=type(exc).__name__)
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"status": "error", "detail": "internal_error"})
