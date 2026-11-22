# 01_agents_md

- Модель: `opencode/big-pickle`, новая сессия `opencode run` в `review-api/`
- Время: 28 с, код выхода 0

## Запрос

```text
Прочитай AGENTS.md. Где контракт, какой командой проверять результат и что нельзя менять без поручения? Найди контракт и пример теста. Назови требования и ограничения фичи A. Пока ничего не меняй.
```

## Ход работы

### 1. `read` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/AGENTS.md"}
```

Результат:

```text
<path>/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/AGENTS.md</path>
<type>file</type>
<content>
1: # review-api — AI-помощник ревьюера PR
2: 
3: FastAPI-сервис: `POST /api/reviews` принимает unified diff и возвращает ревью от LLM. Код из `TRAINING_PR.diff` Практики 1.
4: 
5: ## Где что
6: 
7: - Контракт и правила (SEC-1, API-1, REL-1, OUT-1, QA-1): `docs/requirements.md`. Фичи A и B описаны там же.
8: - Style guide: `docs/style-guide.md` — **прочитай перед любым изменением кода**.
9: - Пример теста: `tests/test_api.py::test_review_returns_llm_answer`.
10: - Заглушка LLM для тестов: `app/dependencies.py` (`llm.calls` — счётчик вызовов).
11: 
12: ## Проверка
13: 
14: - Единственная команда проверки: `sh scripts/check.sh` (pytest по `tests/`).
15: - После каждой правки файла хук `.opencode/plugins/check-after-edit.js` запускает её сам и дописывает `[check-after-edit] PASS/FAIL` к результату инструмента. При FAIL исправляй причину в коде, а не тест.
16: - Окружение: `.venv` (`make install`). Новые зависимости не добавляй.
17: 
18: ## Инструменты
19: 
20: - MCP `review-tools` → `scan_diff(diff_path)`: проверка diff по API-1 и SEC-1 до отправки в LLM.
21: - Skill `pr-diff-review`: процедура ревью diff с валидатором OUT-1. Используй его, когда просят отревьюить diff.
22: 
23: ## Нельзя без явного поручения
24: 
25: - Менять `docs/requirements.md`, `scripts/check.sh`, `.opencode/` и `opencode.json`.
26: - Удалять или ослаблять тесты.
27: - Делать `git commit`, `git push`, approve или merge.

(End of file - total 27 lines)
</content>
```

### 2. `glob` → completed

Вход:

```json
{"pattern": "**/*.md"}
```

Результат:

```text
/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/AGENTS.md
/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/docs/style-guide.md
/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/docs/requirements.md
```

### 3. `glob` → completed

Вход:

```json
{"pattern": "tests/**"}
```

Результат:

```text
/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/tests/test_api.py
/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/tests/__init__.py
/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/tests/test_diff_scan.py
```

### 4. `read` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/docs/requirements.md"}
```

Результат:

```text
<path>/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/docs/requirements.md</path>
<type>file</type>
<content>
1: # Контракт сервиса AI-review
2: 
3: Источник правил — Context Pack Практики 1 (`practices/practice_01/context.md`, ветка `practice_01`).
4: 
5: ## Эндпоинт
6: 
7: `POST /api/reviews` принимает JSON `{"diff": "<unified diff>"}` и возвращает результат ревью от LLM.
8: `GET /health` возвращает `{"status": "ok"}`.
9: 
10: ## Правила
11: 
12: | ID | Правило |
13: |---|---|
14: | SEC-1 | Перед отправкой во внешний LLM из diff удаляются токены, пароли и приватные ключи. |
15: | API-1 | diff длиннее 20 000 символов отклоняется с HTTP 413. |
16: | REL-1 | Внешний LLM-вызов имеет timeout 10 секунд; ошибка превращается в контролируемый ответ. |
17: | OUT-1 | Ответ ревью содержит `summary`, массив `risks` (≤ 3, поля `file`, `line`, `evidence`, `risk`) и массив `checks`. |
18: | SCOPE-1 | Сервис только советует: не пишет код и не выполняет действия в GitHub. |
19: | QA-1 | Риск включается в ответ, только если подтверждён строкой diff или правилом. |
20: | OBS-1 | В лог пишутся только `request_id`, длительность и статус; diff и ответ модели не логируются. |
21: 
22: ## Фича A — входная валидация (API-1)
23: 
24: 1. Нет поля `diff` или оно не строка → HTTP 422, LLM не вызывается.
25: 2. Пустой diff (после `strip()`) → HTTP 422, LLM не вызывается.
26: 3. Длина diff больше 20 000 символов → HTTP 413 с телом `{"detail": "diff too large"}`, LLM не вызывается.
27: 4. Ровно 20 000 символов — допустимо, запрос обрабатывается.
28: 
29: ## Фича B — ошибка зависимости (REL-1)
30: 
31: 1. LLM не ответил за 10 секунд → HTTP 504 с телом `{"detail": "llm timeout"}`.
32: 2. LLM бросил исключение → HTTP 502 с телом `{"detail": "llm unavailable"}`; текст исключения наружу не отд … (+85 симв.)
```

### 5. `read` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/tests/test_api.py"}
```

Результат:

```text
<path>/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/tests/test_api.py</path>
<type>file</type>
<content>
1: from fastapi.testclient import TestClient
2: 
3: from app.api import app
4: from app.dependencies import llm
5: 
6: client = TestClient(app)
7: 
8: 
9: def setup_function() -> None:
10:     llm.calls.clear()
11: 
12: 
13: def test_health() -> None:
14:     response = client.get("/health")
15:     assert response.status_code == 200
16:     assert response.json() == {"status": "ok"}
17: 
18: 
19: def test_review_returns_llm_answer() -> None:
20:     response = client.post("/api/reviews", json={"diff": "diff --git a/x.py b/x.py\n+print(1)\n"})
21:     assert response.status_code == 200
22:     assert response.json() == {"comment": "stub review: no problems found"}
23:     assert len(llm.calls) == 1

(End of file - total 23 lines)
</content>
```

- **Контракт:** `docs/requirements.md` (правила SEC-1, API-1, REL-1, OUT-1, SCOPE-1, QA-1, OBS-1 + фичи A и B).
- **Проверка:** `sh scripts/check.sh` (pytest по `tests/`; хук запускает сам после правок).
- **Нельзя без поручения:** менять `docs/requirements.md`, `scripts/check.sh`, `.opencode/`, `opencode.json`; удалять/ослаблять тесты; `git commit/push`, approve, merge. Также: не добавлять зависимости, при FAIL чинить код, а не тест.
- **Пример теста:** `tests/test_api.py::test_review_returns_llm_answer` (POST `/api/reviews` → 200, `{"comment": "stub review: no problems found"}`, `llm.calls == 1`).

**Фича A — входная валидация (API-1), `docs/requirements.md:22-27`:**
1. Нет поля `diff` или не строка → 422, LLM не вызывается.
2. Пустой diff (после `strip()`) → 422, LLM не вызывается.
3. Длина > 20 000 символов → 413, тело `{"detail": "diff too large"}`, LLM не вызывается.
4. Ровно 20 000 символов — допустимо, запрос обрабатывается.

Ничего не менял.

