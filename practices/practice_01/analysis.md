# Анализ процессов

## AS IS

Шаги текущего процесса на основе TRAINING_PR.diff:

1. Клиент (разработчик или CI) отправляет POST на `/api/reviews` с JSON телом, где ожидается ключ `diff`.
2. Обработчик FastAPI `create_review(payload: dict)` принимает произвольный `dict` без Pydantic-схемы и извлекает `payload["diff"]`.
3. Обработчик вызывает `review_service.review(diff)`. Внутри `ReviewService.review` строится строковый промпт как f-string с raw diff и вызывается `llm.generate(prompt)`.
4. Ответ LLM напрямую проксируется как `{"comment": answer}` и возвращается клиенту.
5. Не зафиксированы проверки длины diff, редактирование секретов, таймауты и стабильный контракт ответа.

Наблюдаемые риски:
- Возможные 422/500 из‑за отсутствия схемы и KeyError при `payload["diff"]`.
- Блокировка event loop при I/O (синхронные обработчики).
- Нарушение SEC-1 (редактирование секретов отсутствует), API-1 (нет ограничения длины), OUT-1 (контракт ответа не соответствует), REL-1 (нет таймаута/фолбэка).

Источник: practices/practice_01/TRAINING_PR.diff, practices/practice_01/CASE.md.

```mermaid
flowchart LR
    Client[Клиент/CI]\nPOST /api/reviews --> API[FastAPI sync handler\ncreate_review(dict)]
    API --> Service[ReviewService.review]
    Service -->|prompt=raw diff| LLM[LLM.generate]
    LLM --> API
    API --> Client
```

## TO BE (первый инкремент)

Шаги целевого процесса с учётом ограничений CASE.md:

1. Клиент/CI отправляет POST `/api/reviews` c телом по схеме: `{ diff: string }`.
2. FastAPI валидирует тело через Pydantic-модель; при отсутствии/невалидном поле — 422 с сообщением.
3. Перед обращением к модели diff проходит редактирование секретов (SEC-1) и проверку длины: > 20 000 символов — 413 (API-1).
4. Обработчик не блокирует event loop: I/O в LLM обёрнуто таймаутом 10 секунд (REL-1) и контролируемым фолбэком.
5. Ответ всегда соответствует OUT-1: `{ summary, risks[max=3]{file,line,evidence,risk}, checks[] }`.

```mermaid
flowchart LR
    Client[Клиент/CI]\nPOST /api/reviews --> API[FastAPI handler\nPydantic schema]
    API -->|SEC-1 redact| Redact[Редактирование секретов]
    Redact -->|API-1 len<=20000| Gate[Порог длины]
    Gate --> Service[ReviewService]
    Service -->|timeout 10s| LLM[LLM provider]
    LLM --> Service
    Service -->|OUT-1| API
    API --> Client
```

## Разница

| Что меняется | AS IS | TO BE | Как проверим изменение |
|---|---|---|---|
| Валидация входа | `dict`, возможен KeyError | Pydantic-схема `diff: str` | Unit: схема даёт 422 при отсутствии поля; Integration: корректный 200 |
| Длина diff | Не проверяется | 413 при >20000 символов (API-1) | Integration: длинная строка → 413 |
| Секреты | Не редактируются | Редактирование [REDACTED] (SEC-1) | Unit: редактирование паттернов; E2E: токен не утекает |
| Таймаут LLM | Нет | 10с и контролируемый ответ (REL-1) | Integration: мок таймаута → контролируемый ответ |
| Контракт ответа | `{comment}` | `{summary, risks[], checks[]}` (OUT-1) | Unit: сериализация; E2E: поля присутствуют |

## Как использовали AI

- Запрос: practices/practice_01/prompts/analitics.md
- Тип промпта: master (Role + Context Pack)
- Ссылка: prompts.md#master-1 (P1-02 контекст)
- Проверка: сопоставили шаги с TRAINING_PR.diff и правилами CASE.md; явные пробелы помечены как «нет данных в источнике».
