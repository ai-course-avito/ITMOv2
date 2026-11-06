"""Тесты таблицы рекордов через API (/race-results, /leaderboard).

Каждый тест работает со своим файлом хранилища в tmp_path (фикстуры в conftest.py);
номера сценариев — из specs/002-leaderboard-logic/spec.md.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

STORAGE_503 = {"detail": "Хранилище рекордов недоступно"}


def post_result(client, name, lap_time_ms):
    return client.post("/race-results", json={"name": name, "lap_time_ms": lap_time_ms})


def read_state(store) -> dict:
    return json.loads(store.path.read_text(encoding="utf-8"))


def seed(store, times: dict[str, int]) -> None:
    """Записать рекорды напрямую в файл; achieved_at растёт в порядке словаря."""
    records = {
        name.casefold(): {
            "name": name,
            "best_time_ms": ms,
            "achieved_at": f"2026-10-27T10:00:00.{i:06d}Z",
        }
        for i, (name, ms) in enumerate(times.items())
    }
    store._save({"version": 1, "records": records, "last_result": None})


# --- US2: сохранение результата под именем ---


def test_first_result_is_new_record(client):
    """US2-1"""
    response = post_result(client, "Камила", 41250)
    assert response.status_code == 201
    assert response.json() == {
        "name": "Камила",
        "lap_time_ms": 41250,
        "best_time_ms": 41250,
        "is_new_record": True,
        "place": 1,
    }


def test_better_time_updates_record(client, store):
    """US2-2"""
    post_result(client, "Камила", 41250)
    body = post_result(client, "Камила", 39800).json()
    assert body["best_time_ms"] == 39800
    assert body["is_new_record"] is True
    assert read_state(store)["records"]["камила"]["best_time_ms"] == 39800


def test_worse_time_keeps_record(client, store):
    """US2-3"""
    post_result(client, "Камила", 39800)
    response = post_result(client, "Камила", 45000)
    assert response.status_code == 201
    assert response.json()["best_time_ms"] == 39800
    assert response.json()["is_new_record"] is False
    assert read_state(store)["records"]["камила"]["best_time_ms"] == 39800


def test_equal_time_keeps_record_and_achieved_at(client, store, clock):
    """US2-4"""
    post_result(client, "Камила", 39800)
    achieved_at = read_state(store)["records"]["камила"]["achieved_at"]
    clock.advance(3600)
    body = post_result(client, "Камила", 39800).json()
    assert body["is_new_record"] is False
    assert read_state(store)["records"]["камила"]["achieved_at"] == achieved_at
    assert achieved_at == "2026-10-28T10:00:00.000000Z"


def test_repeated_request_is_safe(client, store):
    """US2-5"""
    first = post_result(client, "Камила", 41250)
    second = post_result(client, "Камила", 41250)
    assert first.status_code == second.status_code == 201
    assert first.json()["best_time_ms"] == second.json()["best_time_ms"] == 41250
    assert list(read_state(store)["records"]) == ["камила"]


def test_default_name_is_regular_name(client, store):
    """US2-6"""
    response = post_result(client, "Игрок 1", 50000)
    assert response.status_code == 201
    assert read_state(store)["records"]["игрок 1"]["name"] == "Игрок 1"


def test_better_time_other_case_updates_spelling(client, store):
    """US2-8"""
    post_result(client, "Камила", 39800)
    body = post_result(client, "КАМИЛА", 38000).json()
    assert body["name"] == "КАМИЛА"
    assert body["best_time_ms"] == 38000
    assert body["is_new_record"] is True
    records = read_state(store)["records"]
    assert list(records) == ["камила"]
    assert records["камила"]["name"] == "КАМИЛА"


def test_worse_time_other_case_keeps_spelling(client, store):
    """US2-9"""
    post_result(client, "Камила", 39800)
    body = post_result(client, "камила", 45000).json()
    assert body["best_time_ms"] == 39800
    assert body["is_new_record"] is False
    assert read_state(store)["records"]["камила"]["name"] == "Камила"


def test_no_limit_on_number_of_names(client, store):
    """US2-10"""
    seed(store, {f"Игрок {i}": 10000 + i for i in range(1000)})
    response = post_result(client, "Новичок", 5_999_999)
    assert response.status_code == 201
    assert response.json()["place"] == 1001
    assert client.get("/leaderboard").json()["total"] == 1001


def test_name_is_normalized_in_response(client):
    """Edge Cases: пробелы по краям и внутри"""
    assert post_result(client, "  Камила   Салис  ", 41250).json()["name"] == "Камила Салис"
    assert post_result(client, "Аня\tПетрова", 42000).json()["name"] == "Аня Петрова"


def test_last_result_saved_after_each_post(client, store, clock):
    """FR-013a"""
    post_result(client, "Камила", 39800)
    clock.advance(10)
    post_result(client, "Камила", 45000)
    assert read_state(store)["last_result"] == {
        "name": "Камила",
        "lap_time_ms": 45000,
        "finished_at": "2026-10-28T10:00:10.000000Z",
    }


# --- US3: получение таблицы рекордов ---


def test_empty_leaderboard(client):
    """US3-1"""
    response = client.get("/leaderboard")
    assert response.status_code == 200
    assert response.json() == {"entries": [], "total": 0, "last_result": None}


def test_leaderboard_sorted_by_time(client, store):
    """US3-2"""
    seed(store, {"Аня": 50000, "Боря": 40000, "Вика": 45000})
    entries = client.get("/leaderboard").json()["entries"]
    assert [(e["place"], e["name"]) for e in entries] == [(1, "Боря"), (2, "Вика"), (3, "Аня")]
    assert set(entries[0]) == {"place", "name", "best_time_ms", "achieved_at"}


def test_default_limit_is_top_10(client, store):
    """US3-3"""
    seed(store, {f"Игрок {i}": 40000 + i for i in range(15)})
    body = client.get("/leaderboard").json()
    assert [e["place"] for e in body["entries"]] == list(range(1, 11))
    assert body["total"] == 15


def test_custom_limit(client, store):
    """US3-4"""
    seed(store, {f"Игрок {i}": 40000 + i for i in range(15)})
    assert len(client.get("/leaderboard", params={"limit": 3}).json()["entries"]) == 3


def test_equal_time_places_do_not_repeat(client, store):
    """US3-5: «Аня» установила 40 000 раньше «Бори»"""
    seed(store, {"Аня": 40000, "Боря": 40000, "Вика": 41000})
    entries = client.get("/leaderboard").json()["entries"]
    assert [(e["place"], e["name"]) for e in entries] == [(1, "Аня"), (2, "Боря"), (3, "Вика")]


def test_last_result_outside_top_10(client, store, clock):
    """US3-8: время этой гонки, а не лучшее; место по лучшему времени"""
    times = {f"Игрок {i}": 40000 + i for i in range(12)}
    times["Камила"] = 55000
    times["Последний"] = 60000
    seed(store, times)
    post_result(client, "Камила", 58730)
    assert client.get("/leaderboard").json()["last_result"] == {
        "name": "Камила",
        "lap_time_ms": 58730,
        "place": 13,
        "finished_at": "2026-10-28T10:00:00.000000Z",
    }


def test_last_result_overwritten_by_next_post(client):
    """US3-9"""
    post_result(client, "Камила", 41250)
    post_result(client, "Боря", 40000)
    assert client.get("/leaderboard").json()["last_result"]["name"] == "Боря"


def test_last_result_unchanged_after_rejected_post(client):
    """US3-10"""
    post_result(client, "Камила", 41250)
    before = client.get("/leaderboard").json()["last_result"]
    assert post_result(client, "Боря", 2999).status_code == 422
    assert client.get("/leaderboard").json()["last_result"] == before


# --- US4: ошибки и отказ хранилища ---


@pytest.mark.parametrize(
    "body",
    [
        {"name": "   ", "lap_time_ms": 41250},  # US4-1
        {"name": "а" * 21, "lap_time_ms": 41250},  # US4-2
        {"name": "  " + "а" * 21 + "  ", "lap_time_ms": 41250},  # US4-2, после обрезки
        {"name": "Камила", "lap_time_ms": 2999},  # US4-3
        {"name": "Камила", "lap_time_ms": 6_000_000},  # US4-3
        {"name": "Камила", "lap_time_ms": 41250.5},  # US4-4
        {"name": "Камила", "lap_time_ms": "41250"},  # US4-4
        {"name": "Камила", "lap_time_ms": True},  # US4-4
        {"name": "Камила", "lap_time_ms": 41250, "place": 1},  # US4-5
        {"lap_time_ms": 41250},
        {"name": "Камила"},
    ],
)
def test_invalid_result_rejected_and_storage_unchanged(client, store, body):
    post_result(client, "Боря", 40000)
    before = store.path.read_bytes()
    assert client.post("/race-results", json=body).status_code == 422
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("lap_time_ms", [3000, 5_999_999])
def test_boundary_times_accepted(client, lap_time_ms):
    """US4-3: границы диапазона включительно"""
    assert post_result(client, "Камила", lap_time_ms).status_code == 201


def test_twenty_emoji_name_accepted(client):
    """US4-2: длина считается в кодовых точках"""
    response = post_result(client, "🏎" * 20, 41250)
    assert response.status_code == 201
    assert response.json()["name"] == "🏎" * 20


def test_too_large_body_rejected(client, store):
    """US4-6"""
    response = post_result(client, "а" * 3000, 41250)
    assert response.status_code == 413
    assert response.json() == {"detail": "Запрос слишком большой"}
    assert not store.path.exists()


@pytest.mark.parametrize("limit", [0, 51, "abc"])
def test_invalid_limit_rejected(client, limit):
    """US4-7"""
    assert client.get("/leaderboard", params={"limit": limit}).status_code == 422


def test_write_failure_returns_503(client, store, monkeypatch):
    """US4-8"""
    post_result(client, "Камила", 41250)
    before = store.path.read_bytes()

    def broken_replace(src, dst):
        raise OSError("диск недоступен")

    monkeypatch.setattr("app.leaderboard.os.replace", broken_replace)
    response = post_result(client, "Боря", 40000)
    assert response.status_code == 503
    assert response.json() == STORAGE_503
    assert store.path.read_bytes() == before


@pytest.mark.parametrize(
    "content",
    [
        "{не json",
        json.dumps({"version": 2, "records": {}, "last_result": None}),
        json.dumps({"version": 1, "records": {"x": {"name": "X"}}, "last_result": None}),
        json.dumps({"version": 1, "records": [], "last_result": None}),
    ],
)
def test_corrupted_file_returns_503_and_is_untouched(client, store, content):
    """US4-9"""
    store.path.write_text(content, encoding="utf-8")
    before = store.path.read_bytes()

    get_response = client.get("/leaderboard")
    post_response = post_result(client, "Камила", 41250)

    assert get_response.status_code == post_response.status_code == 503
    assert get_response.json() == post_response.json() == STORAGE_503
    assert store.path.read_bytes() == before


def test_missing_file_is_empty_not_error(client, store):
    """US4-10"""
    response = client.get("/leaderboard")
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert not store.path.exists()


def test_concurrent_posts_lose_nothing(client):
    """US4-11"""
    with ThreadPoolExecutor(max_workers=20) as pool:
        responses = list(
            pool.map(lambda i: post_result(client, f"Игрок {i}", 40000 + i), range(20))
        )
    assert [r.status_code for r in responses] == [201] * 20
    assert client.get("/leaderboard").json()["total"] == 20


def test_response_time_with_1000_names(client, store):
    """SC-005: ответ не дольше 0,5 с при 1000 хранимых именах"""
    seed(store, {f"Игрок {i}": 10000 + i for i in range(1000)})

    started = time.perf_counter()
    assert client.get("/leaderboard").status_code == 200
    assert time.perf_counter() - started < 0.5

    started = time.perf_counter()
    assert post_result(client, "Камила", 41250).status_code == 201
    assert time.perf_counter() - started < 0.5
