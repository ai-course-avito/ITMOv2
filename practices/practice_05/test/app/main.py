from fastapi import FastAPI, APIRouter


def create_app() -> FastAPI:
    app = FastAPI(title="Coffee Backend", version="0.1.0")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        return {"ready": True}

    # Reserve /api base and mount v1 router
    api_router = APIRouter(prefix="/api")
    v1_router = APIRouter(prefix="/v1")

    @v1_router.get("/")
    def v1_root():
        return {"service": "coffee-backend", "version": "v1"}

    api_router.include_router(v1_router)
    app.include_router(api_router)

    return app


app = create_app()
