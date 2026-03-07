from fastapi import APIRouter

from app.api.routes import ops_router
from app.api.routes.conversation_internal import router as conversation_internal_router

router = APIRouter()
router.include_router(ops_router)
router.include_router(conversation_internal_router)
