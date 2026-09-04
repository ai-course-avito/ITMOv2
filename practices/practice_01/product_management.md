# Use cases и user stories

## Первый рабочий сценарий

**Когда** разработчик, открывший PR, отправляет diff на `POST /api/reviews` (`api.py:8-10`), **система** проверяет схему и размер входа (API-1), удаляет из diff секреты (SEC-1), вызывает внешний LLM с таймаутом 10 секунд (REL-1) и отбрасывает риски без доказательства (QA-1), **а пользователь получает** структурированный ответ с `summary`, не больше трёх `risks` (каждый с `file`, `line`, `evidence`, `risk`) и списком `checks` (OUT-1) — либо контролируемую ошибку (413 / 422 / ответ о сбое LLM) вместо HTTP 500 (`problem.md`, «Что происходит сейчас»).

Не входит в этот сценарий:

- approve, merge, изменение кода и любые действия в GitHub — сервис только советует (SCOPE-1, `problem.md` «Что не входит в задачу»);
- авторизация и аутентификация пользователей на `/api/reviews` (`problem.md`; по `context.md` — «требует уточнения»);
- интеграция с GitHub API и сам процесс мержа PR (`problem.md`);
- выбор и настройка конкретной LLM-реализации в `app.dependencies.review_service` — требует уточнения (`context.md`, «Что пока неизвестно»);
- правила репозитория, не относящиеся к этому PR: `snake_case` для таблиц БД и i18n frontend-строк (`CASE.md`).

## Use case

| Поле | Значение |
|---|---|
| Актор | Разработчик, открывший PR и желающий получить быстрый предварительный фидбек до ревью живым человеком (`problem.md`, `context.md`) |
| Триггер | HTTP-запрос `POST /api/reviews` с JSON-телом `{"diff": "<текст unified diff>"}` (`api.py:8-10`) |
| Предусловия | Сервис FastAPI запущен (`api.py:5`, `/health` возвращает `{"status": "ok"}` — `api.py:13-15`); `ReviewService` сконструирован с реализацией `LLM` (`review_service.py:9-11`, `app.dependencies.review_service`); внешний LLM-провайдер доступен; поле `diff` — строка длиной не больше 20 000 символов (API-1) |
| Основной результат | HTTP 200 и JSON по OUT-1: `summary` (краткое описание изменения), `risks` — от 0 до 3 элементов, каждый с полями `file`, `line`, `evidence`, `risk` и подтверждённый строкой diff или правилом репозитория (QA-1), `checks` — список проверок, которые стоит запустить. В промпт, отправленный LLM, секреты не попали (SEC-1). В логе — только `request_id`, длительность, статус (OBS-1). Решение о PR принимает человек (SCOPE-1) |
| Ошибка или отказ | (а) в теле нет ключа `diff` или он не строка → контролируемая ошибка валидации (422), а не `KeyError`/500 (`api.py:10`); (б) `len(diff) > 20 000` → HTTP 413 без вызова LLM (API-1); (в) LLM не ответил за 10 секунд или бросил исключение → контролируемый ответ с описанием сбоя, без трассировки 500 (REL-1); (г) LLM вернул риски без evidence → они отбрасываются, ответ остаётся валидным по OUT-1 (QA-1) |

```mermaid
sequenceDiagram
    actor Dev as Разработчик (автор PR)
    participant API as FastAPI POST /api/reviews (app/api.py)
    participant RS as ReviewService (app/review_service.py)
    participant LLM as Внешний LLM (LLM.generate)
    participant Log as Лог (OBS-1)

    Dev->>API: POST /api/reviews {"diff": "..."}
    API->>API: Валидация схемы: diff обязателен и строка
    alt нет ключа diff / не строка
        API-->>Dev: 422 контролируемая ошибка (вместо KeyError 500 на api.py:10)
    else len(diff) > 20 000
        API-->>Dev: 413 Payload Too Large (API-1)
    else вход валиден
        API->>RS: review(diff)
        RS->>RS: Редактирование секретов -> [REDACTED] (SEC-1)
        RS->>RS: prompt = "Review this pull request...\n{очищенный diff}" (review_service.py:14)
        RS->>LLM: generate(prompt), timeout 10 с (REL-1)
        alt таймаут или исключение провайдера
            LLM--xRS: ошибка / нет ответа за 10 с
            RS-->>API: контролируемый ответ: summary о сбое, risks=[], checks
        else ответ получен
            LLM-->>RS: текст с summary, risks, checks
            RS->>RS: Фильтр QA-1: только risks с evidence, не больше 3
            RS-->>API: {summary, risks[<=3]{file,line,evidence,risk}, checks} (OUT-1)
        end
        API-->>Dev: 200 JSON по OUT-1
    end
    API->>Log: request_id, длительность, статус (без diff и ответа модели)
    Dev->>Dev: Читает риски и сам решает судьбу PR (SCOPE-1)
```

## User stories и acceptance criteria

