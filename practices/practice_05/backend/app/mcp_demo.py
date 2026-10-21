"""Exercise the actual MCP stdio server against a disposable, seeded SQLite DB."""
import argparse
import asyncio
import hashlib
import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .history import search_key
from .schemas import FareSearch


async def demonstrate() -> dict:
    with tempfile.TemporaryDirectory(prefix="flight-mcp-demo-") as directory:
        database = Path(directory) / "history.sqlite3"
        key = search_key(FareSearch(origin="MOW", destination="LED", departure_date="2099-11-10"))
        other_key = search_key(FareSearch(origin="MOW", destination="LED", departure_date="2099-11-11"))
        with sqlite3.connect(database) as db:
            db.execute("CREATE TABLE fare_searches (id INTEGER PRIMARY KEY, searched_at TEXT, search_key TEXT, currency TEXT, min_price TEXT)")
            db.executemany("INSERT INTO fare_searches VALUES (?, ?, ?, ?, ?)", [
                (1, "2099-01-01T00:00:00Z", key, "RUB", "4000"),
                (2, "2099-01-02T00:00:00Z", key, "RUB", "3500"),
                (3, "2099-01-03T00:00:00Z", key, None, None),
                (4, "2099-01-04T00:00:00Z", key, "USD", "50"),
                (5, "2099-01-05T00:00:00Z", other_key, "RUB", "3000"),
            ])
        before = hashlib.sha256(database.read_bytes()).hexdigest()
        server = StdioServerParameters(
            command=sys.executable, args=["-m", "app.mcp_server"],
            cwd=str(Path(__file__).resolve().parents[1]),
            env={"FLIGHT_HISTORY_DB": str(database)},
        )
        records = []
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                tools = await session.list_tools()
                assert "compare_prices" in [tool.name for tool in tools.tools]
                cases = [
                    ("success", {"current_search_id": 2}, False, None),
                    ("first_search", {"current_search_id": 1}, False, None),
                    ("latest_search", {}, False, None),
                    ("invalid_input", {"current_search_id": -1}, True, None),
                    ("empty_price", {"current_search_id": 3}, True, "empty_price"),
                    ("currency_mismatch", {"current_search_id": 4}, True, "currency_mismatch"),
                    ("incompatible_searches", {"current_search_id": 5, "previous_search_id": 2}, True, "incompatible_searches"),
                    ("invalid_order", {"current_search_id": 1, "previous_search_id": 2}, True, "invalid_order"),
                    ("unknown_id", {"current_search_id": 999}, True, "search_not_found"),
                ]
                for name, arguments, expect_error, code in cases:
                    result = await session.call_tool("compare_prices", arguments)
                    response = result.model_dump(mode="json", exclude_none=True)
                    assert result.isError == expect_error, (name, response)
                    if code:
                        assert code in json.dumps(response), (name, response)
                    if name == "success":
                        content = result.structuredContent
                        assert content is not None
                        assert content["difference"] == -500
                        assert content["percent_difference"] == -12.5
                        assert content["direction"] == "cheaper"
                    if name in ("first_search", "latest_search"):
                        assert result.structuredContent["status"] == "no_previous_price"
                    records.append({"case": name, "request": {"method": "tools/call", "params": {"name": "compare_prices", "arguments": arguments}}, "response": response})
        assert hashlib.sha256(database.read_bytes()).hexdigest() == before, "Tool modified the database"
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "transport": "stdio", "data": "synthetic rows in temporary SQLite; no live Ignav requests",
            "initialization": initialized.model_dump(mode="json", exclude_none=True),
            "tools": tools.model_dump(mode="json", exclude_none=True),
            "calls": records, "database_unchanged": True,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = asyncio.run(demonstrate())
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: {len(result['calls'])} real MCP calls over stdio; database unchanged.")
    if args.report:
        print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
