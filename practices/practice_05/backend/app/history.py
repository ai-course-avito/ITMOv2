import asyncio
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException

from .price_math import price_change
from .schemas import FareSearch, FareSearchResponse, PriceComparison, RoundTripSearch

DATABASE_PATH = Path(__file__).resolve().parents[1] / "price_history.sqlite3"


def search_key(search: FareSearch | RoundTripSearch) -> str:
    parameters = search.model_dump(mode="json")
    parameters["trip_type"] = "round_trip" if isinstance(search, RoundTripSearch) else "one_way"
    return json.dumps(parameters, sort_keys=True, separators=(",", ":"))


def save_and_compare(
    search: FareSearch | RoundTripSearch, result: FareSearchResponse, database_path: Path
) -> PriceComparison:
    currencies = {item.price.currency for item in result.itineraries}
    if len(currencies) > 1:
        raise HTTPException(
            status_code=502,
            detail="Сервис вернул цены в разных валютах; сравнение невозможно.",
        )
    currency = next(iter(currencies), None)
    price = min((Decimal(str(item.price.amount)) for item in result.itineraries), default=None)
    searched_at = datetime.now(timezone.utc).isoformat()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with closing(sqlite3.connect(database_path, timeout=5)) as connection, connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS fare_searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    searched_at TEXT NOT NULL,
                    search_key TEXT NOT NULL,
                    currency TEXT,
                    min_price TEXT
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS fare_searches_key_id
                ON fare_searches (search_key, id)
            """)
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute("""
                SELECT searched_at, currency, min_price FROM fare_searches
                WHERE search_key = ? AND min_price IS NOT NULL
                ORDER BY id DESC LIMIT 1
            """, (search_key(search),)).fetchone()
            connection.execute("""
                INSERT INTO fare_searches (searched_at, search_key, currency, min_price)
                VALUES (?, ?, ?, ?)
            """, (searched_at, search_key(search), currency, str(price) if price is not None else None))
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Не удалось сохранить историю поиска.") from exc

    base = {
        "previous_price": float(previous[2]) if previous else None,
        "previous_currency": previous[1] if previous else None,
        "previous_search_at": previous[0] if previous else None,
        "current_price": float(price) if price is not None else None,
        "current_currency": currency,
        "current_search_at": searched_at,
    }
    if price is None:
        return PriceComparison(status="no_current_price", **base)
    if previous is None:
        return PriceComparison(status="no_previous_price", **base)
    if previous[1] != currency:
        return PriceComparison(status="currency_mismatch", **base)
    old_price = Decimal(previous[2])
    difference, percent = price_change(old_price, price)
    return PriceComparison(
        status="compared",
        difference=float(difference),
        percent_difference=float(percent) if percent is not None else None,
        **base,
    )


async def add_history(
    search: FareSearch | RoundTripSearch, result: FareSearchResponse,
    database_path: Path | None = None,
) -> FareSearchResponse:
    comparison = await asyncio.to_thread(save_and_compare, search, result, database_path or DATABASE_PATH)
    return result.model_copy(update={"comparison": comparison})
