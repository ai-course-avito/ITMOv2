import asyncio
from contextlib import contextmanager
from typing import Callable, Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

import app.main as main_module
import app.history as history_module
from app.ignav import _cache
from app.main import app, get_api_key, get_http_client

DATE = "2099-11-10"
BASE = {"origin": "MOW", "destination": "LED", "departure_date": DATE}


@pytest.fixture(autouse=True)
def isolated_history(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(history_module, "DATABASE_PATH", tmp_path / "history.sqlite3")


@contextmanager
def client_with_upstream(handler: Callable[[httpx.Request], httpx.Response]) -> Iterator[TestClient]:
    upstream = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app.dependency_overrides[get_http_client] = lambda: upstream
    _cache.clear()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        _cache.clear()
        asyncio.run(upstream.aclose())


def leg(stops: int = 0) -> dict:
    segments = [{
        "marketing_carrier_code": "SU", "departure_airport": "SVO",
        "departure_time_local": "2099-11-10T08:00:00", "arrival_airport": "LED",
        "arrival_time_local": "2099-11-10T09:30:00",
    }]
    if stops:
        segments = [segments[0], {**segments[0], "departure_airport": "KZN"}]
    return {"carrier": "Аэрофлот", "segments": segments, "duration_minutes": 90}


def itinerary(amount: int, stops: int = 0) -> dict:
    return {"ignav_id": f"id-{amount}", "price": {"amount": amount, "currency": "RUB"}, "outbound": leg(stops)}


def test_one_way_search_sorts_normalizes_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGNAV_API_KEY", "test-key")
    calls = 0

    def upstream(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url == "https://ignav.com/api/fares/one-way"
        assert request.headers["X-Api-Key"] == "test-key"
        assert request.headers["Content-Type"] == "application/json"
        assert request.content
        assert b'"max_stops":0' in request.content
        assert b'"max_price":5000' in request.content
        assert b'"market":"RU"' in request.content
        return httpx.Response(200, json={"itineraries": [itinerary(4000), itinerary(3000, 1)]})

    with client_with_upstream(upstream) as client:
        body = {**BASE, "direct": True, "max_price": 5000}
        first = client.post("/api/fares/one-way", json=body)
        second = client.post("/api/fares/one-way", json=body)
    assert first.status_code == second.status_code == 200
    assert [offer["price"]["amount"] for offer in first.json()["itineraries"]] == [3000, 4000]
    assert first.json()["itineraries"][0]["outbound"]["stops"] == 1
    assert calls == 1


def test_round_trip_and_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGNAV_API_KEY", "test-key")

    def upstream(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/fares/round-trip"
        assert b'"return_date":"2099-11-15"' in request.content
        return httpx.Response(200, json={"itineraries": []})

    with client_with_upstream(upstream) as client:
        response = client.post("/api/fares/round-trip", json={**BASE, "return_date": "2099-11-15"})
    assert response.status_code == 200
    assert response.json()["itineraries"] == []


def test_round_trip_preserves_both_legs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGNAV_API_KEY", "test-key")

    def upstream(_: httpx.Request) -> httpx.Response:
        fare = itinerary(9000)
        fare["inbound"] = leg(1)
        return httpx.Response(200, json={"itineraries": [fare]})

    with client_with_upstream(upstream) as client:
        response = client.post("/api/fares/round-trip", json={**BASE, "return_date": "2099-11-15"})
    assert response.status_code == 200
    offer = response.json()["itineraries"][0]
    assert offer["outbound"]["stops"] == 0
    assert offer["inbound"]["stops"] == 1
    assert offer["ignav_id"] == "id-9000"


@pytest.mark.parametrize("body", [
    {**BASE, "origin": "MO"},
    {**BASE, "destination": "MOW"},
    {**BASE, "departure_date": "2099-11"},
    {**BASE, "departure_date": "2099-13-01"},
    {**BASE, "departure_date": 4098384000},
    {**BASE, "max_price": 0},
])
def test_invalid_input_does_not_reach_ignav(body: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGNAV_API_KEY", "test-key")
    with client_with_upstream(lambda _: (_ for _ in ()).throw(AssertionError("unexpected call"))) as client:
        response = client.post("/api/fares/one-way", json=body)
    assert response.status_code == 422


def test_invalid_return_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGNAV_API_KEY", "test-key")
    with client_with_upstream(lambda _: (_ for _ in ()).throw(AssertionError("unexpected call"))) as client:
        response = client.post("/api/fares/round-trip", json={**BASE, "return_date": "2099-11-09"})
    assert response.status_code == 422


def test_missing_key(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("IGNAV_API_KEY", raising=False)
    monkeypatch.setattr(main_module, "ENV_FILE", tmp_path / ".env")
    with client_with_upstream(lambda _: (_ for _ in ()).throw(AssertionError("unexpected call"))) as client:
        response = client.post("/api/fares/one-way", json=BASE)
    assert response.status_code == 503
    assert "не настроен" in response.json()["detail"]


def test_local_env_key(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("IGNAV_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("IGNAV_API_KEY=test-local-key\n", encoding="utf-8")
    monkeypatch.setattr(main_module, "ENV_FILE", env_file)
    assert get_api_key() == "test-local-key"


def test_provider_input_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGNAV_API_KEY", "test-key")
    calls = 0

    def upstream(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": {"code": "invalid_airport_code", "message": "invalid"}})

    with client_with_upstream(upstream) as client:
        response = client.post("/api/fares/one-way", json=BASE)
    assert response.status_code == 422
    assert calls == 1


def test_unable_to_complete_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGNAV_API_KEY", "test-key")
    calls = 0

    def upstream(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(424, json={"error": {"code": "unable_to_complete_request"}})
        return httpx.Response(200, json={"itineraries": []})

    with client_with_upstream(upstream) as client:
        response = client.post("/api/fares/one-way", json=BASE)
    assert response.status_code == 200
    assert calls == 2


def test_unsupported_search_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGNAV_API_KEY", "test-key")
    calls = 0

    def upstream(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(424, json={"error": {"code": "unsupported_search"}})

    with client_with_upstream(upstream) as client:
        response = client.post("/api/fares/one-way", json=BASE)
    assert response.status_code == 422
    assert calls == 1


def test_price_history_comparison_and_filter_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGNAV_API_KEY", "test-key")
    prices = iter([4000, 3500, 2500])

    def upstream(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"itineraries": [itinerary(next(prices))]})

    with client_with_upstream(upstream) as client:
        first = client.post("/api/fares/one-way", json=BASE).json()["comparison"]
        _cache.clear()
        second = client.post("/api/fares/one-way", json=BASE).json()["comparison"]
        _cache.clear()
        different_filter = client.post("/api/fares/one-way", json={**BASE, "max_price": 5000}).json()["comparison"]
    assert first["status"] == "no_previous_price"
    assert second["status"] == "compared"
    assert second["previous_price"] == 4000
    assert second["current_price"] == 3500
    assert second["difference"] == -500
    assert second["percent_difference"] == -12.5
    assert different_filter["status"] == "no_previous_price"


def test_empty_search_is_saved_but_not_used_as_price(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGNAV_API_KEY", "test-key")
    responses = iter([[itinerary(4000)], [], [itinerary(3500)]])

    def upstream(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"itineraries": next(responses)})

    with client_with_upstream(upstream) as client:
        client.post("/api/fares/one-way", json=BASE)
        _cache.clear()
        empty = client.post("/api/fares/one-way", json=BASE).json()["comparison"]
        _cache.clear()
        after_empty = client.post("/api/fares/one-way", json=BASE).json()["comparison"]
    assert empty["status"] == "no_current_price"
    assert after_empty["previous_price"] == 4000
    assert after_empty["difference"] == -500
    with history_module.sqlite3.connect(history_module.DATABASE_PATH) as connection:
        rows = connection.execute("SELECT min_price FROM fare_searches ORDER BY id").fetchall()
    assert rows == [("4000.0",), (None,), ("3500.0",)]


def test_currency_mismatch_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGNAV_API_KEY", "test-key")
    currencies = iter(["RUB", "USD"])

    def upstream(_: httpx.Request) -> httpx.Response:
        fare = itinerary(4000)
        fare["price"]["currency"] = next(currencies)
        return httpx.Response(200, json={"itineraries": [fare]})

    with client_with_upstream(upstream) as client:
        client.post("/api/fares/one-way", json=BASE)
        _cache.clear()
        comparison = client.post("/api/fares/one-way", json=BASE).json()["comparison"]
    assert comparison["status"] == "currency_mismatch"
    assert comparison["difference"] is None


def test_cached_search_still_creates_history_record(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGNAV_API_KEY", "test-key")
    calls = 0

    def upstream(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"itineraries": [itinerary(4000)]})

    with client_with_upstream(upstream) as client:
        client.post("/api/fares/one-way", json=BASE)
        second = client.post("/api/fares/one-way", json=BASE).json()
    assert calls == 1
    assert second["cache_hit"] is True
    assert second["comparison"]["status"] == "compared"
    assert second["comparison"]["difference"] == 0


def test_first_empty_search_does_not_become_comparison_price(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGNAV_API_KEY", "test-key")
    responses = iter([[], [itinerary(3500)]])

    with client_with_upstream(lambda _: httpx.Response(200, json={"itineraries": next(responses)})) as client:
        empty = client.post("/api/fares/one-way", json=BASE).json()["comparison"]
        _cache.clear()
        next_search = client.post("/api/fares/one-way", json=BASE).json()["comparison"]
    assert empty["status"] == "no_current_price"
    assert next_search["status"] == "no_previous_price"


def test_mixed_currencies_fail_without_saving(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IGNAV_API_KEY", "test-key")
    rub = itinerary(4000)
    usd = itinerary(100)
    usd["price"]["currency"] = "USD"

    with client_with_upstream(lambda _: httpx.Response(200, json={"itineraries": [rub, usd]})) as client:
        response = client.post("/api/fares/one-way", json=BASE)
    assert response.status_code == 502
    assert "разных валютах" in response.json()["detail"]
    assert not history_module.DATABASE_PATH.exists()
