"""Модели данных проекта «Гонки»."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.leaderboard import normalize_name

MAX_NAME_LENGTH = 20


class CarModel(str, Enum):
    """Разрешённые 3 модельки машинок."""

    RACER = "racer"
    DRIFTER = "drifter"
    TANK = "tank"


class CarColor(str, Enum):
    """Разрешённые цвета (пастельная палитра: красная, жёлтая, фиолетовая)."""

    PURPLE = "purple"
    RED = "red"
    YELLOW = "yellow"


class CarSelection(BaseModel):
    """Вход пользователя на экране выбора машинки.

    extra="forbid" — лишние/незнакомые поля в запросе отклоняются автоматически.
    Enum-поля — неизвестные model_id/color отклоняются автоматически (422),
    гонка в этом случае не запускается (обработчик не вызывается).
    """

    model_config = ConfigDict(extra="forbid")

    model_id: CarModel
    color: CarColor


class ErrorReport(BaseModel):
    """Вход с кнопки "Сообщить об ошибке".

    Валидация (та же идея, что и в Фиче A): пустое или слишком длинное
    сообщение отклоняется ещё до того, как что-либо будет сохранено/отправлено
    дальше на диагностику.
    """

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=500)
    # Необязательный контекст — что было выбрано на момент ошибки (если есть).
    model_id: CarModel | None = None
    color: CarColor | None = None

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("сообщение не может быть пустым/состоять из пробелов")
        return stripped


class RaceResult(BaseModel):
    """Результат гонки — время круга победителя под его именем (POST /race-results).

    Имя нормализуется (края обрезаны, серии пробельных символов → один пробел) и
    после этого должно быть длиной 1–20 символов (кодовых точек). Время — только
    целое число JSON в миллисекундах: строка, дробное или bool отклоняются (422),
    хранилище в этом случае не трогается.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    lap_time_ms: int = Field(strict=True, ge=3000, le=5_999_999)

    @field_validator("name")
    @classmethod
    def name_must_fit_after_normalization(cls, value: str) -> str:
        normalized = normalize_name(value)
        if not 1 <= len(normalized) <= MAX_NAME_LENGTH:
            raise ValueError(f"имя должно быть длиной 1–{MAX_NAME_LENGTH} символов")
        return normalized


class SaveResultResponse(BaseModel):
    """Ответ на сохранение результата."""

    name: str
    lap_time_ms: int
    best_time_ms: int
    is_new_record: bool
    place: int


class LeaderboardEntry(BaseModel):
    """Строка таблицы рекордов: лучшее время имени."""

    place: int
    name: str
    best_time_ms: int
    achieved_at: str


class LastResultOut(BaseModel):
    """Последний сохранённый результат (общий для всех клиентов)."""

    name: str
    lap_time_ms: int
    place: int
    finished_at: str


class Leaderboard(BaseModel):
    """Ответ GET /leaderboard."""

    entries: list[LeaderboardEntry]
    total: int
    last_result: LastResultOut | None
