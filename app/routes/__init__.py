from fastapi import APIRouter

# Importa apenas módulos que realmente existem
from .web import router as web_router
from .clientes import router as clientes_router
from .encomendas import router as encomendas_router
from .webhook import router as webhook_router

router = APIRouter()

# Registra as rotas
router.include_router(web_router)
router.include_router(clientes_router)
router.include_router(encomendas_router)
router.include_router(webhook_router)
