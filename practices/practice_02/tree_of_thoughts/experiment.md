# Улучшение через Tree of Thoughts (ToT)

## 1. Сконструированный ToT-промпт
Сгенерируй 3 альтернативных инженерных подхода к реализации первого рабочего сценария из TRAINING_PR.diff (FastAPI POST /api/reviews + ReviewService.review(diff) -> llm.generate), устраняющих риски: отсутствие валидации, отсутствие обработки исключений LLM, неконтролируемый размер diff. Для каждой альтернативы опиши архитектурный паттерн/библиотеки/алгоритмы. Оцени каждую по критериям: вычислительная сложность, читаемость, поддерживаемость, риски интеграции — по шкале 1–10 с аргументацией. Выбери лучшую или скомбинируй сильные стороны и разверни финальный артефакт: краткий обзор, спецификация контракта валидации, обработка ошибок, и блок-схема Mermaid.

Ограничения: соблюдай факты diff; не вводи внешние зависимости, если они не критичны; цель — минимальные изменения, покрывающие риски.

## 2. Дерево мыслей и сравнительная матрица

Альтернатива A: Pydantic-валидация + простая обработка ошибок
- Идея: добавить Pydantic-модель для запроса (`diff: str`), использовать FastAPI валидацию, оборачивать вызов LLM в try/except с маппингом исключений.
- Библиотеки: FastAPI встроенная валидация (pydantic), стандартные исключения.
- Оценка:
  - Вычислительная сложность: 9/10 — минимальная нагрузка; валидация O(len(diff)), try/except не добавляет затрат.
  - Читаемость: 9/10 — декларативная схема, явный маппинг ошибок.
  - Поддерживаемость: 9/10 — стандартные практики FastAPI/Pydantic.
  - Риски интеграции: 8/10 — низкие, изменений в архитектуре минимум.

Альтернатива B: Middleware для валидации/лимитов + централизованный error handler
- Идея: вынести ограничения длины diff и базовую фильтрацию в middleware, добавить глобальный exception handler.
- Библиотеки: FastAPI middleware/exception handlers.
- Оценка:
  - Вычислительная сложность: 8/10 — небольшой overhead middleware.
  - Читаемость: 8/10 — часть логики скрыта; разделение ответственностей понятное.
  - Поддерживаемость: 8/10 — централизованная обработка, но больше файлов.
  - Риски интеграции: 7/10 — требуется продумать порядок middleware и покрытие всех роутов.

Альтернатива C: Асинхронная очередь и worker для LLM
- Идея: перевод LLM вызова в фонового worker’а (Celery/RQ), API возвращает 202/ID.
- Библиотеки: Celery/RQ + брокер.
- Оценка:
  - Вычислительная сложность: 6/10 — накладные расходы, сложнее эксплуатация.
  - Читаемость: 7/10 — больше компонентов.
  - Поддерживаемость: 6/10 — инфраструктурные зависимости.
  - Риски интеграции: 5/10 — значительные изменения, не подтверждённые diff.

Выбор
- Победитель: Альтернатива A (Pydantic + try/except). Лучшая по суммарным критериям, соответствует принципу «минимальные корректные изменения» и рискам из diff.
- Комбинация: из B берём идею централизованного exception handler’а для однородных ответов; лимит diff оставляем как бизнес-решение валидации/сервиса.

## 3. Реализованный финальный артефакт

Краткий обзор
- Добавить Pydantic-модель Request с полем `diff: str` и ограничением по длине (порог можно вынести в константу). Обновить эндпоинт для использования модели. Обернуть вызов LLM в try/except, маппировать исключения в 502/503. Зафиксировать формат ответа `{ "comment": str }`.

Контракт валидации (Markdown)
| Поле | Тип | Ограничения | Ошибка |
|---|---|---|---|
| diff | string | required, type=str, max_length=N (определить) | 422 Unprocessable Entity |

Пример контроллера (псевдокод с type hints)
```python
from pydantic import BaseModel, Field, ValidationError
from fastapi import FastAPI, HTTPException

class ReviewRequest(BaseModel):
    diff: str = Field(..., description="Unified diff", max_length=20000)

app = FastAPI()

@app.post("/api/reviews")
def create_review(payload: ReviewRequest) -> dict[str, str]:
    try:
        return review_service.review(payload.diff)
    except LLMTimeoutError as e:
        raise HTTPException(status_code=503, detail="LLM timeout") from e
    except Exception as e:
        raise HTTPException(status_code=502, detail="LLM error") from e
```

Сервис: контроль размера/нормализация diff (псевдокод)
```python
class ReviewService:
    def __init__(self, llm: LLM, max_len: int = 20000) -> None:
        self.llm = llm
        self.max_len = max_len

    def review(self, diff: str) -> dict[str, str]:
        if len(diff) > self.max_len:
            raise ValueError("diff too large")
        prompt = f"Review this pull request and find problems:\n{diff}"
        answer = self.llm.generate(prompt)
        return {"comment": answer}
```

Диаграмма Mermaid
```mermaid
flowchart LR
    A[POST /api/reviews] --> B{Валидация (Pydantic)}
    B -- ok --> C[Service.review]
    C --> D{LLM.generate}
    D -- ok --> E[{comment}]
    B -- 422 --> X[422 Unprocessable Entity]
    D -- exception --> Y[502/503 контролируемо]
```

Как проверим
- Негативный JSON без diff → 422.
- Исключение LLM → 502/503.
- Длинный diff > 20000 символов → 413 Payload Too Large (API-1 из CASE.md), без вызова LLM.
