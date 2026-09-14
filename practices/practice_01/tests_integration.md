# Integration-проверки

| Связь компонентов | Что может сломаться | Как воспроизводим | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| FastAPI ↔ Pydantic | 422/500 при неверном входе | POST без `diff` | 422 с описанием поля | problem.md, CASE.md |
| API ↔ Preprocess | 413 при длинном diff | POST с 20001 символом | 413 Payload Too Large | CASE.md API-1 |
| Service ↔ LLM (мок) | Таймауты | мок задерживает >10с | контролируемый ответ без 5xx | CASE.md REL-1 |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): prompts.md#master-4
- Что проверили и исправили сами: сценарии используют моки и не требуют реального API ключа.

Эскиз docker-compose для интеграционных тестов (описательно):

```yaml
version: '3.8'
services:
  api:
    build: .
    environment:
      - OPENROUTER_API_KEY=fake
    command: uvicorn app.api:app --port 8080
  tests:
    image: python:3.11
    volumes:
      - .:/workspace
    working_dir: /workspace
    command: pytest -q
```
