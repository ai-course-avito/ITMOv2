import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ai import interrupt
from ai.interrupt_bus import InterruptBus
from ai.mcp_health import health
from ai.memory import run_backfill
from api.errors import install_error_handlers
from config import Settings
from container import Container
from core import metrics, setup_logging
from database import Context, PostgresDB, PostgresPool
from database.retention import run_retention
from database.usage_compaction import run_usage_compaction
from middlewares import setup_middleware
from openapi import add_roles
from routers import setup_routers
from routers.request import ClientDisconnected


async def start(app: FastAPI, container: Container) -> None:
    """Start what the service runs on (the pool, the initial token, the background jobs, the bus between replicas) and register how
    to stop each in the container."""
    settings = container.settings
    pool = PostgresPool(settings.database)
    await pool.__aenter__()
    container.on_close(lambda: pool.__aexit__(None, None, None))
    app.state.db_pool = pool
    metrics.POOL.pool = pool.pool
    if settings.initial_api_key:  # the owner: the token of the deployment
        await PostgresDB(pool, Context(agent=None, token=None, user=None)).ensure_initial_token(settings.initial_api_key)
    background = [
        asyncio.create_task(run_retention(pool.pool)),
        asyncio.create_task(run_usage_compaction(pool.pool)),
        asyncio.create_task(run_backfill(PostgresDB(pool, Context(agent=None, token=None, user=None)))),
    ]

    async def stop_background() -> None:
        for task in background:
            task.cancel()
        await asyncio.gather(*background, return_exceptions=True)

    if settings.redis_url:  # several replicas: they stop each other's streams
        interrupt.bus = InterruptBus.from_url(settings.redis_url)
        background.append(asyncio.create_task(interrupt.bus.serve(interrupt.stop_for_replica)))

        async def close_bus() -> None:
            await interrupt.bus.close()
            interrupt.bus = None

        container.on_close(close_bus)
    container.on_close(stop_background)  # runs first on the way out: the tasks stop, then the bus and the pool
    health.client_of = lambda: interrupt.bus.client if interrupt.bus else None


def create_app(settings: Settings) -> FastAPI:
    container = Container(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await start(app, container)
        try:
            yield
        finally:
            await container.aclose()

    setup_logging()
    app = FastAPI(lifespan=lifespan)
    app.state.container = container
    setup_middleware(app)
    setup_routers(app)
    add_roles(app)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            # errors() may hold non-JSON values (e.g. the ValueError of a custom validator)
            content={"detail": jsonable_encoder(exc.errors(), custom_encoder={Exception: str})},
        )

    @app.exception_handler(ClientDisconnected)
    async def client_disconnected_handler(request: Request, exc: ClientDisconnected):
        return JSONResponse(status_code=499, content={"detail": "Client closed the request"})

    install_error_handlers(app)
    return app


app = create_app(Settings.from_env())
