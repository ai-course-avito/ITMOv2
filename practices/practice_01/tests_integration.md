# Integration-проверки

| Связь компонентов | Что может сломаться | Как воспроизводим | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| API ↔ ReviewService ↔ LLM | Формат ответа не соответствует OUT-1 | POST `/api/reviews` с валидным коротким diff | HTTP 200 и JSON с `summary, risks, checks` | OUT-1 в CASE.md; TRAINING_PR.diff показывает текущее несоответствие |
| ReviewService ↔ LLM | Таймаут/исключение LLM приводит к 5xx | Подменить LLM-заглушкой с задержкой >10с/исключением | Не 5xx; контролируемый ответ в формате OUT-1 (summary о таймауте, risks=[]) | REL-1, OUT-1 в CASE.md |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): P1-02; Master Prompt v1.
- Что проверили и исправили сами: связали проверки с правилами REL-1/OUT-1 и текущим кодом из TRAINING_PR.diff.
