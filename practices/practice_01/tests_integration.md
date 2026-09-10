# Интеграционные тесты

## Тест-кейсы

| ID | Назначение | Предусловия | Действие | Ожидаемый результат | Evidence |
|---|---|---|---|---|---|
| I1 | Сквозная обработка корректного запроса | Мок LLM с ответом "ok"; поднят тестовый FastAPI | POST /api/reviews с {"diff": "..."} | 200 и тело содержит поле комментария | TRAINING_PR.diff: app/api.py:35-38; app/review_service.py:19-22 |
| I2 | Ошибка валидации при отсутствии diff | Поднят тестовый FastAPI | POST /api/reviews с {} | 422 Unprocessable Entity | TRAINING_PR.diff: app/api.py:36-37 |
| I3 | Превышение размера diff | Настроен лимит тела запроса | POST с diff длиной > лимита | 413 Payload Too Large | CASE.md → API-1 |

## Как использовали AI

- Для фиксации базовых интеграционных сценариев на основе diff и правил CASE; запись P1-03 в prompts.md.
