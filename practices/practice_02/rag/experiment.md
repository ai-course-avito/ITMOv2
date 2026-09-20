# RAG

- Вопрос к источникам:

Какие ошибки в изменениях TRAINING_PR.diff и что нужно исправить.

## Разрешённые источники

| Файл или документ | Зачем нужен | Какой фрагмент используем |
|---|---|---|
| practices/practice_01/TRAINING_PR.diff | Единый источник правок | Строки 1-22 (app/review_service.py), 23-37 (app/api.py) |
| practices/practice_01/CASE.md | Правила репозитория (API-1, REL-1, OUT-1 и др.) | Ссылки на коды правил без номеров строк |

## Запрос

Определить ошибки и рискованные места в изменениях и предложить минимальные правки.

## Ответ со ссылками на источники

1. Отсутствует валидация тела запроса и небезопасный доступ к ключу diff в обработчике create_review. В текущем виде `payload["diff"]` приведёт к `KeyError` при отсутствии ключа и не позволяет FastAPI автоматически валидировать вход. Фрагмент: practices/practice_01/TRAINING_PR.diff, строки 35-38 (app/api.py). Также предусмотреть ограничение размера diff по CASE.md: API-1.

   Что изменить: ввести Pydantic-модель для тела запроса и использовать её в обработчике. Например:

   ```python
   from pydantic import BaseModel

   class ReviewRequest(BaseModel):
       diff: str

   @app.post("/api/reviews")
   def create_review(payload: ReviewRequest) -> dict[str, str]:
       return review_service.review(payload.diff)
   ```

2. Неопределённая схема ответа. Возврат «сырых» словарей усложняет контракт API и документирование. Фрагменты: practices/practice_01/TRAINING_PR.diff, строки 19-22 (app/review_service.py) и 35-38 (app/api.py).

   Что изменить: по возможности зафиксировать схему ответа через Pydantic-модель, чтобы OpenAPI описывал контракт. Например:

   ```python
   class ReviewResponse(BaseModel):
       comment: str

   @app.post("/api/reviews", response_model=ReviewResponse)
   def create_review(payload: ReviewRequest) -> ReviewResponse:
       return ReviewResponse(**review_service.review(payload.diff))
   ```

3. Совместимость аннотаций с версией Python. Использование `dict[str, str]` требует Python ≥ 3.9. Если целевая версия ниже, это вызовет синтаксическую ошибку. Фрагменты: practices/practice_01/TRAINING_PR.diff, строки 19-22 и 35-38.

   Что изменить при необходимости: заменить на `Dict[str, str]` и добавить `from typing import Dict`. Это изменение зависит от целевой версии интерпретатора.

Примечание: изменения в `LLM.generate` (перевод однострочного объявления на многострочное с `...`) не несут функциональной нагрузки и не являются ошибкой. Фрагмент: practices/practice_01/TRAINING_PR.diff, строки 10-13.

## Что изменили в исходном артефакте

- Файл и раздел:
  - app/api.py, обработчик `create_review`
  - app/review_service.py, метод `review`
- Изменение:
  - Предложено ввести Pydantic-модель `ReviewRequest` для тела запроса и, по возможности, `ReviewResponse` для ответа; заменить небезопасный доступ `payload["diff"]` на строго типизированный доступ `payload.diff`.
- Как проверили ссылки:
  - Сопоставлены рекомендации с конкретными строками TRAINING_PR.diff: 35-38 (добавленный маршрут в app/api.py), 19-22 (добавленный метод `review` в app/review_service.py), 10-13 (изменение объявления `LLM.generate`).
- Что отклонили как неподтверждённое:
  - Обязательная замена `dict[str, str]` на `Dict[str, str]` — зависит от версии Python и не подтверждена источником.
  - Изменение пути маршрута или DI-паттернов для `review_service` — нет данных в предоставленном диффе.
