"""Liveness, readiness and metrics. No token is needed: they are for the platform
that runs the service (Docker, Kubernetes, Prometheus)."""

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from core import metrics
from database.foundation import list_migrations

router = APIRouter(tags=["Operations"])

READINESS_TIMEOUT_SECONDS = 3


@router.get("/healthz", summary="Liveness: the process answers")
async def healthz():
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness: the database answers and is migrated")
async def readyz(request: Request):
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        return JSONResponse(status_code=503, content={"status": "starting"})

    try:
        async with asyncio.timeout(READINESS_TIMEOUT_SECONDS):
            async with pool.pool.acquire() as connection:
                version = await connection.fetchval(
                    "SELECT version FROM migrations WHERE id = 1"
                )
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "database unavailable", "detail": type(exc).__name__},
        )

    expected = list_migrations()[-1][0]
    if version != expected:
        return JSONResponse(
            status_code=503,
            content={"status": "migrating", "migration": version, "expected": expected},
        )
    return {"status": "ok", "migration": version}


@router.get("/metrics", summary="Prometheus metrics", include_in_schema=False)
async def metrics_page():
    body, content_type = metrics.render()
    return Response(content=body, media_type=content_type)
