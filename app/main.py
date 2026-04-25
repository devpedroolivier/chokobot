from app.api.router import router
from app.infrastructure.web.app_factory import create_http_app

app, request_context_middleware = create_http_app(
    title="Trufinha — Atendente WhatsApp",
    router=router,
    startup_event="startup_complete",
    mount_static=True,
)
