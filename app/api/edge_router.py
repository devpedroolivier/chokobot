from fastapi import APIRouter

from app.api.routes import ops_router, webhook_router

router = APIRouter()
router.include_router(ops_router)
router.include_router(webhook_router)
