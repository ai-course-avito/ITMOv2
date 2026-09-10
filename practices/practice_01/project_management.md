# План поставки

## Инкременты и ответственность

| Инкремент | Наблюдаемый результат | Что делает человек | Что делает AI или субагент | Проверка | Зависимости |
|---|---|---|---|---|---|
| 1 | Pydantic-модели ReviewRequest/ReviewResponse с валидацией diff | Backend-dev пишет модели | AI (P1-02) проверяет модели на соответствие OUT-1 | tests_unit.md: payload без diff → 422; diff > 20000 → 413 | TRAINING_PR.diff |
| 2 | redact секретов (SEC-1) + защита от prompt injection | Backend-dev реализует фильтр | AI (P1-02) проверяет покрытие паттернов SEC-1 | tests_unit.md: diff с token → [REDACTED] в prompt | Increment 1 |
| 3 | REL-1: таймаут 10s + обработка ошибок; OUT-1: структурированный ответ | Backend-dev реализует ReviewService.review | AI (P1-02) проверяет try/except и формат ответа | tests_unit.md: LLM timeout → контролируемый ответ; ответ соответствует OUT-1 | Increment 2 |
| 4 | OBS-1: логирование request_id, duration, status | Backend-dev добавляет logging | AI (P1-02) проверяет отсутствие diff/ответа в логах | tests_unit.md: лог содержит ровно 3 поля | Increment 3 |
| 5 | Интеграция и E2E-покрытие | QA + backend-dev пишут тесты | AI (P1-02) генерирует edge-кейсы | tests_integration.md, tests_e2e.md | Increments 1–4 |

## Диаграмма Ганта

```mermaid
gantt
<<<<<<< HEAD
    title План первого рабочего сценария
    dateFormat  YYYY-MM-DD
    section Подготовка
    Контекст и критерии :a1, 2026-09-01, 2d
    section Реализация
    Первый инкремент :after a1, 3d
    section Проверка
    Тесты и ревью :2d
```

Замените даты и задачи на свой план.

## Как использовали AI

- Для чего:
- Тип промпта:
- Строка в [`prompts.md`](prompts.md):
- Что проверили и исправили сами:
=======
    title План первого рабочего сценария — AI-помощник ревьюера PR
    dateFormat  YYYY-MM-DD
    section Подготовка
    Контекст и критерии :a1, 2026-09-10, 1d
    Анализ PR (P1-01, P1-02) :a2, 2026-09-10, 1d
    section Инкремент 1
    Pydantic-модели + валидация :b1, 2026-09-11, 1d
    section Инкремент 2
    SEC-1 redact + prompt delimiter :b2, 2026-09-12, 1d
    section Инкремент 3
    REL-1 timeout + OUT-1 формат :b3, 2026-09-13, 1d
    section Инкремент 4
    OBS-1 логирование :b4, 2026-09-14, 1d
    section Проверка
    Unit + Integration + E2E тесты :c1, 2026-09-15, 1d
    Peer review :c2, 2026-09-15, 0.5d
```

## Как использовали AI

- Для чего: разбиение задачи на инкременты с распределением ответственности между человеком и AI
- Тип промпта: zero-shot (P1-01), затем уточнение с master prompt (P1-02)
- Строка в `prompts.md`: P1-01, P1-02
- Что проверили и исправили сами: сверили каждый инкремент с правилами из CASE.md
>>>>>>> 137af94 (my new)
