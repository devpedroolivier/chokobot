from .painel import router as painel_router
from .pedidos import router as pedidos_router
from .clientes import router as clientes_router
from .webhook import router as webhook_router

__all__ = [
    "painel_router",
    "pedidos_router",
    "clientes_router",
    "webhook_router",
]
