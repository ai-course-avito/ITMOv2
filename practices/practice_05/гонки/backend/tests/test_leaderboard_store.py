"""Тесты хранилища таблицы рекордов (app/leaderboard.py) без HTTP.

Нормализация имени, ранжирование, сохранение между экземплярами хранилища
(перезапуск сервера) и отказ записи.
"""

import pytest

from app.leaderboard import (
    LeaderboardStore,
    StorageError,
    empty_state,
    name_key,
    normalize_name,
    rank,
)


def test_normalize_name_trims_edges():
    assert normalize_name("  Камила  ") == "Камила"


def test_normalize_name_collapses_inner_spaces():
    assert normalize_name("Камила   Салис") == "Камила Салис"


def test_normalize_name_treats_tab_as_space():
    assert normalize_name("Камила\tСалис") == "Камила Салис"


def test_name_key_ignores_case():
    assert name_key("КАМИЛА") == name_key("камила") == name_key("Камила")


def test_rank_equal_time_earlier_record_is_higher():
    records = {
        "боря": {
            "name": "Боря",
            "best_time_ms": 40000,
            "achieved_at": "2026-10-28T11:00:00.000000Z",
        },
        "аня": {"name": "Аня", "best_time_ms": 40000, "achieved_at": "2026-10-28T10:00:00.000000Z"},
        "вика": {
            "name": "Вика",
            "best_time_ms": 39000,
            "achieved_at": "2026-10-28T12:00:00.000000Z",
        },
    }
    assert rank(records) == ["вика", "аня", "боря"]


def test_load_without_file_returns_empty_state(store):
    assert store._load() == empty_state()


def test_save_and_load_roundtrip(store):
    state = {
        "version": 1,
        "records": {
            "камила": {
                "name": "Камила",
                "best_time_ms": 41250,
                "achieved_at": "2026-10-28T10:00:00.000000Z",
            }
        },
        "last_result": {
            "name": "Камила",
            "lap_time_ms": 41250,
            "finished_at": "2026-10-28T10:00:00.000000Z",
        },
    }
    store._save(state)
    assert store._load() == state


def test_restarted_store_sees_same_leaderboard(store, clock):
    """US3-6: новый экземпляр хранилища на том же файле (перезапуск сервера)."""
    store.save_result("Камила", 41250)
    clock.advance(60)
    store.save_result("Боря", 40000)
    before = store.get_leaderboard(10)

    restarted = LeaderboardStore(store.path, clock=clock.now)
    assert restarted.get_leaderboard(10) == before
    assert before["last_result"]["name"] == "Боря"


def test_second_store_sees_writes_of_first(store, clock):
    """US3-7: запись через одно хранилище видна при чтении через другое."""
    other = LeaderboardStore(store.path, clock=clock.now)
    store.save_result("Камила", 41250)
    board = other.get_leaderboard(10)
    assert [e["name"] for e in board["entries"]] == ["Камила"]


def test_failed_replace_keeps_old_file_and_no_temp_left(store, monkeypatch):
    """US4-8: сбой атомарной замены — StorageError, прежний файл цел, временных файлов нет."""
    store.save_result("Камила", 41250)
    before = store.path.read_bytes()

    def broken_replace(src, dst):
        raise OSError("диск недоступен")

    monkeypatch.setattr("app.leaderboard.os.replace", broken_replace)
    with pytest.raises(StorageError):
        store.save_result("Боря", 40000)

    assert store.path.read_bytes() == before
    assert sorted(p.name for p in store.path.parent.iterdir()) == ["leaderboard.json"]
