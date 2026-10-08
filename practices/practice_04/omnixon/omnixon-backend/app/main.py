from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ai.interrupts import InterruptRegistry
from api.controllers.conversations import ClientDisconnected
from api.errors import install_error_handlers
from config import Settings
from container import Container, controllers, wire_data_layer, wire_services
from core import metrics, setup_logging
from infrastructure.jobs import EmbeddingBackfillJob, MessageRetentionJob, TaskSupervisor, UsageCompactionJob
from infrastructure.llm import ModelGateway
from infrastructure.postgres import PostgresPool
from middlewares import setup_middleware
from openapi import add_roles
from repositories.database import Database
from services.memories import MemoryService
from services.tokens import TokenService


async def start(app: FastAPI, container: Container) -> None:
    """Start what the service runs on (the pool, the initial token, the background jobs, the bus between replicas) and register how to stop
    each in the container. What was started first is stopped last."""
    settings = container.settings
    pool = PostgresPool(settings.database)
    await pool.__aenter__()
    container.on_close(lambda: pool.__aexit__(None, None, None))
    app.state.db_pool = pool
    container.get(Database).bind(pool.pool)
    metrics.POOL.pool = pool.pool
    container.on_close(container.get(ModelGateway).aclose)

    if settings.initial_api_key:  # the owner: the token of the deployment
        await container.get(TokenService).ensure_initial(settings.initial_api_key)

    registry = container.get(InterruptRegistry)
    container.on_close(registry.aclose)  # ends the streams that are left and closes the bus
    if settings.redis_url:  # several replicas: they stop each other's streams
        import asyncio

        serving = asyncio.ensure_future(registry.serve())

        async def stop_serving() -> None:
            serving.cancel()
            await asyncio.gather(serving, return_exceptions=True)

        container.on_close(stop_serving)

    supervisor = container.get(TaskSupervisor)
    container.on_close(supervisor.aclose)
    jobs = [
        MessageRetentionJob(pool.pool, settings.message_ttl_days, settings.message_cleanup_interval_seconds),
        UsageCompactionJob(pool.pool, settings.usage_ttl_days, settings.usage_compact_interval_seconds),
        EmbeddingBackfillJob(pool.pool, container.get(MemoryService)),
    ]
    for job in jobs:
        job.start()
        container.on_close(job.aclose)


def create_app(settings: Settings) -> FastAPI:
    container = Container(settings)
    wire_data_layer(container)
    wire_services(container)

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
    for controller in controllers(container):
        app.include_router(controller.router)
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
