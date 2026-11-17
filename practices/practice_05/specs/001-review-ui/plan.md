# Implementation Plan: Веб-страница ревью диффа

**Branch**: `001-review-ui` | **Date**: 2026-10-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-review-ui/spec.md`; общий
контракт стыка — [specs/contract/review-api.md](../contract/review-api.md).

## Summary

Одна HTML-страница (`web/index.html`) и один скрипт (`web/app.js`),
которые сервер команды логики отдаёт по `GET /` и `GET /app.js`. Скрипт —
ES-модуль: чистые функции (разбор ответа по правилу контракта п.5,
выбор пользовательского текста по `status`/`code`, модель состояния
страницы, контроллер запроса с тайм-аутом 45 с и защитой от второго
запроса) экспортируются и тестируются `node --test`; привязка к DOM
выполняется только в браузере. Без фреймворков, сборки и npm.

## Technical Context

**Language/Version**: HTML5, JavaScript (ES2022, модули); Node.js 24 для тестов

**Primary Dependencies**: нет; браузерные `fetch`, `AbortController`;
в тестах — встроенные `node:test`, `node:assert/strict`

**Storage**: N/A (история не хранится, FR/Assumptions)

**Testing**: `node --test 'web/*.test.js'` — добавляется строкой в
`scripts/check.sh` (отдельное поручение пользователя по принципу II);
сквозной прогон страницы в браузере — после реализации обеих команд

**Target Platform**: современный браузер, страница с `127.0.0.1:8055`

**Project Type**: web (статическая страница поверх API команды логики)

**Performance Goals**: интерфейс не зависает при вставке большого текста;
ответ — до 45 с ожидания

**Constraints**: один файл скрипта (контракт п.1 даёт только `/app.js`);
пользовательский текст — по `code`, не из `message` (контракт п.6);
тайм-аут 45 с, поздний ответ игнорируется (контракт п.8)

**Scale/Scope**: 1 экран, 6 состояний, ~200 строк JS, ~60 строк HTML

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Принцип | Как план его соблюдает | Статус |
|---|---|---|
| I. Только stdlib; `node --test` без npm | нет `package.json`, `node_modules`, CDN; тесты на `node:test` | ✅ |
| II. Тест сначала, `check.sh` не ослаблять | `web/app.test.js` пишется до `web/app.js`; в `check.sh` **добавляется** строка `node --test` — усиление, разрешено пользователем отдельным поручением; существующие строки не трогаются | ✅ (по отдельному поручению) |
| III. Без сети и модели в тестах | `fetch` подставляется параметром контроллера; тесты не открывают сокетов | ✅ |
| IV. Совместимость `review_diff`/`subscribe` | Python-код не меняется | ✅ |
| V. Единый контракт | страница реализует только контракт: путь, тело, правило разбора, тексты по коду, 45 с; контракт не меняется | ✅ |
| VI. `127.0.0.1` | страница использует относительный путь `/api/review` — тот же origin | ✅ |

**Re-check после Phase 1**: дизайн не добавил маршрутов (один файл
скрипта) и зависимостей — ✅.

## Project Structure

### Documentation (this feature)

```text
specs/001-review-ui/
├── plan.md
├── research.md
├── data-model.md          # исходы, состояния страницы, тексты
├── quickstart.md
├── contracts/
│   └── ui-states.md       # контракт «исход → что видит пользователь»
└── tasks.md               # /speckit.tasks
```

### Source Code (repository root = practices/practice_05)

```text
web/
├── index.html      # разметка: поле, кнопка, индикатор, результат, «подробнее»
├── app.js          # ES-модуль: чистые функции + привязка к DOM (только в браузере)
└── app.test.js     # node --test: чистые функции и контроллер с подставным fetch

scripts/check.sh    # + одна строка: node --test 'web/*.test.js'
```

**Structure Decision**: новый каталог `web/` — зона команды UI. Python-код
(`app/`, `tests/`) не трогается; сервер команды логики отдаёт файлы
`web/` как есть (контракт п.1).

## Complexity Tracking

Не требуется — нарушений нет; правка `check.sh` разрешена отдельным
поручением и является усилением проверки.
