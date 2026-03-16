from app.api.edge_router import router
from app.infrastructure.web.app_factory import create_http_app

app, request_context_middleware = create_http_app(
    title="Chokobot Edge Gateway",
    router=router,
    startup_event="edge_startup_complete",
)
