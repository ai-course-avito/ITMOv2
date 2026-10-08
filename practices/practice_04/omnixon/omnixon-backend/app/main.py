import asyncio
import logfire
from core import metrics
from contextlib import asynccontextmanager
from middlewares import setup_middleware
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from core import (
    DATABASE_CONFIG,
    INITIAL_API_KEY,
    REDIS_URL,
    error_response,
    setup_logging,
)
from starlette.exceptions import HTTPException as StarletteHTTPException
from ai import interrupt
from ai.interrupt_bus import InterruptBus
from ai.memory import run_backfill
from database import Context, PostgresDB, PostgresPool
from database.retention import run_retention
from database.usage_compaction import run_usage_compaction
from routers import setup_routers
from routers.request import ClientDisconnected


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with PostgresPool(DATABASE_CONFIG) as db_pool:  # closes the pool on exit
        app.state.db_pool = db_pool
        metrics.POOL.pool = db_pool.pool
        if INITIAL_API_KEY:  # the owner: the token of the deployment
            await PostgresDB(
                db_pool, Context(agent=None, token=None, user=None)
            ).ensure_initial_token(INITIAL_API_KEY)
        background = [
            asyncio.create_task(run_retention(db_pool.pool)),
            asyncio.create_task(run_usage_compaction(db_pool.pool)),
            asyncio.create_task(
                run_backfill(
                    PostgresDB(db_pool, Context(agent=None, token=None, user=None))
                )
            ),
        ]
        if REDIS_URL:  # several replicas: they stop each other's streams
            interrupt.bus = InterruptBus.from_url(REDIS_URL)
            background.append(asyncio.create_task(interrupt.bus.serve(interrupt.stop_for_replica)))
        try:
            yield
        finally:
            for task in background:
                task.cancel()
            await asyncio.gather(*background, return_exceptions=True)
            if interrupt.bus is not None:
                await interrupt.bus.close()
                interrupt.bus = None


setup_logging()

app = FastAPI(lifespan=lifespan)
setup_middleware(app)
setup_routers(app)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        # errors() may hold non-JSON values (e.g. the ValueError of a custom validator)
        content={
            "detail": jsonable_encoder(exc.errors(), custom_encoder={Exception: str})
        },
    )


@app.exception_handler(ClientDisconnected)
async def client_disconnected_handler(request: Request, exc: ClientDisconnected):
    return JSONResponse(
        status_code=499, content={"detail": "Client closed the request"}
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    status, detail = error_response(exc)
    log = logfire.exception if status == 500 else logfire.warning
    log(
        "Request failed with {status} on {method} {path}",
        status=status,
        method=request.method,
        path=request.url.path,
        _exc_info=exc,
    )
    return JSONResponse(status_code=status, content={"detail": detail})
