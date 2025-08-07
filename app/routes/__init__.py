from fastapi import APIRouter
from .encomendas import router as encomendas_router
from .web import router as web_router
from .webhook import router as webhook_router  # ← adiciona aqui

router = APIRouter()

router.include_router(encomendas_router)
router.include_router(web_router)
router.include_router(webhook_router)  # ← inclui aqui
