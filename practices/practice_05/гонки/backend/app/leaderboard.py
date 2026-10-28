"""Таблица рекордов гонки: нормализация имени, ранжирование и хранилище.

Рекорды хранятся в одном JSON-файле на сервере — общем для всех клиентов
и переживающем перезапуск. Запись атомарная (временный файл + os.replace),
одновременные запросы сериализуются блокировкой. Повреждённый файл не
перезаписывается: любая операция с ним поднимает StorageError (→ 503).
"""

import json
import os
import tempfile
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

STORAGE_UNAVAILABLE_DETAIL = "Хранилище рекордов недоступно"


class StorageError(Exception):
    """Хранилище рекордов нельзя прочитать или записать (файл повреждён, нет доступа)."""


def empty_state() -> dict:
    """Состояние пустого хранилища (файла ещё нет)."""
    return {"version": 1, "records": {}, "last_result": None}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_ts(dt: datetime) -> str:
    """UTC в фиксированном формате ISO 8601 с микросекундами и суффиксом Z.

    Формат фиксированной ширины — поэтому сравнение строк совпадает с хронологическим
    (на этом держится порядок мест при равном времени).
    """
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def normalize_name(value: str) -> str:
    """Обрезать пробельные символы по краям и схлопнуть каждую серию внутри в один пробел.

    str.split() без аргументов делит по любым пробельным символам Unicode
    (str.isspace), включая табуляцию и перевод строки (contract.md 2.1).
    """
    return " ".join(value.split())


def name_key(name: str) -> str:
    """Ключ имени: регистр не учитывается — «Камила» и «камила» один рекорд."""
    return name.casefold()


def _is_int(value) -> bool:
    # bool — подкласс int в Python, но в файле рекордов это ошибка структуры.
    return isinstance(value, int) and not isinstance(value, bool)


def validate_state(data) -> dict:
    """Проверить структуру прочитанного файла; при любом отклонении — StorageError."""
    if not isinstance(data, dict) or data.get("version") != 1:
        raise StorageError("неизвестный формат файла рекордов")

    records = data.get("records")
    if not isinstance(records, dict):
        raise StorageError("records должен быть объектом")
    for record in records.values():
        if not (
            isinstance(record, dict)
            and isinstance(record.get("name"), str)
            and _is_int(record.get("best_time_ms"))
            and isinstance(record.get("achieved_at"), str)
        ):
            raise StorageError("повреждённая запись рекорда")

    last = data.get("last_result")
    if last is not None and not (
        isinstance(last, dict)
        and isinstance(last.get("name"), str)
        and _is_int(last.get("lap_time_ms"))
        and isinstance(last.get("finished_at"), str)
    ):
        raise StorageError("повреждённый последний результат")

    return data


def rank(records: dict) -> list[str]:
    """Ключи имён по местам: время по возрастанию, при равенстве — кто раньше установил.

    Ключ — третий критерий только для детерминированности; номера мест не повторяются.
    """
    return sorted(
        records,
        key=lambda key: (records[key]["best_time_ms"], records[key]["achieved_at"], key),
    )


class LeaderboardStore:
    """Хранилище рекордов в одном JSON-файле."""

    def __init__(self, path: Path, clock: Callable[[], datetime] = utc_now) -> None:
        self.path = Path(path)
        self._clock = clock
        self._lock = threading.Lock()

    def _load(self) -> dict:
        if not self.path.exists():
            return empty_state()
        try:
            with self.path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StorageError(str(exc)) from exc
        return validate_state(data)

    def _save(self, state: dict) -> None:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.path.parent, suffix=".tmp", delete=False
            ) as f:
                tmp_path = f.name
                json.dump(state, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.path)
        except Exception as exc:
            if tmp_path is not None and os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise StorageError(str(exc)) from exc

    def save_result(self, name: str, lap_time_ms: int) -> dict:
        """Сохранить результат: обновить рекорд имени (только при строго лучшем времени)
        и последний результат. Имя должно быть уже нормализовано.
        """
        with self._lock:
            state = self._load()
            records = state["records"]
            key = name_key(name)
            now = format_ts(self._clock())

            record = records.get(key)
            is_new_record = record is None or lap_time_ms < record["best_time_ms"]
            if is_new_record:
                records[key] = {"name": name, "best_time_ms": lap_time_ms, "achieved_at": now}
            state["last_result"] = {"name": name, "lap_time_ms": lap_time_ms, "finished_at": now}

            self._save(state)
            return {
                "name": name,
                "lap_time_ms": lap_time_ms,
                "best_time_ms": records[key]["best_time_ms"],
                "is_new_record": is_new_record,
                "place": rank(records).index(key) + 1,
            }

    def get_leaderboard(self, limit: int) -> dict:
        """Топ-limit по лучшему времени, число имён и последний результат с текущим местом."""
        with self._lock:
            state = self._load()
        records = state["records"]
        order = rank(records)
        entries = [{"place": i + 1, **records[key]} for i, key in enumerate(order[:limit])]

        last = state["last_result"]
        last_result = None
        if last is not None:
            last_result = {**last, "place": order.index(name_key(last["name"])) + 1}

        return {"entries": entries, "total": len(records), "last_result": last_result}
