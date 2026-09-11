# Integration-проверки

| Связь компонентов | Что может сломаться | Как воспроизводим | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| FastAPI route ↔ `ReviewService` | `KeyError` на `payload["diff"]` превращается в 500 вместо 422 | `POST /api/reviews` без поля `diff` через `TestClient` | 422 с телом, описывающим ошибку валидации | `tests/test_api.py::test_missing_diff_integration` |
| FastAPI route ↔ `LLM` (через `ReviewService`) | Исключение из `llm.generate` пробрасывается как непрозрачный 500 | Мок `LLM`, бросающий исключение при вызове | Контролируемый 5xx с понятным телом, без stack trace клиенту | `tests/test_api.py::test_llm_failure_returns_controlled_error` |
| `response_model` ↔ реальный ответ | Ответ не соответствует объявленной схеме `ReviewResponse` | `POST /api/reviews` с валидным `diff` | Ответ `201`, тело соответствует `ReviewResponse{comment: string}` | `tests/test_api.py::test_response_matches_schema` |
| Валидатор размера ↔ route | `diff` длиннее лимита проходит валидацию и уходит в LLM | `POST /api/reviews` с `diff` в 20 001 символ через `TestClient` | 413, вызов `llm.generate` не происходит | `tests/test_api.py::test_diff_over_limit_rejected` |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): P1-02.
- Что проверили и исправили сами: для каждой строки таблицы сверили, что «что может сломаться» — это реальный риск из `P1_02.txt`, а не гипотетический сценарий, и что ожидаемый результат воспроизводим через `TestClient` без реального обращения к внешнему LLM.
