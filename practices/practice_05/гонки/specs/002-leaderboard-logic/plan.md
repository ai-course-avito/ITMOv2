# Implementation Plan: Таблица рекордов гонки (логика)

**Branch**: `002-leaderboard-logic` (работа ведётся в текущей ветке `practice_5`) | **Date**: 2026-10-28 |
**Spec**: [spec.md](spec.md) | **Contract**: [../contract.md](../contract.md)

**Input**: Feature specification from `specs/002-leaderboard-logic/spec.md`

## Summary

Серверная часть таблицы рекордов: `POST /race-results` принимает время победителя, нормализует
имя, обновляет лучший результат имени и последний результат; `GET /leaderboard` отдаёт топ-N,
`total` и `last_result`. Данные хранятся в одном JSON-файле на сервере (`backend/leaderboard.json`),
запись атомарная (временный файл + `os.replace`) и сериализована блокировкой. Фронтенд в этой
фиче не меняется — требования спеки, выполняемые на клиенте, вынесены в «Вне этой фичи».

## Technical Context

**Language/Version**: Python ≥ 3.10 (`target-version = "py310"` в ruff)

**Primary Dependencies**: FastAPI, Pydantic v2 (уже есть). Новых зависимостей нет — только
стандартная библиотека (`json`, `os`, `tempfile`, `threading`, `datetime`, `pathlib`).

**Storage**: JSON-файл `backend/leaderboard.json`, путь задаётся одной константой; в тестах
хранилище подменяется через `app.dependency_overrides` на файл в `tmp_path`.

**Testing**: pytest + `fastapi.testclient.TestClient` в `backend/tests/`, запуск через
`bash scripts/check.sh`.

**Target Platform**: локальный сервер uvicorn (один процесс), браузерный клиент на `:5173`.

**Project Type**: web-service (бэкенд веб-приложения).

**Performance Goals**: ответ ≤ 0,5 с при 1000 имён (SC-005) — чтение и сортировка файла на
каждый запрос укладываются с большим запасом.

**Constraints**: одно общее хранилище для всех клиентов; переживает перезапуск; атомарная запись;
повреждённый файл не перезаписывается; тело запроса ≤ 2048 байт (существующий middleware).

**Scale/Scope**: единицы–тысячи имён, единицы одновременных запросов; один процесс uvicorn.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Принцип | Проверка | Статус |
|---------|----------|--------|
| I. Стек FastAPI + Vue 3 | Только FastAPI/Pydantic и stdlib; новых зависимостей и фреймворков нет; `requirements.txt` не меняется | PASS |
| II. Физика и управление | `frontend/` не меняется вовсе → физика, управление и `checkLap` побайтово те же. Согласованный выбор победителя 50/50 (В3) в эту фичу не входит | PASS |
| III. `scripts/check.sh` | Новые тесты в `backend/tests/`, `check.sh` не меняется; каждая задача закрывается `PASS` | PASS (проверяется при реализации) |
| IV. Given/When/Then | Все FR спеки имеют сценарии; сценарии бэкенда → pytest-тесты (таблица в [quickstart.md](quickstart.md)) | PASS |
| V. Решения человека | Открытых вопросов в спеке нет; стек хранения задан пользователем; ограничение «один процесс» — существующий способ запуска, вынесено в Assumptions (см. research R6) | PASS |
| Тех. ограничения | Входные модели Pydantic с `extra="forbid"` | PASS |

**Повторная проверка после Phase 1**: дизайн не добавил зависимостей и не трогает фронтенд —
все гейты PASS.

## Scope

### В этой фиче (бэкенд)

FR-006, FR-007, FR-008, FR-009, FR-010, FR-011, FR-012, FR-013a, FR-014, FR-015, FR-016,
FR-017, FR-018, FR-019; FR-020 выполняется тривиально (фронтенд не меняется).
Сценарии: US2-1…US2-6, US2-8…US2-10; US3-1…US3-10; US4-1…US4-12.

### Вне этой фичи (клиент, `frontend/` не трогаем по решению пользователя)

| Требование | Что нужно на клиенте | Почему не здесь |
|------------|----------------------|-----------------|
| FR-001, FR-002, FR-005 (US1-1…4, US1-7, US1-8) | Замер времени и таймер по монотонным часам, формат ММ:СС.сс | Код игрового цикла в `App.vue` |
| FR-003 (US1-5, US1-9, US1-10) | Случайный победитель 50/50 при одновременном финише | Меняет `App.vue`; согласовано (В3), но фронтенд в этой фиче не трогаем |
| FR-004 (US1-6) | Не отправлять результат при ошибке 3D | Клиентская логика |
| FR-013 (US2-7) | Ровно один POST — победителя | Клиентская логика |

Эти требования остаются в спеке и должны войти в отдельную фичу фронтенда (вместе со спекой UI
001). Сервер к ним готов: контракт API от них не зависит.

## Project Structure

### Documentation (this feature)

```text
specs/002-leaderboard-logic/
├── plan.md              # этот файл
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── leaderboard-api.md   # Phase 1
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py            # + эндпоинты POST /race-results, GET /leaderboard, обработка 503
│   ├── models.py          # + RaceResult (вход), модели ответов
│   └── leaderboard.py     # новый: нормализация имени, ранжирование, LeaderboardStore (JSON-файл)
├── tests/
│   ├── test_leaderboard_store.py   # новый: хранилище, ранжирование, атомарность, повреждённый файл
│   └── test_leaderboard_api.py     # новый: сценарии US2–US4 через TestClient
└── leaderboard.json       # создаётся сервером при первой записи, в .gitignore

.gitignore                 # + backend/leaderboard.json
frontend/                  # не меняется
```

**Structure Decision**: существующая структура «бэкенд веб-приложения» (`backend/app`,
`backend/tests`). Логика хранения и ранжирования — в отдельном модуле `app/leaderboard.py`, чтобы
тестировать её без HTTP; эндпоинты — в `app/main.py` рядом с существующими.

## Assumptions

- Сервер работает одним процессом uvicorn (как сейчас); блокировка записи — внутри процесса
  ([research.md](research.md) R6). Несколько воркеров потребуют отдельного решения человека.
- Файл `backend/leaderboard.json` не хранится в git (как `backend/error_reports.log`).
- Ограничение тела 2048 байт (существующий middleware) проверяет только заголовок
  `Content-Length`; запрос без него (chunked) ограничение обходит. Известное ограничение,
  middleware в этой фиче не меняется.
- Сброс и редактирование рекордов — только вручную, удалением или правкой файла при
  остановленном сервере.

## Complexity Tracking

Нарушений конституции нет.
