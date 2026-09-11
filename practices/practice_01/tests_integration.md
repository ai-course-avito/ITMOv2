# Integration-проверки

| Связь компонентов | Что может сломаться | Как воспроизводим | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| FastAPI -> ReviewService | Нет 422 на невалидном теле | POST /api/reviews с {} | 422 Unprocessable Entity | app/api.py:35-38 принимает dict без модели |
| FastAPI -> ReviewService -> LLM | Нет 413 при >20k | POST /api/reviews с diff=20001 символ | 413 Payload Too Large | app/api.py:35-38 нет проверки длины |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): P1-03
- Что проверили и исправили сами: соответствие проверок правилам API-1 и текущему коду
