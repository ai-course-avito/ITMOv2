# Unit-проверки

| Требование или правило | Что проверяем изолированно | Вход | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| OUT-1 контракт | Маппинг ответа LLM в `{summary,risks,checks}` | синтетический ответ LLM | JSON с требуемыми полями | CASE.md OUT-1 |
| SEC-1 | Редактирование секретов | diff с "token=abc" | промпт содержит [REDACTED] | CASE.md SEC-1 |
| API-1 | Ограничение длины | строка длиной 20001 | выбрасывается ошибка, верхний уровень вернёт 413 | CASE.md API-1 |

Примеры unit-тестов (эскизы):

```python
import pytest


def redact_secrets(text: str) -> str:
    # Простейшая заглушка для демонстрации SEC-1
    return text.replace("token=", "[REDACTED]=")


def test_redact_secrets_replaces_token():
    assert "[REDACTED]=" in redact_secrets("token=abc123")


def enforce_len_limit(diff: str, limit: int = 20000) -> None:
    if len(diff) > limit:
        raise ValueError("payload too large")


def test_enforce_len_limit_raises_on_long_input():
    with pytest.raises(ValueError):
        enforce_len_limit("x" * 20001)


def map_llm_answer_to_contract(answer: str) -> dict:
    # Демонстрация OUT-1: минимальный маппинг
    return {"summary": answer[:140], "risks": [], "checks": []}


def test_out1_mapper_shapes_response():
    data = map_llm_answer_to_contract("ok")
    assert set(data.keys()) == {"summary", "risks", "checks"}
```

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): prompts.md#master-4
- Что проверили и исправили сами: проверили, что тесты не зависят от реального LLM и используют моки.
