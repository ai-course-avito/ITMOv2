# Итоговый артефакт (ToT) — очищенный

## ToT-промпт (итоговый)
Сгенерируй 3 альтернативных инженерных подхода к реализации первого сценария из TRAINING_PR.diff (FastAPI POST /api/reviews + ReviewService.review(diff) -> llm.generate), устраняя риски: отсутствие валидации, отсутствие обработки исключений LLM, неконтролируемый размер diff. Оцени по критериям (сложность, читаемость, поддерживаемость, риски интеграции), выбери лучший и разверни финальный артефакт: краткий обзор, контракт валидации, обработка ошибок и Mermaid-блок-схема. Ограничения: только факты diff, минимальные корректные изменения.

## Финальный артефакт

Краткий обзор
В diff добавлен эндпоинт FastAPI `POST /api/reviews`, принимающий `payload: dict` и передающий `payload["diff"]` сервису. В `ReviewService` реализован метод `review(diff: str)`, формирующий промпт и вызывающий `llm.generate`, возвращая `{ "comment": answer }`. Для повышения надёжности и безопасности вводим минимальные изменения: Pydantic-валидация входа и маппинг исключений LLM.

Контракт валидации
| Поле | Тип | Ограничения | Ошибка |
|---|---|---|---|
| diff | string | required, type=str, max_length=20000 | 422 Unprocessable Entity |

Контроллер (псевдокод)
```python
from pydantic import BaseModel, Field
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

Сервис: контроль размера/нормализация diff
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
    B -- diff > 20000 --> Z[413 Payload Too Large]
```
