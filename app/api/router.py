from fastapi import APIRouter

from app.api.routes import clientes_router, painel_router, pedidos_router, webhook_router

router = APIRouter()
router.include_router(painel_router)
router.include_router(clientes_router)
router.include_router(pedidos_router)
router.include_router(webhook_router)
