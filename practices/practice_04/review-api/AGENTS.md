# review-api — AI-помощник ревьюера PR

FastAPI-сервис: `POST /api/reviews` принимает unified diff и возвращает ревью от LLM. Код из `TRAINING_PR.diff` Практики 1.

## Где что

- Контракт и правила (SEC-1, API-1, REL-1, OUT-1, QA-1): `docs/requirements.md`. Фичи A и B описаны там же.
- Style guide: `docs/style-guide.md` — **прочитай перед любым изменением кода**.
- Пример теста: `tests/test_api.py::test_review_returns_llm_answer`.
- Заглушка LLM для тестов: `app/dependencies.py` (`llm.calls` — счётчик вызовов).

## Проверка

- Единственная команда проверки: `sh scripts/check.sh` (pytest по `tests/`).
- После каждой правки файла хук `.opencode/plugins/check-after-edit.js` запускает её сам и дописывает `[check-after-edit] PASS/FAIL` к результату инструмента. При FAIL исправляй причину в коде, а не тест.
- Окружение: `.venv` (`make install`). Новые зависимости не добавляй.

## Инструменты

- MCP `review-tools` → `scan_diff(diff_path)`: проверка diff по API-1 и SEC-1 до отправки в LLM.
- Skill `pr-diff-review`: процедура ревью diff с валидатором OUT-1. Используй его, когда просят отревьюить diff.

## Нельзя без явного поручения

- Менять `docs/requirements.md`, `scripts/check.sh`, `.opencode/` и `opencode.json`.
- Удалять или ослаблять тесты.
- Делать `git commit`, `git push`, approve или merge.
