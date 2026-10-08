from fastapi import APIRouter

from .request import router as request_router
from .user import router as user_router
from .history import router as history_router
from .chat import router as chat_router
from .self import router as self_router

router = APIRouter(tags=["Main API"])


@router.get("/", summary="Health check")
async def read_root():
    return {"status": "ok"}


for sub_router in (request_router, user_router, history_router, chat_router, self_router):
    router.include_router(sub_router)
