# Chain of Verification

- Проверяемый черновик или утверждение:

Черновик изменений к файлу practices/practice_01/TRAINING_PR.diff, добавляющий REST-эндпоинт создания review и минимальные правки типизации/валидации. Черновик включал базовую реализацию без проверки обязательного поля в payload.

## Запрос на проверку

Проверить корректность и устойчивость изменений в TRAINING_PR.diff:
1. Обработка отсутствующего поля payload["diff"] без KeyError и с корректным HTTP-статусом.
2. Корректность импортов и аннотаций типов в FastAPI-обработчике.
3. Валидность протокола LLM и сигнатуры метода generate.
4. Соответствие формата diff и минимальность изменений.
5. Возвращаемая форма данных соответствует ожиданиям API (dict с ключом "comment").

## Вопросы проверки и evidence

| Вопрос | Источник или проверка | Результат |
|---|---|---|
| Обрабатывается ли отсутствие ключа "diff" без KeyError? | Просмотр функции create_review: использование payload.get("diff") | Да, используется .get; при None бросается HTTPException 422 |
| Возвращается ли корректный статус при невалидном запросе? | Проверка raise HTTPException(status_code=422, ...) | Да, 422 Unprocessable Entity |
| Импортирован ли HTTPException? | Строка импорта в app/api.py дифе | Да, добавлен импорт из fastapi |
| Корректны ли аннотации dict[str, str]? | Совместимость с Python 3.9+ | Да, синтаксис валиден для 3.9+ |
| Валиден ли протокол LLM и метод-стаб generate? | Строки в app/review_service.py | Да, метод определен с сигнатурой и эллипсисом |
| Возвращаемый формат review_service.review соответствует API? | review_service.review возвращает {"comment": answer} | Да, соответствует ожидаемому ответу эндпоинта |
| Сохранен ли минимализм правок? | Сравнение с исходным черновиком | Да, добавлены только импорт и валидация без введения Pydantic-моделей |

## Исправленный результат

Окончательная версия TRAINING_PR.diff после исправлений:

```
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
-from fastapi import FastAPI
+from fastapi import FastAPI, HTTPException
 
 from app.dependencies import review_service
 
 app = FastAPI()
 
 
 +@app.post("/api/reviews")
-def create_review(payload: dict) -> dict[str, str]:
-    return review_service.review(payload["diff"])
+def create_review(payload: dict[str, str]) -> dict[str, str]:
+    diff_value = payload.get("diff")
+    if diff_value is None:
+        raise HTTPException(status_code=422, detail="'diff' field is required")
+    return review_service.review(diff_value)
 
 
 @app.get("/health")
 def health() -> dict[str, str]:
     return {"status": "ok"}
```

## Что изменили в исходном артефакте

- Файл и раздел:
- practices/practice_01/TRAINING_PR.diff, секция app/api.py и заголовок импорта
- Изменение:
  - Добавлен импорт HTTPException.
  - В обработчике POST /api/reviews заменен тип параметра на dict[str, str], добавлена явная валидация наличия поля "diff" с возвратом 422 вместо KeyError.
  - Небольшой косметический рефакторинг метода Protocol.generate в app/review_service.py для читабельности.
- Что отклонили:
  - Введение Pydantic-модели для тела запроса (слишком тяжело для учебного примера, выбрана минимальная правка).
  - Дополнительные изменения контрактов API и структуры ответа (оставлен {"comment": str}).

Скрытые рассуждения модели не сохраняйте; нужны только вопросы, evidence и исправленный результат.
