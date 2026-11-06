# Implementation Plan: HTTP API ревью диффа

**Branch**: `002-review-api` | **Date**: 2026-10-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-review-api/spec.md`; общий
контракт стыка — [specs/contract/review-api.md](../contract/review-api.md).

## Summary

Локальный HTTP-сервер на `http.server.ThreadingHTTPServer` (только
`127.0.0.1`) — прозрачная обёртка над `review_diff`: `POST /api/review`
разбирает JSON `{"diff": ...}`, вызывает `review_diff` и отдаёт его словарь
с кодом 200/400/502 по `status`; ошибки самого HTTP-слоя — `request_error`
(400/413/405/404). Тот же процесс отдаёт файлы страницы `web/index.html` и
`web/app.js`, которые пишет команда UI. Клиент модели и каталог статики
передаются параметрами, поэтому тесты поднимают настоящий сервер на
свободном порту с подставной моделью — без сети и без Ollama.

## Technical Context

**Language/Version**: Python 3.10+ (на машине 3.14)

**Primary Dependencies**: только стандартная библиотека: `http.server`,
`json`, `argparse`, `pathlib`; в тестах — `http.client`, `threading`,
`tempfile`, `unittest`

**Storage**: N/A (каждый запрос самодостаточен)

**Testing**: `unittest` через `sh scripts/check.sh`; настоящие
HTTP-запросы к серверу, поднятому в тесте на порту 0

**Target Platform**: Linux, локальный запуск на `127.0.0.1`

**Project Type**: web-service (один процесс: API + отдача двух статических файлов)

**Performance Goals**: один пользователь; медленный запрос к модели (до
30 с) не блокирует другие запросы (FR-012)

**Constraints**: тело запроса ≤ 1 МиБ, отказ по `Content-Length` до чтения
тела; ответы всегда JSON без трассировок; адрес фиксирован `127.0.0.1`

**Scale/Scope**: 3 маршрута, 1 модуль, ~150 строк кода

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Принцип | Как план его соблюдает | Статус |
|---|---|---|
| I. Только стандартная библиотека | `http.server`, `json`, `argparse`; новых зависимостей нет | ✅ |
| II. Тест сначала, `check.sh` | `tests/test_server.py` пишется до `app/server.py`, падение показывается; `check.sh` не меняется этой командой (его расширяет команда UI по отдельному поручению) | ✅ |
| III. Без сети и настоящей модели в тестах | сервер принимает `client` параметром; тесты используют подставные клиенты; сеть — только loopback к собственному тестовому серверу, Ollama не вызывается | ✅ (loopback-сокет к своему серверу — не внешняя сеть; см. research R5) |
| IV. Совместимость `review_diff`/`subscribe` | `review_diff` вызывается как есть, словарь не меняется; `subscribe` не затрагивается | ✅ |
| V. Единый контракт стыка | все коды, пути, лимиты, флаг — из `specs/contract/review-api.md`; контракт не меняется | ✅ |
| VI. Только `127.0.0.1` | адрес зашит, не конфигурируется; тест проверяет `server_address` | ✅ |

Нарушений нет; Complexity Tracking не заполняется.

**Re-check после Phase 1**: дизайн не добавил зависимостей и маршрутов
сверх контракта — ✅.

## Project Structure

### Documentation (this feature)

```text
specs/002-review-api/
├── plan.md              # этот файл
├── research.md          # Phase 0: решения и альтернативы
├── data-model.md        # Phase 1: запрос, ответы, конфигурация запуска
├── quickstart.md        # Phase 1: как запустить и проверить вручную
├── contracts/
│   └── server-interface.md  # внутренний интерфейс модуля (запуск, фабрика сервера)
└── tasks.md             # Phase 2: /speckit.tasks
```

### Source Code (repository root = practices/practice_05)

```text
app/
├── review.py            # без изменений (review_diff)
├── ollama_client.py     # без изменений
└── server.py            # НОВЫЙ: HTTP-слой, запуск `python3 -m app.server`

tests/
└── test_server.py       # НОВЫЙ: HTTP-тесты против сервера на порту 0

web/                     # принадлежит команде UI (001-review-ui); сервер только читает
├── index.html
└── app.js
```

**Structure Decision**: существующая плоская структура `app/` + `tests/`.
Команда логики создаёт и меняет только `app/server.py` и
`tests/test_server.py`; каталог `web/` читает, но не пишет — его файлы
предоставляет команда UI (контракт п.1).

## Complexity Tracking

Не требуется — нарушений конституции нет.
