#!/usr/bin/env python3
"""Reproducible, offline verification of practice_05 features A and B."""

import argparse
import asyncio
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[4]
BACKEND = PROJECT / "backend"
FRONTEND = PROJECT / "frontend"


def run_command(command: list[str], cwd: Path) -> tuple[bool, str]:
    environment = os.environ.copy()
    environment.pop("IGNAV_API_KEY", None)
    try:
        result = subprocess.run(
            command, cwd=cwd, env=environment, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return result.returncode == 0, result.stdout.strip()


def smoke_scenario() -> tuple[bool, str]:
    import httpx
    from fastapi.testclient import TestClient

    sys.path.insert(0, str(BACKEND))
    import app.history as history
    from app.ignav import _cache
    from app.main import app, get_api_key, get_http_client

    prices = [4000, 3500]
    upstream_calls = 0

    def itinerary(amount: int) -> dict:
        return {
            "ignav_id": f"mock-{amount}",
            "price": {"amount": amount, "currency": "RUB"},
            "outbound": {"carrier": "Test Air", "segments": [{
                "departure_airport": "SVO",
                "departure_time_local": "2099-11-10T08:00:00",
                "arrival_airport": "LED",
                "arrival_time_local": "2099-11-10T09:30:00",
            }]},
        }

    def upstream(_: httpx.Request) -> httpx.Response:
        nonlocal upstream_calls
        upstream_calls += 1
        if upstream_calls == 1:
            return httpx.Response(200, json={"itineraries": [itinerary(prices[0])]})
        if upstream_calls == 2:
            return httpx.Response(200, json={"itineraries": [itinerary(prices[1])]})
        return httpx.Response(200, json={"itineraries": []})

    old_path = history.DATABASE_PATH
    _cache.clear()
    with tempfile.TemporaryDirectory(prefix="flight-feature-check-") as directory:
        history.DATABASE_PATH = Path(directory) / "history.sqlite3"
        client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        app.dependency_overrides[get_http_client] = lambda: client
        app.dependency_overrides[get_api_key] = lambda: "offline-skill-test"
        try:
            with TestClient(app) as api:
                body = {"origin": "MOW", "destination": "LED", "departure_date": "2099-11-10"}
                first = api.post("/api/fares/one-way", json=body)
                _cache.clear()  # Simulate a later search after the short fare-cache window.
                second = api.post("/api/fares/one-way", json=body)
                _cache.clear()
                empty = api.post("/api/fares/one-way", json=body)
                invalid = api.post("/api/fares/one-way", json={**body, "origin": "MO"})
            with sqlite3.connect(history.DATABASE_PATH) as database:
                rows = database.execute(
                    "SELECT currency, min_price FROM fare_searches ORDER BY id"
                ).fetchall()
        finally:
            app.dependency_overrides.clear()
            asyncio.run(client.aclose())
            history.DATABASE_PATH = old_path
            _cache.clear()

    first_state = first.json().get("comparison", {}).get("status") if first.status_code == 200 else None
    second_comparison = second.json().get("comparison", {}) if second.status_code == 200 else {}
    empty_state = empty.json().get("comparison", {}).get("status") if empty.status_code == 200 else None
    passed = (
        first_state == "no_previous_price"
        and second_comparison.get("status") == "compared"
        and second_comparison.get("difference") == -500
        and second_comparison.get("percent_difference") == -12.5
        and empty_state == "no_current_price"
        and invalid.status_code == 422
        and upstream_calls == 3
        and rows == [("RUB", "4000.0"), ("RUB", "3500.0"), (None, None)]
    )
    details = (
        f"first={first_state}, second={second_comparison.get('status')}, "
        f"difference={second_comparison.get('difference')} RUB "
        f"({second_comparison.get('percent_difference')}%), empty={empty_state}, "
        f"invalid_http={invalid.status_code}, mocked_upstream_calls={upstream_calls}, "
        f"saved_rows={len(rows)}"
    )
    return passed, details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="Write a Markdown verification report")
    args = parser.parse_args()

    python = BACKEND / ".venv" / "bin" / "python"
    checks = [
        ("Backend tests", *run_command([str(python), "-m", "pytest", "-q"], BACKEND)),
        ("After-edit hook tests", *run_command(["node", "--test", "scripts/tests/verify-after-edit.test.mjs"], PROJECT)),
        ("Frontend build", *run_command(["npm", "run", "build"], FRONTEND)),
    ]
    if checks[0][1]:
        try:
            checks.append(("Offline A/B scenario", *smoke_scenario()))
        except Exception as exc:
            checks.append(("Offline A/B scenario", False, f"{type(exc).__name__}: {exc}"))
    else:
        checks.append(("Offline A/B scenario", False, "Skipped because backend tests failed."))

    report = ["# Flight feature verification", "", "Mocked Ignav; isolated temporary SQLite; no live fare request.", ""]
    for name, passed, details in checks:
        report.extend([f"## {name}: {'PASS' if passed else 'FAIL'}", "", "```text", details, "```", ""])
    output = "\n".join(report)
    print(output)
    if args.report:
        report_path = args.report if args.report.is_absolute() else PROJECT / args.report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(output, encoding="utf-8")
        print(f"Report: {report_path}")
    return 0 if all(passed for _, passed, _ in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
