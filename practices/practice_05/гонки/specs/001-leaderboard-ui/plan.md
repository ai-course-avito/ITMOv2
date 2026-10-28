# Implementation Plan: Таблица рекордов гонки (UI)

**Branch**: `001-leaderboard-ui` | **Date**: 2026-10-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-leaderboard-ui/spec.md`

**Contract**: [specs/contract.md](../contract.md) — источник истины по API, ошибкам и таймеру.

## Summary

Добавить во фронтенд (Vue 3) поле имени для каждого игрока, таймер гонки, экран сохранения
результата и таблицу рекордов (топ-10 + строка «Последняя гонка»). Фронтенд вызывает уже
существующие эндпоинты `POST /race-results` и `GET /leaderboard` строго по контракту, с таймаутом
5 с и разделением ошибок на повторяемые и неповторяемые. Чистая логика (формат времени,
нормализация имени, правила показа таблицы, классификация ошибок, выбор победителя) выносится в
JS-модули без зависимостей от Vue и проверяется встроенным `node --test`. Бэкенд, физика и
управление не меняются.

## Technical Context

**Language/Version**: JavaScript (ES2022, ES-модули), Vue 3.5 (`<script setup>`, Composition API);
Node 24 для сборки и тестов

**Primary Dependencies**: vue 3, vite 8, three (уже есть). Новых зависимостей нет

**Storage**: нет на клиенте (рекорды хранит сервер); имена живут в состоянии вкладки

**Testing**: `node --test` (встроен в Node, без пакетов) для чистых модулей в `frontend/tests/`;
запускается вручную, в `scripts/check.sh` **не** добавляется (решение человека 2026-10-28).
`scripts/check.sh` (ruff + pytest бэкенда) должен оставаться PASS

**Target Platform**: современный десктопный браузер с WebGL; локально Vite dev-server `:5173`,
API `http://localhost:8000`

**Project Type**: web application (frontend + backend); меняется только `frontend/`

**Performance Goals**: таймер обновляется каждый кадр игрового цикла (~60 раз/с, SC-002 ≥ 10);
таблица или её состояние видны ≤ 2 с после открытия (SC-003)

**Constraints**: таймаут запросов 5 с; бэкенд не трогать; `updatePhysics`, `checkLap`,
`keepInsideTrack`, `CAR_MODELS`, обработчики клавиш — без изменений

**Scale/Scope**: 1 экранный компонент нового вида (`Leaderboard.vue`), 2 JS-модуля, правки
`App.vue`; ~15 требований, 4 истории

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Принцип | Проверка | Статус |
|---------|----------|--------|
| I. Стек FastAPI + Vue 3 | Только Vue 3 Composition API и стандартные Web API (`fetch`, `AbortController`, `performance.now`). Новых зависимостей и фреймворков нет; в `package.json` добавляется только скрипт `"test": "node --test tests/"` | ✅ PASS |
| II. Физика и управление | `updatePhysics`, `checkLap`, `keepInsideTrack`, параметры `CAR_MODELS`, раскладка и `onKeyDown/onKeyUp` не меняются. Меняется только `declareWinner` (выбор победителя при финише в одном кадре) — согласовано человеком 2026-10-28 (контракт В3, spec FR-014/FR-015) | ✅ PASS (согласованное изменение) |
| III. Зелёный `scripts/check.sh` | Бэкенд не меняется; baseline 2026-10-28: 66 passed, PASS. После каждой задачи — `bash scripts/check.sh` → PASS. Сам `check.sh` не меняется | ✅ PASS |
| IV. Given/When/Then | Все FR спеки ссылаются на сценарии; чистые модули покрываются `node --test` по этим сценариям (см. [quickstart.md](quickstart.md)) | ✅ PASS |
| V. Решения — человеку | Открытый вопрос (тесты фронтенда) задан и решён: `node --test` без `check.sh`. Остальное взято из спеки и контракта | ✅ PASS |

**Зависимость**: эндпоинты `/race-results` и `/leaderboard` уже реализованы в `backend/`
(сейчас не закоммичены — работа команды логики, спека 002). Эта фича их **использует, но не
меняет**; перед слиянием 001 они должны быть влиты.

## Project Structure

### Documentation (this feature)

```text
specs/001-leaderboard-ui/
├── plan.md              # этот файл
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── api-client.md    # функции клиента API ↔ HTTP по specs/contract.md
│   └── ui-components.md # Leaderboard.vue и новые элементы App.vue
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
frontend/
├── package.json            # + "test": "node --test tests/"
├── src/
│   ├── App.vue             # правки: имена, таймер, финиш, статус сохранения, таблица
│   ├── Leaderboard.vue     # новый: таблица рекордов (4 состояния + «Последняя гонка»)
│   ├── api.js              # новый: API_BASE, fetch с таймаутом 5 с, классификация ошибок
│   ├── raceLogic.js        # новый: чистые функции (имя, время, таблица, победитель)
│   ├── ReportErrorButton.vue  # без изменений
│   ├── scene3d.js          # без изменений
│   ├── main.js             # без изменений
│   └── style.css           # без изменений
└── tests/
    ├── raceLogic.test.js   # новый: node --test
    └── api.test.js         # новый: node --test с подменённым fetch

backend/                     # НЕ МЕНЯЕТСЯ
scripts/check.sh             # НЕ МЕНЯЕТСЯ
```

**Structure Decision**: веб-приложение; меняется только `frontend/`. Логика без Vue вынесена в
`raceLogic.js` и `api.js`, чтобы тестировать её `node --test` без браузера и без новых пакетов.
UI таблицы — отдельный компонент `Leaderboard.vue`, т. к. он показывается на двух экранах.
Существующий `App.vue` остаётся владельцем состояния игры.

## Complexity Tracking

Нарушений конституции нет.
