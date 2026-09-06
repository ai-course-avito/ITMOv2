# Анализ процесса: AS IS и TO BE

## AS IS

- Событие: клиент отправляет POST `/api/reviews` с телом `payload: dict`.
- Обработка: `create_review(payload: dict)` достаёт `payload["diff"]` без схемы/валидации и передаёт в `ReviewService.review`.
- ReviewService: формирует `prompt = f"Review this pull request and find problems:\n{diff}"` и вызывает `llm.generate(prompt)` без таймаута и обработки ошибок.
- Результат: возвращается `{"comment": answer}`; при отсутствии `diff` — `KeyError` и HTTP 500.
- Риски: отсутствие валидации, отсутствие контролируемых ошибок LLM, риск prompt-injection/утечки секретов.

Участники: Клиент → FastAPI `/api/reviews` → ReviewService → внешний LLM.

## TO BE

- Схема: Pydantic-модель `ReviewRequest(diff: constr(strip=True))` с автоматической 422 при невалидном вводе.
- Ограничения входа: отклонять diff > 20000 символов (HTTP 413).
- Санитизация: `sanitize(diff)` удаляет секреты (SEC-1) перед отправкой во внешний LLM.
- Надёжность: LLM-клиент с таймаутом 10с, обработкой ошибок (REL-1), маппингом на контролируемый ответ.
- Формат: нормализованный ответ `{summary, risks<=3, checks}` (OUT-1); без изменения кода/действий (SCOPE-1); логи без содержимого diff/ответа (OBS-1).

```mermaid
flowchart LR
    A[Client] --> B[FastAPI /api/reviews]
    B --> C[Pydantic ReviewRequest]
    C -->|valid| D[Check length <= 20k]
    C -->|invalid| I[422 Validation Error]
    D -->|>20k| J[413 Payload Too Large]
    D -->|ok| E[Sanitize diff (SEC-1)]
    E --> F[LLM client (timeout=10s, REL-1)]
    F --> G[Normalize to {summary, risks<=3, checks} (OUT-1)]
    F -- error/timeout --> H[Controlled error mapping]
    G --> R[200 Response]
```

## Разница

| Что меняется | AS IS | TO BE | Как проверим изменение |
|---|---|---|---|
| Валидация тела | dict, KeyError и 500 | Pydantic-модель, 422 | Отправить `{}` → 422 |
| Длина diff | Не ограничено | 413 при >20000 | Отправить длинный diff → 413 |
| Секреты в prompt | Сырые данные | sanitize → [REDACTED] | Передать `token=abc`; проверить prompt |
| Ошибки LLM | 500 без обработки | Контролируемый ответ | Мок LLM timeout → контролируемая ошибка |
| Формат ответа | {comment} | {summary, risks<=3, checks} | Контракт OUT-1 |

## Как использовали AI

- Для чего: Сводка AS IS/TO BE и фиксация различий на основе TRAINING_PR.diff и CASE.md.
- Тип промпта: master prompt.
- Строка в [`prompts.md`](prompts.md): P1-02.
- Что проверили и исправили сами: Сопоставили шаги TO BE с правилами SEC-1, API-1, REL-1, OUT-1, OBS-1; проверили воспроизводимость проверок.
