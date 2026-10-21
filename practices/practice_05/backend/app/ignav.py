import asyncio
import logging
import time
from typing import Any

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from .schemas import FareSearch, FareSearchResponse, Itinerary, Leg, RoundTripSearch

BASE_URL = "https://ignav.com"
CACHE_SECONDS = 180
logger = logging.getLogger(__name__)
_cache: dict[tuple[str, str, str], tuple[float, FareSearchResponse]] = {}
_cache_lock = asyncio.Lock()


def provider_error(response: httpx.Response) -> tuple[str, str]:
    try:
        error = response.json().get("error", {})
        return str(error.get("code", "unknown")), str(error.get("message", ""))
    except (ValueError, AttributeError):
        return "unknown", ""


def normalize_leg(raw: dict[str, Any]) -> Leg:
    segments = raw["segments"]
    return Leg(
        carrier=raw.get("carrier"),
        duration_minutes=raw.get("duration_minutes"),
        segments=segments,
        stops=len(segments) - 1,
    )


def normalize(payload: dict[str, Any], round_trip: bool) -> FareSearchResponse:
    raw_itineraries = payload["itineraries"]
    if not isinstance(raw_itineraries, list):
        raise ValueError("itineraries must be a list")
    itineraries = []
    for raw in raw_itineraries:
        inbound = normalize_leg(raw["inbound"]) if round_trip else None
        itineraries.append(Itinerary(
            ignav_id=raw["ignav_id"],
            price=raw["price"],
            outbound=normalize_leg(raw["outbound"]),
            inbound=inbound,
            requires_self_transfer=raw.get("requires_self_transfer", False),
        ))
    itineraries.sort(key=lambda item: item.price.amount)
    return FareSearchResponse(
        itineraries=itineraries,
        observed_at=payload.get("observed_at"),
        cache_hit=payload.get("cache_hit", False),
    )


async def search_fares(
    search: FareSearch | RoundTripSearch, client: httpx.AsyncClient, api_key: str
) -> FareSearchResponse:
    round_trip = isinstance(search, RoundTripSearch)
    path = "/api/fares/round-trip" if round_trip else "/api/fares/one-way"
    body: dict[str, Any] = {
        "origin": search.origin,
        "destination": search.destination,
        "departure_date": search.departure_date.isoformat(),
        "market": search.market,
    }
    if round_trip:
        body["return_date"] = search.return_date.isoformat()
    if search.direct:
        body["max_stops"] = 0
    if search.max_price is not None:
        body["max_price"] = search.max_price
    cache_key = (api_key, path, str(sorted(body.items())))
    now = time.monotonic()
    async with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1].model_copy(update={"cache_hit": True}, deep=True)

    for attempt in range(3):
        try:
            response = await client.post(
                f"{BASE_URL}{path}", json=body, headers={"X-Api-Key": api_key}
            )
        except httpx.RequestError as exc:
            if attempt < 2:
                await asyncio.sleep(0.25 * 2**attempt)
                continue
            logger.warning("Ignav network failure: %s", type(exc).__name__)
            raise HTTPException(status_code=504, detail="Сервис поиска не ответил. Повторите поиск позже.") from exc

        if response.status_code == 200:
            try:
                result = normalize(response.json(), round_trip)
            except (ValueError, KeyError, TypeError, ValidationError) as exc:
                logger.warning("Invalid Ignav response: %s", type(exc).__name__)
                raise HTTPException(status_code=502, detail="Сервис поиска вернул некорректный ответ.") from exc
            async with _cache_lock:
                _cache[cache_key] = (time.monotonic() + CACHE_SECONDS, result)
            return result.model_copy(deep=True)

        code, _ = provider_error(response)
        if (response.status_code == 424 and code == "unable_to_complete_request") or response.status_code >= 500:
            if attempt < 2:
                await asyncio.sleep(0.25 * 2**attempt)
                continue
        if response.status_code == 400:
            messages = {
                "invalid_airport_code": "Укажите поддерживаемые трёхбуквенные коды аэропортов или городов.",
                "duplicate_route_airports": "Пункты отправления и назначения совпадают.",
                "departure_date_in_past": "Дата вылета уже прошла.",
                "invalid_date_range": "Дата возвращения должна быть не раньше даты вылета.",
                "unsupported_market": "Выбранный рынок не поддерживается Ignav.",
            }
            raise HTTPException(status_code=422, detail=messages.get(code, "Проверьте параметры поиска."))
        if code == "unsupported_search":
            raise HTTPException(status_code=422, detail="Эти даты вне доступного диапазона поиска. Выберите более ранние даты.")
        if response.status_code in (401, 403):
            raise HTTPException(status_code=503, detail="Ключ Ignav недействителен или аккаунт не подтверждён.")
        if response.status_code in (402, 429):
            raise HTTPException(status_code=503, detail="Лимит или оплата Ignav требуют настройки аккаунта.")
        logger.warning("Ignav failed with status %s and code %s", response.status_code, code)
        raise HTTPException(status_code=502, detail="Не удалось получить билеты. Повторите поиск позже.")
    raise HTTPException(status_code=502, detail="Не удалось получить билеты. Повторите поиск позже.")
