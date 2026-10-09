"""Liveness, readiness and metrics. No token is needed: they are for the platform that runs the service (Docker, Kubernetes, Prometheus)."""

import asyncio

from fastapi.responses import JSONResponse, Response

from api.controller import Controller, endpoint
from core import metrics
from infrastructure.postgres import list_migrations
from repositories.database import Database

READINESS_TIMEOUT_SECONDS = 3


class HealthController(Controller):
    tags = ["Operations"]

    def __init__(self, database: Database):
        self.database = database
        super().__init__()

    @endpoint.get("/healthz", summary="Liveness: the process answers")
    async def healthz(self):
        return {"status": "ok"}

    @endpoint.get("/readyz", summary="Readiness: the database answers and is migrated")
    async def readyz(self):
        if self.database.pool is None:
            return JSONResponse(status_code=503, content={"status": "starting"})
        try:
            async with asyncio.timeout(READINESS_TIMEOUT_SECONDS):
                async with self.database.pool.acquire() as connection:
                    version = await connection.fetchval("SELECT version FROM migrations WHERE id = 1")
        except Exception as exc:
            return JSONResponse(status_code=503, content={"status": "database unavailable", "detail": type(exc).__name__})
        expected = list_migrations()[-1][0]
        if version != expected:
            return JSONResponse(status_code=503, content={"status": "migrating", "migration": version, "expected": expected})
        return {"status": "ok", "migration": version}

    @endpoint.get("/metrics", summary="Prometheus metrics", include_in_schema=False)
    async def metrics_page(self):
        body, content_type = metrics.render()
        return Response(content=body, media_type=content_type)


class RootController(Controller):
    """The root of the API: the clients' check that the service is there and their token is accepted."""

    prefix = "/api/v1"
    tags = ["Main API"]

    @endpoint.get("/", summary="Health check")
    async def read_root(self):
        return {"status": "ok"}
