# Integration-проверки

Файл ведёт OpenCode. Интеграционный уровень проверяет связки FastAPI ↔ Pydantic ↔ ReviewService ↔ LLM‑адаптер.

| Связь компонентов | Что может сломаться | Как воспроизводим | Ожидаемый результат | Подтверждение |
|---|---|---|---|---|
| FastAPI ↔ Pydantic (вход) | Невалидный body не даёт 422 | POST без diff | 422 Unprocessable Entity с деталями | curl/pytest: assert status 422 |
| ReviewService ↔ LLM | Исключение не маппится | Мок LLM: raise TimeoutError | 502 Bad Gateway | pytest with TestClient |
| ReviewService ↔ нормализация | Более 3 рисков в сырых данных | Мок LLM: вернуть список из 5 | Срез до 3 в ответе | assert len<=3 |
| response_model | Ответ не соответствует схеме | Валидный POST | Поля summary, risks, типы корректны | pydantic.parse_obj_as или response_model в FastAPI |

## Как использовали AI

- Для чего: определить критичные интеграции и негативные пути.
- Тип промпта: master prompt.
- Строка в [`prompts.md`](prompts.md): P1-02, P1-03.
- Что проверил студент и какие исправления поручил агенту: сценарии выровнены со статусами и контрактом, исключён jq из команд.
