# Integration-проверки

| Связь компонентов | Что может сломаться | Как воспроизводим | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| API ↔ Pydantic | Нет схемы, KeyError | POST {} | 422 Unprocessable Entity | context.md, TRAINING_PR.diff |
| API ↔ ReviewService | >20k символов | POST длинный diff | 413 Payload Too Large | CASE.md API-1 |
| ReviewService ↔ LLM | Таймаут/ошибка | мок generate с TimeoutError | Контролируемая ошибка | CASE.md REL-1 |
| ReviewService ↔ LLM | Утечка секретов | diff с token=abc | В prompt [REDACTED] | CASE.md SEC-1 |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): P1-02.
- Что проверили и исправили сами: Связали проверки с SEC-1, API-1, REL-1.
