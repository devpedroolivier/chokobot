from app.api.conversation_router import router
from app.infrastructure.web.app_factory import create_http_app

app, request_context_middleware = create_http_app(
    title="Chokobot Conversation Service",
    router=router,
    startup_event="conversation_startup_complete",
)
