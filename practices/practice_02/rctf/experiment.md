# R.C.T.F.

- **Role:** IT-Engeneer
- **Context:** @practices/practice_01/TRAINING_PR.diff
- **Task:** Найти ошибки в контесте, записать их в файл @practices/practice_02/rctf/experiment.md строго по образцу. Как будто это твоя работа
- **Format:** Текст с вставками там где надо на python

## Полный запрос

Role: IT-Engeneer
Context: @practices/practice_01/TRAINING_PR.diff
Task: Найти ошибки в контесте, записать их в файл @practices/practice_02/rctf/experiment.md строго по образцу. Как будто это твоя работа
Format: Текст с вставками там где надо на python

## Что получили

Артефакт для ревью (diff):

```diff
diff --git a/app/review_service.py b/app/review_service.py
index 21bf12a..814c7d1 100644
--- a/app/review_service.py
+++ b/app/review_service.py
@@ -1,10 +1,23 @@
 from typing import Protocol
 
 
 class LLM(Protocol):
-    def generate(self, prompt: str) -> str: ...
+    def generate(self, prompt: str) -> str:
+        ...
 
 
 class ReviewService:
     def __init__(self, llm: LLM) -> None:
         self.llm = llm
+
+    def review(self, diff: str) -> dict[str, str]:
+        prompt = f"Review this pull request and find problems:\n{diff}"
+        answer = self.llm.generate(prompt)
+        return {"comment": answer}
 diff --git a/app/api.py b/app/api.py
 index 7c99aa1..da41e4f 100644
 --- a/app/api.py
+++ b/app/api.py
@@ -1,8 +1,17 @@
 from fastapi import FastAPI
 
 from app.dependencies import review_service
 
 app = FastAPI()
 
 
+@app.post("/api/reviews")
+def create_review(payload: dict) -> dict[str, str]:
+    return review_service.review(payload["diff"])
+
 @app.get("/health")
 def health() -> dict[str, str]:
     return {"status": "ok"}
```

Найденные проблемы и риски:

- app/api.py: Отсутствует схема запроса/ответа (Pydantic). Использование `payload: dict` ломает валидацию и ухудшает OpenAPI-документацию. При отсутствии ключа `diff` будет `KeyError` и 500, вместо корректного 422.
- app/api.py: Нет `response_model`, нет валидации ответа. Документация эндпоинта неполная.
- app/api.py: Нет обработки ошибок сервиса/LLM. Любая ошибка приведет к 500 без понятного сообщения.
- app/api.py: Нет аутентификации/авторизации. Открытый доступ к затратной операции (вызов LLM) создает риск злоупотреблений и расходов.
- app/api.py: Нет ограничений на размер тела запроса. Большой `diff` может перегрузить сервер и/или LLM.
- app/api.py: Синхронная функция потенциально блокирует event loop, если внутри выполняется I/O (сеть к LLM). Стоит использовать `async` и/или `run_in_threadpool`.
- app/api.py: Жесткая зависимость на глобальный `review_service` из `app.dependencies`. Для тестируемости и расширяемости лучше использовать DI через `Depends`.
- app/review_service.py: Возврат `dict[str, str]` требует Python 3.9+. В окружениях <3.9 это приведет к ошибкам типизации/линтинга. Лучше `Dict[str, str]` из `typing` или гарантировать версию.
- app/review_service.py: Нет лимита размера входного `diff`. Риск превышения токен-лимитов у LLM и DoS по CPU/стоимости.
- app/review_service.py: Нет маскировки чувствительных данных. Передача сырых диффов в внешнее LLM может утечь секреты/PII.
- app/review_service.py: Неопределенный формат ответа LLM. Ключ `"comment"` содержит произвольную строку без структуры; сложно парсить на клиенте.
- app/review_service.py: Нет обработки исключений `llm.generate`. Любое исключение приведет к 500 в API.

Рекомендации и минимальные правки (Python-вставки):

1. Ввести модели запроса/ответа и response_model.

```python
from pydantic import BaseModel, Field
from fastapi import Body, HTTPException

class ReviewRequest(BaseModel):
    diff: str = Field(min_length=1, max_length=50_000)

class ReviewResponse(BaseModel):
    comment: str

@app.post("/api/reviews", response_model=ReviewResponse)
def create_review(payload: ReviewRequest = Body(...)) -> ReviewResponse:
    try:
        return ReviewResponse(**review_service.review(payload.diff))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=502, detail="LLM service error")
```

2. Инжектировать `ReviewService` через Depends для тестируемости.

```python
from fastapi import Depends

def get_review_service() -> ReviewService:
    return review_service  # существующая фабрика/синглтон

@app.post("/api/reviews", response_model=ReviewResponse)
def create_review(payload: ReviewRequest, svc: ReviewService = Depends(get_review_service)) -> ReviewResponse:
    return ReviewResponse(**svc.review(payload.diff))
```

3. Ограничить размер diff и обезопасить вызов LLM.

```python
class ReviewService:
    MAX_DIFF_CHARS = 50_000

    def review(self, diff: str) -> dict[str, str]:
        if len(diff) > self.MAX_DIFF_CHARS:
            raise ValueError("diff is too large")
        prompt = f"Review this pull request and find problems:\n{diff}"
        answer = self.llm.generate(prompt)
        return {"comment": answer}
```

4. Если есть совместимость <3.9, заменить `dict[str, str]` на `Dict[str, str]`.

```python
from typing import Dict

def review(self, diff: str) -> Dict[str, str]:
    ...
```

5. При необходимости — добавить аутентификацию (например, API ключ через Header) и rate limiting на уровне шлюза.

## Что изменили в исходном артефакте

- Файл и раздел: practices/practice_02/rctf/experiment.md
- Изменение: Заполнен отчет R.C.T.F. по результатам ревью патча TRAINING_PR.diff с перечислением проблем и минимальных рекомендаций по исправлению (вставки на Python приведены как примеры).
- Как проверили: Просмотрен и проанализирован предоставленный diff; потенциальные точки отказа и риски сопоставлены с практиками FastAPI, типизации и интеграции LLM.
- Что отклонили: Не вносились изменения в код приложения в рамках этого задания; реализацию аутентификации и rate limiting оставили за пределами данного отчета как зависящие от требований и инфраструктуры.
