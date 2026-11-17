---
description: "Задачи команды UI: веб-страница ревью диффа"
---

# Tasks: Веб-страница ревью диффа

**Input**: `specs/001-review-ui/` (plan.md, spec.md, research.md, data-model.md, contracts/), контракт `specs/contract/review-api.md`

**Tests**: обязательны — принцип II: тест первым, падение показать.

**Файлы команды**: `web/index.html`, `web/app.js`, `web/app.test.js`, одна новая строка в `scripts/check.sh`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 Создать `web/app.test.js` (`node:test`, `node:assert/strict`, импорт из `./app.js`) с одним тестом `canSubmit` — показать падение (`app.js` нет)
- [x] T002 Добавить в `scripts/check.sh` последней строкой `node --test 'web/*.test.js'` (отдельное поручение пользователя; существующие строки не менять); показать, что `check.sh` теперь красный из-за T001

## Phase 2: Foundational

- [x] T003 Каркас `web/app.js`: `REQUEST_TIMEOUT_MS = 45000`, `USER_TEXT` по data-model.md, `canSubmit`, блок `if (typeof document !== "undefined") init(document)`

**Checkpoint**: `check.sh` зелёный (Python + 1 тест node).

## Phase 3: User Story 1 — успешное ревью (P1) 🎯 MVP

**Independent Test**: подставной `fetch` отвечает 200 `ok` → исход `ok` со `stats`; `viewState` показывает ревью и статистику.

- [x] T004 [US1] Тесты: `canSubmit` для пустого/пробельного/непустого; `interpretResponse(200, ok-JSON)` → `kind: ok`, `review`, `stats`; `viewState(ok)` → `showReview`, `showStats`, без сообщения — показать падение
- [x] T005 [US1] `interpretResponse`, `viewState` в `web/app.js`
- [x] T006 [US1] Тесты контроллера: `createReviewer({fetchImpl})`: `review(diff)` вызывает `fetchImpl("/api/review", {method: "POST", headers: JSON, body: '{"diff":…}'})`; второй `review()` во время первого возвращает `null` и не вызывает `fetch` (SC-003); пустой дифф → исход `rejected/empty_diff` без вызова `fetch` (SC-002) — показать падение
- [x] T007 [US1] `createReviewer` в `web/app.js`
- [x] T008 [US1] `web/index.html`: поле, кнопка «Ревью», индикатор, блок ревью, блок статистики (файлы / +добавлено / −удалено), блок сообщения, `<details>` «подробнее»; `<script type="module" src="/app.js">`
- [x] T009 [US1] `init(document)` в `web/app.js`: кнопка `disabled` по `canSubmit`; нажатие → загрузка → `review()` → `viewState` → отрисовка; правка поля сбрасывает сообщение (FR-011)

## Phase 4: User Story 2 — отказ валидации (P2)

- [x] T010 [US2] Тесты: `interpretResponse(400, rejected/empty_diff)` и `rejected/diff_too_large` → `kind: rejected`; `interpretResponse(413, request_error/request_too_large)` → тот же `userText`, что `diff_too_large`; `viewState` отказа — без ревью и статистики; основной текст ≠ `message` сервера — показать падение
- [x] T011 [US2] Ветки отказа в `interpretResponse`/`userText`/`viewState`

## Phase 5: User Story 3 — ошибка модели или сети (P3)

- [x] T012 [US3] Тесты: `interpretResponse(502, error/model_timeout+stats)` → `kind: model_error`, `stats` есть, текст по коду, `message` с `[Errno 111]` не попадает в основной текст; `request_error/invalid_request` → текст `network`; тело не JSON, `status` неизвестный → `network`; контроллер: `fetchImpl` отклоняется → `network`; `fetchImpl` не отвечает дольше `timeoutMs` (малое значение) → `network`, поздний ответ не меняет исход — показать падение
- [x] T013 [US3] Ветки ошибки модели, `request_error`, `network`; `AbortController` и таймер в `createReviewer`

## Phase 6: Polish

- [x] T014 `sh scripts/check.sh` — полный вывод (Python + node)
- [x] T015 Сквозная проверка страницы по quickstart.md — после реализации команды логики
- [x] T016 Отчёт по задачам с `файл:строка`

## Dependencies & Execution Order

T001 → T002 → T003 → US1 (T004→T005, T006→T007, T008→T009) → US2 (T010→T011) → US3 (T012→T013) → T014 → T015 → T016.
[P] не ставится: почти все задачи правят `web/app.js` или `web/app.test.js`.

## Implementation Strategy

Логика страницы проверяется `node --test` без сервера и браузера; сервер команды логики нужен только для T015. Реализация после команды логики, чтобы её `check.sh` не видел недописанных файлов UI.
