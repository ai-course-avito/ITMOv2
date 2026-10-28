from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as calculation_router


ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Fourier & Chebyshev Education Site")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.include_router(calculation_router)


def page(path: str) -> FileResponse:
    return FileResponse(ROOT / path)


@app.get("/", response_class=FileResponse)
def home() -> FileResponse:
    return page("index.html")


@app.get("/fourier/", response_class=FileResponse)
def fourier() -> FileResponse:
    return page("fourier/index.html")


@app.get("/chebyshev/", response_class=FileResponse)
def chebyshev() -> FileResponse:
    return page("chebyshev/index.html")


@app.get("/approximation/", response_class=FileResponse)
def approximation() -> FileResponse:
    return page("approximation/index.html")


@app.get("/demos/", response_class=FileResponse)
def demos() -> FileResponse:
    return page("demos/index.html")


@app.get("/about/", response_class=FileResponse)
def about() -> FileResponse:
    return page("about/index.html")
