"""Read-only MCP access to the flight search history. Run with stdio."""
import os
import json
import sqlite3
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .history import DATABASE_PATH
from .price_math import price_change

mcp = FastMCP("flight-history")
SearchId = Annotated[int, Field(gt=0, strict=True)]


def compare_saved_prices(
    database_path: Path, current_search_id: int | None = None,
    previous_search_id: int | None = None,
) -> dict[str, Any]:
    if not database_path.is_file():
        raise ValueError("history_missing: История ещё не создана. Выполните поиск в приложении.")
    try:
        with closing(sqlite3.connect(database_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN")  # One consistent snapshot for both rows.
            current = db.execute(
                "SELECT * FROM fare_searches WHERE id = ?", (current_search_id,)
            ).fetchone() if current_search_id is not None else db.execute(
                "SELECT * FROM fare_searches ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if current is None:
                raise ValueError("search_not_found: Текущий поиск не найден.")
            previous = db.execute(
                "SELECT * FROM fare_searches WHERE id = ?", (previous_search_id,)
            ).fetchone() if previous_search_id is not None else db.execute(
                "SELECT * FROM fare_searches WHERE search_key = ? AND id < ? "
                "AND min_price IS NOT NULL ORDER BY id DESC LIMIT 1",
                (current["search_key"], current["id"]),
            ).fetchone()
    except sqlite3.Error as exc:
        raise ValueError("history_unavailable: Не удалось прочитать историю SQLite.") from exc
    if current["min_price"] is None:
        raise ValueError("empty_price: Текущий поиск не содержит цены для сравнения.")
    if previous is None:
        if previous_search_id is not None:
            raise ValueError("search_not_found: Предыдущий поиск не найден.")
        return {"status": "no_previous_price", "current_search_id": current["id"],
                "message": "Предыдущей сопоставимой цены пока нет."}
    if previous["id"] >= current["id"]:
        raise ValueError("invalid_order: Предыдущая запись должна быть раньше текущей.")
    if previous["search_key"] != current["search_key"]:
        raise ValueError("incompatible_searches: Маршрут, даты, рынок или фильтры отличаются.")
    if previous["min_price"] is None:
        raise ValueError("empty_price: Предыдущий поиск не содержит цены для сравнения.")
    if previous["currency"] != current["currency"]:
        raise ValueError("currency_mismatch: Нельзя сравнивать цены в разных валютах.")
    old, new = Decimal(previous["min_price"]), Decimal(current["min_price"])
    difference, percent = price_change(old, new)
    return {
        "status": "compared", "direction": "cheaper" if difference < 0 else "more_expensive" if difference > 0 else "unchanged",
        "previous_search_id": previous["id"], "current_search_id": current["id"],
        "search": json.loads(current["search_key"]),
        "previous_search_at": previous["searched_at"], "current_search_at": current["searched_at"],
        "previous_price": float(old), "current_price": float(new), "currency": current["currency"],
        "difference": difference, "percent_difference": percent,
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False))
def compare_prices(
    current_search_id: SearchId | None = None,
    previous_search_id: SearchId | None = None,
) -> dict[str, Any]:
    """Compare saved flight prices, without live Ignav calls or database writes.

    Omit current_search_id to use the latest search. Omit previous_search_id
    to use the preceding nonempty search with identical parameters.
    Explicit IDs must be positive integers; previous must precede current.
    Returns signed difference and percentage (null if previous price is zero),
    or no_previous_price. Empty prices, incompatible parameters, unknown IDs
    and different currencies produce an MCP tool error.
    """
    path = Path(os.environ.get("FLIGHT_HISTORY_DB", str(DATABASE_PATH)))
    return compare_saved_prices(path, current_search_id, previous_search_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
