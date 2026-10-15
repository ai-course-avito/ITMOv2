# AGENTS.md: ai-review-api

Маленький AI-review API на FastAPI: принимает diff, возвращает ревью. LLM заменен заглушкой без сети.

- Контракт API: `docs/requirements.md` (в том числе раздел "Планируемые фичи").
- Пример теста: `tests/test_example.py` (TestClient + `dependency_overrides`, пишем новые тесты в этом стиле).
- Проверка: `sh scripts/check.sh` (в конце печатает `CHECK PASS` или `CHECK FAIL`). Запускай после каждого изменения.
- Стиль кода: docs/style-guide.md
- Без поручения НЕ менять: контракт `docs/requirements.md` и `scripts/check.sh`.
- Код приложения в `app/`, тесты в `tests/`. LLM в тестах всегда подменяем через `app.dependency_overrides[get_llm_client]`.
