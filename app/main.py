from app.api.router import router
from app.infrastructure.web.app_factory import create_http_app

app, request_context_middleware = create_http_app(
    title="Agente WhatsApp - Chokodelícia",
    router=router,
    startup_event="startup_complete",
    mount_static=True,
)
