from fastapi import APIRouter, Depends

from access import require
from .agent import router as agent_router
from .agent_version import router as agent_version_router
from .agent_connection import router as agent_connection_router
from .model import router as model_router
from .mcp_server import router as mcp_server_router
from .token import router as token_router
from .rag import router as rag_router
from .memory import router as memory_router
from .usage import router as usage_router

# Everything here needs at least the user role; routes and handlers narrow it further (see access.py)
router = APIRouter(dependencies=[Depends(require("user"))], tags=["Admin API"])

for sub_router in (
    agent_router,
    agent_version_router,
    agent_connection_router,
    model_router,
    mcp_server_router,
    token_router,
    rag_router,
    memory_router,
    usage_router,
):
    router.include_router(sub_router)
