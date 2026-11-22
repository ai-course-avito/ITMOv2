# 02_feature_a

- Модель: `opencode/big-pickle`, новая сессия `opencode run` в `review-api/`
- Время: 79 с, код выхода 0

## Запрос

```text
Реализуй фичу A из docs/requirements.md. Перед изменением кода прочитай docs/style-guide.md. Сначала добавь тесты на все четыре пункта фичи A и убедись по результату хука, что они падают; затем исправь код приложения, пока хук не вернёт PASS. В конце назови правило style guide и место в коде, где оно выполнено, и перечисли фактически выполненные команды. Не делай commit.
```

## Ход работы

### 1. `read` → error

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/docs/requirements.md", "offset": "1.0", "limit": "200.0"}
```

Результат:

```text
The read tool was called with invalid arguments: SchemaError(Expected number | undefined, got "1.0"
  at ["offset"]).
Please rewrite the input so it satisfies the expected schema.
```

### 2. `read` → error

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/docs/requirements.md", "offset": "1.0", "limit": "200.0"}
```

Результат:

```text
The read tool was called with invalid arguments: SchemaError(Expected number | undefined, got "1.0"
  at ["offset"]).
Please rewrite the input so it satisfies the expected schema.
```

### 3. `read` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/docs/requirements.md", "offset": 1, "limit": 200}
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

### 4. `read` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/docs/style-guide.md", "offset": 1, "limit": 200}
```

Результат:

```text
<path>/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/docs/style-guide.md</path>
<type>file</type>
<content>
1: # Style guide
2: 
3: 1. Поведение проверяем через публичный интерфейс: HTTP-запросы `TestClient`, а не приватные функции.
4: 2. Каждое правило из `docs/requirements.md` — отдельный тест с ID правила в имени (`test_api1_...`, `test_rel1_...`).
5: 3. Ошибки отдаём через `HTTPException` с коротким `detail` на английском; внутренние сообщения наружу не выходят.
6: 4. Не добавляем новые зависимости и фреймворки ради маленькой правки.
7: 5. Не ослабляем `scripts/check.sh` и не удаляем тесты ради зелёного результата.
8: 
9: Хороший пример — `tests/test_api.py::test_review_returns_llm_answer`: запрос через HTTP, проверка кода ответа, тела и числа вызовов LLM.

(End of file - total 9 lines)
</content>
```

### 5. `read` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/tests/test_api.py", "offset": 1, "limit": 200}
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

### 6. `read` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/app/api.py", "offset": 1, "limit": 200}
```

Результат:

```text
<path>/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/app/api.py</path>
<type>file</type>
<content>
1: from fastapi import FastAPI
2: 
3: from app.dependencies import review_service
4: 
5: app = FastAPI()
6: 
7: 
8: @app.post("/api/reviews")
9: def create_review(payload: dict) -> dict[str, str]:
10:     return review_service.review(payload["diff"])
11: 
12: 
13: @app.get("/health")
14: def health() -> dict[str, str]:
15:     return {"status": "ok"}

(End of file - total 15 lines)
</content>
```

### 7. `read` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/app/dependencies.py", "offset": 1, "limit": 200}
```

Результат:

```text
<path>/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/app/dependencies.py</path>
<type>file</type>
<content>
1: from app.review_service import ReviewService
2: 
3: 
4: class StubLLM:
5:     """Детерминированная заглушка внешнего LLM: сеть и ключи не нужны."""
6: 
7:     def __init__(self) -> None:
8:         self.calls: list[str] = []
9: 
10:     def generate(self, prompt: str) -> str:
11:         self.calls.append(prompt)
12:         return "stub review: no problems found"
13: 
14: 
15: llm = StubLLM()
16: review_service = ReviewService(llm)

(End of file - total 16 lines)
</content>
```

### 8. `read` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/app/review_service.py", "offset": 1, "limit": 200}
```

Результат:

```text
<path>/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/app/review_service.py</path>
<type>file</type>
<content>
1: from typing import Protocol
2: 
3: 
4: class LLM(Protocol):
5:     def generate(self, prompt: str) -> str:
6:         ...
7: 
8: 
9: class ReviewService:
10:     def __init__(self, llm: LLM) -> None:
11:         self.llm = llm
12: 
13:     def review(self, diff: str) -> dict[str, str]:
14:         prompt = f"Review this pull request and find problems:\n{diff}"
15:         answer = self.llm.generate(prompt)
16:         return {"comment": answer}

(End of file - total 16 lines)
</content>
```

Сначала добавим тесты на фичу A.

### 9. `edit` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/tests/test_api.py", "oldString": "from fastapi.testclient import TestClient\n\nfrom app.api import app\nfrom app.dependencies import llm\n\nclient = TestClient(app)\n\n\ndef setup_function() -> None:\n    llm.calls.clear()\n\n\ndef test_health() -> None:\n    response = client.get(\"/health\")\n    assert response.status_code == 200\n    assert response.json() == {\"status\": \"ok\"}\n\n\ndef test_review_returns_llm_answer() -> None:\n    response = client.post(\"/api/reviews\", json={\"diff\": \"diff --git a/x.py b/x.py … (+2003 симв.)
```

Результат:

```text
Edit applied successfully.

[check-after-edit] sh scripts/check.sh → FAIL (exit 1)
        response = client.post("/api/reviews", json={"diff": diff})
>       assert response.status_code == 413
E       assert 200 == 413
E        +  where 200 = <Response [200 OK]>.status_code

tests/test_api.py:47: AssertionError
=========================== short test summary info ============================
FAILED tests/test_api.py::test_api1_no_diff_field - KeyError: 'diff'
FAILED tests/test_api.py::test_api1_diff_not_string - assert 200 == 422
FAILED tests/test_api.py::test_api1_empty_diff_after_strip - assert 200 == 422
FAILED tests/test_api.py::test_api1_diff_too_large - assert 200 == 413
4 failed, 7 passed in 0.32s
```

### 10. `edit` → completed

Вход:

```json
{"filePath": "/Users/lewolkogonov/ITMOv2/practices/practice_04/review-api/app/api.py", "oldString": "from fastapi import FastAPI\n\nfrom app.dependencies import review_service\n\napp = FastAPI()\n\n\n@app.post(\"/api/reviews\")\ndef create_review(payload: dict) -> dict[str, str]:\n    return review_service.review(payload[\"diff\"])\n\n\n@app.get(\"/health\")\ndef health() -> dict[str, str]:\n    return {\"status\": \"ok\"}", "newString": "from fastapi import FastAPI, HTTPException\n\nfrom app.dependencies import review_service\n\napp = FastAPI()\n\n\n@app.post(\"/api/reviews\")\ndef create_rev … (+566 симв.)
```

Результат:

```text
Edit applied successfully.

[check-after-edit] sh scripts/check.sh → PASS
...........                                                              [100%]
11 passed in 0.13s
```

Rule: style-guide.md:3 — "Ошибки отдаём через `HTTPException` с коротким `detail` на английском; внутренние сообщения наружу не выходят." Выполнено в `app/api.py:11–19` (валидация diff, raise HTTPException 422/413).

Commands: read(docs/requirements.md, docs/style-guide.md, tests/test_api.py, app/api.py, app/review_service.py, app/dependencies.py); edit(tests/test_api.py — добавлены test_api1_* и граничный test_api1_diff_exactly_20000); edit(app/api.py — валидация по п.1–4 фичи A); hook `sh scripts/check.sh` → FAIL после добавления тестов, → PASS после правки кода.

