# Артефакт по RCTF (исправленный)

### Краткий обзор изменения
В diff добавлен эндпоинт FastAPI `POST /api/reviews`, принимающий `payload: dict` и передающий `payload["diff"]` в сервис. В `ReviewService` реализован метод `review(diff: str)`, который формирует промпт, вставляя diff целиком, и вызывает `llm.generate`, возвращая `{ "comment": answer }`. Валидация входа и обработка исключений отсутствуют.

### Риски и проверки
| Candidate | Evidence (file:lines) | Check (AS IS → TO BE) |
|---|---|---|
| Нет валидации тела запроса для POST /api/reviews | app/api.py:35–38 — доступ к `payload["diff"]` без проверки | POST `{}` → (AS IS) 500 из‑за KeyError; (TO BE) 422/400 с описанием ошибки |
| Нет обработки исключений при вызове LLM | app/review_service.py:19–22 — `self.llm.generate(prompt)` без try/except | Смоделировать исключение в LLM → (AS IS) 5xx без маппинга; (TO BE) 502/503 с контролируемым сообщением |
| Неконтролируемый размер diff и возможность prompt injection | app/review_service.py:19–22 — diff целиком встраивается в промпт | Очень длинный/вредоносный diff → (TO BE) отказ по лимиту/усечение; инъекция не влияет на системные инструкции |

### Диаграмма потока
```mermaid
flowchart LR
    A[POST /api/reviews] --> B{Валидация тела?}
    B -- AS IS: нет --> C[Подготовка промпта с полным diff]
    C --> D[self.llm.generate]
    D -- AS IS: исключение --> E[5xx без маппинга]
    D -- ok --> F[{"comment": answer}]
    B -- TO BE: ошибка --> X[422/400]
    D -- TO BE: исключение --> Y[502/503 контролируемо]
```

### Как использовали RCTF
- Role: Principal Software Engineer (AI-assisted Code Review)
- Context: FastAPI + сервис LLM; работаем только по фактам diff; NFR — надёжность, безопасность, управляемость.
- Task: обзор, список рисков с evidence и check, диаграмма потока.
- Format: markdown-таблица + Mermaid + краткий обзор.
