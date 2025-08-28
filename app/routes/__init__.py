from fastapi import APIRouter
from .painel import router as painel_router
from .clientes import router as clientes_router
from .webhook import router as webhook_router

router = APIRouter()
router.include_router(painel_router)
router.include_router(clientes_router)
router.include_router(webhook_router)
