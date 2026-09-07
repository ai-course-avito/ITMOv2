# Анализ процесса: AS IS и TO BE

## AS IS

Ручной процесс ревью в команде из 30 инженеров (5 сеньоров):

```mermaid
flowchart TD
    A[Разработчик пушит ветку и открывает PR] --> B[GitHub назначает ревьюера]
    B --> C{Свободен ли сеньор?}
    C -- Да --> D[Сеньор читает код и diff вручную]
    C -- Нет --> E[Ожидание до 18ч avg]
    D --> F[Комментарии в PR]
    F --> G[Автор вносит правки]
    G --> H[Повторное ожидание ревью]
    H --> I{Нужны правки?}
    I -- Да --> F
    I -- Нет --> J[Merge]
```

Проблемы: высокая задержка до первого отзыва, непостоянное качество комментариев, много циклов «мелких фиксов», отсутствие автоматических проверок на типовые проблемы.

## TO BE

Добавляем авто-ревью бота, работающего от вебхука и очереди. Диаграмма последовательностей для одного PR:

```mermaid
sequenceDiagram
    participant Dev as Автор PR
    participant GH as GitHub
    participant WH as Webhook API
    participant BUS as Event Bus/Queue
    participant WRK as Review Worker Pool
    participant LLM as OpenRouter LLM API
    Dev->>GH: Открывает/обновляет PR
    GH-->>WH: Webhook (pull_request.*) с ссылкой на diff
    WH->>BUS: Publish ReviewRequested{pr, diff_url}
    BUS-->>WRK: Deliver task
    WRK->>GH: Fetch diff (rate-limited)
    WRK->>WRK: Diff Parser, Token Budget, Prompt Builder
    WRK->>LLM: Request review (idempotency-key)
    alt 429/5xx от LLM
        WRK->>LLM: Exponential backoff (max 5m)
        Note over WRK,LLM: Джиттер, трейсинг попыток
    else OK
        LLM-->>WRK: Structured JSON
        WRK->>GH: Post comments + summary
    end
    WRK-->>BUS: Ack
```

Важные элементы: триггер — GitHub Webhook; декуплинг через очередь; защита от падений LLM — backoff и graceful degradation (сводка-«извинение» без блокировки пайплайна).

## Разница

| Что меняется | AS IS | TO BE | Как проверим изменение |
|---|---|---|---|
| Триггер ревью | Ручное назначение ревьюера | Авто-триггер по Webhook | Интеграционный тест: эмуляция Webhook → публикация комментария |
| Время на первый отзыв | ~18 часов | < 5 минут | Метрика TtFR из GitHub Events |
| Обработка больших diff | Нет ограничений | Отсечение > 64 KiB, чанки | Тест с большим diff (ожидаемый 413/422 или частичная обработка) |
| Отказоустойчивость LLM | Нет | Backoff + fallback | Тесты 429/500 с ожиданием повторов |
| Структура ответа | Текст без схемы | JSON-схема + маппинг в комментарии | Контрактные тесты схемы |

## Graceful degradation

Если LLM недоступен или превышен лимит, система:
- ставит задачу в повтор с экспоненциальной паузой (до N попыток),
- при исчерпании попыток публикует один комментарий с кратким статусом и ссылкой на ретрай позже,
- никогда не возвращает 5xx клиенту из-за внутренних ошибок LLM в синхронном API; для асинхронного пути — ack задачи и запись в DLQ.

## Как использовали AI

- Назначение запроса: сравнить AS IS и TO BE, зафиксировать точки интеграции и поведение при сбоях LLM.
- Тип промпта: Master Prompt с Chain of Verification.
- Ссылка на prompts.md: #P1-05
- Собственная верификация: проверили соответствие TO BE архитектуре в adr.md и тестам (integration/load/e2e); уточнили, что именно является триггером и как проявляется деградация.
