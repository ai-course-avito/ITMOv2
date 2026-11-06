"""Модели данных проекта «Гонки»."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
