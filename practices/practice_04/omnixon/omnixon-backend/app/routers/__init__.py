from fastapi import FastAPI

from .main import router as main_router
from .admin import router as admin_router
from .health import router as health_router


def setup_routers(app: FastAPI):
    app.include_router(health_router)
    app.include_router(main_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1/admin")
