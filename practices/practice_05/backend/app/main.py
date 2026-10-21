import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, AsyncIterator

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .ignav import search_fares
from .history import add_history
from .schemas import FareSearch, FareSearchResponse, HealthResponse, RoundTripSearch

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        app.state.http_client = client
        yield


app = FastAPI(title="Билетик API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


def get_api_key() -> str:
    api_key = os.getenv("IGNAV_API_KEY", "").strip()
    if not api_key and ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == "IGNAV_API_KEY":
                api_key = value.strip().strip('"\'')
                break
    if not api_key:
        raise HTTPException(status_code=503, detail="Ключ Ignav не настроен на сервере.")
    return api_key


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/api/fares/one-way", response_model=FareSearchResponse)
async def one_way(
    search: FareSearch,
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
    api_key: Annotated[str, Depends(get_api_key)],
) -> FareSearchResponse:
    result = await search_fares(search, client, api_key)
    return await add_history(search, result)


@app.post("/api/fares/round-trip", response_model=FareSearchResponse)
async def round_trip(
    search: RoundTripSearch,
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
    api_key: Annotated[str, Depends(get_api_key)],
) -> FareSearchResponse:
    result = await search_fares(search, client, api_key)
    return await add_history(search, result)
