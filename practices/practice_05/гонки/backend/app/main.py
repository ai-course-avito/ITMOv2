"""FastAPI-приложение проекта «Гонки».

Фича A (входная валидация): эндпоинт /select-car принимает выбор машинки
(модель + цвет), отклоняет некорректный/слишком большой запрос и только
при успешной валидации "запускает гонку" (в этой заглушке — возвращает
статус старта; реальный запуск движка гонки добавится позже).

Кнопка "Сообщить об ошибке": эндпоинт /report-error принимает текст ошибки
от пользователя (с той же идеей валидации, что и в Фиче A) и пишет его в
лог-файл для диагностики.

Таблица рекордов: /race-results сохраняет время победителя под его именем,
/leaderboard отдаёт лучшие результаты (общие для всех, переживают перезапуск).
Хранилище — JSON-файл на сервере (app/leaderboard.py); если он недоступен
или повреждён, оба эндпоинта отвечают 503 и файл не трогают.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.leaderboard import STORAGE_UNAVAILABLE_DETAIL, LeaderboardStore, StorageError
from app.models import (
    CarSelection,
    ErrorReport,
    Leaderboard,
    RaceResult,
    SaveResultResponse,
)

app = FastAPI(title="Гонки API")

# Разрешаем фронтенду (Vite dev-server) ходить в API при локальной разработке.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ERROR_LOG_PATH = Path(__file__).resolve().parent.parent / "error_reports.log"
LEADERBOARD_PATH = Path(__file__).resolve().parent.parent / "leaderboard.json"

_store = LeaderboardStore(LEADERBOARD_PATH)


def get_store() -> LeaderboardStore:
    """Зависимость эндпоинтов таблицы рекордов (в тестах подменяется на файл в tmp_path)."""
    return _store


StoreDep = Annotated[LeaderboardStore, Depends(get_store)]


@app.exception_handler(StorageError)
async def storage_error_handler(request: Request, exc: StorageError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": STORAGE_UNAVAILABLE_DETAIL})


# Простая защита от слишком большого запроса (фича A: "большой запрос — отклонить").
MAX_BODY_SIZE_BYTES = 2048


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length is not None and int(content_length) > MAX_BODY_SIZE_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": "Запрос слишком большой"},
        )
    return await call_next(request)


@app.post("/select-car")
def select_car(selection: CarSelection) -> dict:
    """Принять выбор машинки и "запустить" гонку.

    До этой точки выполнение доходит только если model_id и color прошли
    валидацию (иначе FastAPI/Pydantic сам вернёт 422, не вызывая этот код) —
    то есть движок гонки не запускается на мусорных данных.
    """
    return {
        "status": "ok",
        "message": (
            f"Машинка «{selection.model_id.value}» ({selection.color.value}) выехала на трассу"
        ),
    }


@app.post("/report-error", status_code=201)
def report_error(report: ErrorReport) -> dict:
    """Принять сообщение об ошибке от пользователя (кнопка "Сообщить об ошибке").

    До этой точки выполнение доходит, только если сообщение не пустое и не
    превышает 500 символов (иначе Pydantic вернёт 422, запись в лог не произойдёт).
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": report.message,
        "model_id": report.model_id.value if report.model_id else None,
        "color": report.color.value if report.color else None,
    }
    with ERROR_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return {"status": "ok", "message": "Спасибо, сообщение об ошибке принято"}


@app.post("/race-results", status_code=201)
def save_race_result(result: RaceResult, store: StoreDep) -> SaveResultResponse:
    """Сохранить время круга победителя под его именем.

    До этой точки доходят только валидные данные (имя нормализовано, время в
    диапазоне) — иначе Pydantic вернёт 422 и хранилище не будет затронуто.
    Повтор того же запроса безопасен: равное время рекорд не меняет.
    """
    return SaveResultResponse(**store.save_result(result.name, result.lap_time_ms))


@app.get("/leaderboard")
def get_leaderboard(store: StoreDep, limit: Annotated[int, Query(ge=1, le=50)] = 10) -> Leaderboard:
    """Таблица рекордов: топ-limit по лучшему времени, число имён и последний результат."""
    return Leaderboard(**store.get_leaderboard(limit))
