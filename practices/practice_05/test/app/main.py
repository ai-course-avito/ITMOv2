from pathlib import Path
from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse


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

    # Mount static frontend at /ui
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/ui", StaticFiles(directory=str(frontend_dir), html=True), name="ui")

        @app.get("/")
        def root_redirect():
            # Redirect base URL to UI
            return RedirectResponse(url="/ui/")

    return app


app = create_app()