**User story 1.** Как разработчик, открывший PR, я хочу отправить diff и получить не больше трёх рисков с файлом, строкой и доказательством, чтобы исправить очевидные проблемы до ревью живым человеком.

**User story 2.** Как разработчик, я хочу при большом diff, пустом запросе или сбое LLM получать понятную ошибку за предсказуемое время, а не HTTP 500, чтобы доверять инструменту (`problem.md`, «Почему это мешает»).

**User story 3.** Как владелец репозитория, я хочу, чтобы секреты из diff никогда не покидали сервис в сторону внешнего LLM и не попадали в логи, чтобы соблюсти SEC-1 и OBS-1.

```gherkin
Feature: AI-ревью diff через POST /api/reviews (ReviewService)
  Сервис принимает diff, вызывает внешний LLM и возвращает summary, risks и checks.
  Сервис только советует: approve, merge и правка кода не выполняются (SCOPE-1).

  Background:
    Given сервис FastAPI запущен и GET /health возвращает {"status": "ok"}
    And ReviewService сконструирован с тестовой реализацией LLM (mock LLM.generate)

  Scenario: Позитивный — структурированный отзыв на валидный diff
    Given diff длиной не больше 20 000 символов без секретов
    And mock LLM возвращает ответ с summary, двумя risks с evidence и списком checks
    When разработчик отправляет POST /api/reviews с телом {"diff": "<diff>"}
    Then статус ответа 200
    And тело содержит поля summary, risks и checks (OUT-1)
    And в risks не больше 3 элементов, каждый с полями file, line, evidence, risk
    And каждый risk имеет непустой evidence из diff или ссылку на правило репозитория (QA-1)
    And ответ получен не позже чем через 10 секунд (REL-1)
    And в логе есть только request_id, длительность и статус, а содержимого diff нет (OBS-1)

  Scenario: Позитивный — секреты не уходят во внешний LLM
    Given diff содержит строки "token=abc123" и "-----BEGIN PRIVATE KEY-----"
    When разработчик отправляет POST /api/reviews с этим diff
    Then промпт, переданный в mock LLM.generate, не содержит "abc123" и тела приватного ключа
    And промпт содержит маркер [REDACTED] (SEC-1, хороший пример из CASE.md)

  Scenario: Негативный — diff превышает лимит
    Given diff длиной 20 001 символ
    When разработчик отправляет POST /api/reviews с этим diff
    Then статус ответа 413 (API-1)
    And mock LLM.generate не вызывался

  Scenario: Граничный — diff ровно 20 000 символов
    Given diff длиной ровно 20 000 символов
    When разработчик отправляет POST /api/reviews с этим diff
    Then статус ответа 200 (лимит API-1 включительный: отклоняется только "длиннее 20 000")
    And mock LLM.generate вызван один раз

  Scenario: Негативный — тело без ключа diff
    Given тело запроса {} без ключа diff
    When разработчик отправляет POST /api/reviews
    Then статус ответа 422, а не 500 (сейчас api.py:10 даёт KeyError — P1-02, check 5)
    And mock LLM.generate не вызывался

  Scenario: Негативный — внешний LLM не отвечает
    Given mock LLM.generate блокируется дольше 10 секунд
    When разработчик отправляет POST /api/reviews с валидным diff
    Then ответ приходит не позже чем через ~10 секунд (REL-1)
    And статус ответа не 5xx, тело содержит summary с описанием сбоя, risks пустой, checks непустой (OUT-1)

  Scenario: Негативный — внешний LLM бросает исключение
    Given mock LLM.generate поднимает RuntimeError
    When разработчик отправляет POST /api/reviews с валидным diff
    Then ответ контролируемый: статус не 5xx, тело валидно по OUT-1, трассировки исключения в теле нет (REL-1)
    And в лог записаны request_id, длительность и статус ошибки (OBS-1)

  Scenario: Граничный — LLM вернул больше трёх рисков и риск без доказательства
    Given mock LLM возвращает 5 risks, один из которых без evidence
    When разработчик отправляет POST /api/reviews с валидным diff
    Then в ответе не больше 3 risks (OUT-1)
    And risk без evidence в ответ не включён (QA-1)
```

## Как использовали AI

- Для чего: формулировка первого рабочего сценария, границ (не входит), таблицы use case, sequence-диаграммы потока `POST /api/reviews` → `ReviewService` → LLM и gherkin-сценариев по правилам SEC-1, API-1, REL-1, OUT-1, QA-1, OBS-1 на основе `problem.md` и TO BE из `analysis.md`.
- Тип промпта: master prompt (build).
- Строка в [`prompts.md`](prompts.md): P1-03.
- Что проверили и исправили сами: проверила sequence-диаграмму на соответствие реальному потоку из diff (Dev → API → ReviewService → LLM → Log) и на синтаксические ошибки — рендерится корректно. Сверила упомянутые строки review_service.py:14 с кодом.
