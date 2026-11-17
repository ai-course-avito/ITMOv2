---
description: "Задачи команды логики: HTTP API ревью диффа"
---

# Tasks: HTTP API ревью диффа

**Input**: `specs/002-review-api/` (plan.md, spec.md, research.md, data-model.md, contracts/), контракт `specs/contract/review-api.md`

**Tests**: обязательны — принцип II конституции: тест пишется первым и падает до реализации.

**Файлы команды**: только `app/server.py` и `tests/test_server.py`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 Создать `tests/test_server.py` с помощниками: подъём `create_server(port=0, client=..., static_dir=<tmp>)` в фоне (`serve_forever` в потоке, `shutdown` в `tearDown`), запрос через `http.client.HTTPConnection` с возвратом (код, заголовки, разобранный JSON); подставные клиенты по образцу `tests/test_review.py` (`FakeClient`, `ExplodingClient`, `TimeoutClient`, `UnavailableClient`)

## Phase 2: Foundational

- [x] T002 Тест: сервер слушает только `127.0.0.1` (`server.server_address[0]`) — `tests/test_server.py`; показать падение (модуля нет)
- [x] T003 Каркас `app/server.py`: константы `MAX_REQUEST_BYTES`, `DEFAULT_PORT`, `WEB_DIR`; `create_server()` на `ThreadingHTTPServer(("127.0.0.1", port), Handler)`; `_send_json(code, body)` с `application/json; charset=utf-8`; тихий `log_message` при `verbose=False`

**Checkpoint**: T002 зелёный.

## Phase 3: User Story 1 — успешное ревью через HTTP (P1) 🎯 MVP

**Independent Test**: POST корректного диффа → 200 и словарь `review_diff`.

- [x] T004 [US1] Тесты в `tests/test_server.py`: успех → 200, тело равно `review_diff(diff, client)` (включая `stats`); незнакомые поля в JSON игнорируются → 200; дифф ровно `MAX_DIFF_BYTES` байт (многобайтные символы, тело JSON > 8192 байт) → 200 — показать падение
- [x] T005 [US1] `POST /api/review` в `app/server.py`: чтение тела по `Content-Length`, `json.loads`, вызов `review_diff(diff, client=self.server.model_client)`, HTTP по `status` (200/400/502)

## Phase 4: User Story 2 — понятный отказ (P1)

**Independent Test**: пустой/большой дифф и плохие запросы → правильные коды, модель не вызывается (`ExplodingClient`).

- [x] T006 [US2] Тесты: `empty_diff` → 400 `rejected`; `diff_too_large` → 400; тело не JSON → 400 `request_error`/`invalid_request`; JSON не объект, нет `diff`, `diff` не строка → 400 `invalid_request`; `Content-Length` 1048577 без тела → 413 `request_too_large` приходит без отправки тела (тайм-аут сокета 2 с); нет/некорректный `Content-Length` → 400 `invalid_request` — показать падение
- [x] T007 [US2] В `app/server.py`: проверки по порядку из data-model.md; `_send_request_error(code)` по таблице code → HTTP; при 413 тело не читать и `close_connection = True`
- [x] T008 [US2] Тесты маршрутизации: `GET /api/review` и `PUT /api/review` → 405 `method_not_allowed`; `GET /nope`, `POST /nope` → 404 `not_found`; все ответы — JSON с `application/json` — показать падение
- [x] T009 [US2] Маршрутизация `do_GET/do_POST/do_PUT/do_DELETE/do_PATCH` в `app/server.py`; query string отбрасывается

## Phase 5: User Story 3 — ошибка модели (P2)

**Independent Test**: каждый из клиентов-отказов → 502, код и `stats`.

- [x] T010 [US3] Тесты: `TimeoutClient` → 502 `model_timeout` со `stats`; `UnavailableClient` → 502 `model_unavailable` со `stats` — показать падение (или зелёный, если T005 уже даёт — тогда доказать мутацией: сломать 502 → тест падает)

## Phase 6: User Story 4 — демо без Ollama (P2)

- [x] T011 [US4] Тесты: `FakeModelClient().complete()` возвращает непустой текст без сокетов; `main(["--fake-model"])`-разбор выбирает `FakeModelClient` (через выделенную `build_client(args)`), без флага — `OllamaClient`; `resolve_port({})` = 8055, `resolve_port({"REVIEW_PORT": "9000"})` = 9000, `"abc"` → `ValueError`; в демо пустой дифф всё равно 400 `empty_diff` — показать падение
- [x] T012 [US4] `FakeModelClient`, `build_client`, `resolve_port`, `main()` с `argparse`; `if __name__ == "__main__": raise SystemExit(main())`

## Phase 7: Статика и параллельность (контракт п.1, FR-012, FR-014)

- [x] T013 Тесты: `GET /` → 200 `text/html` и байты `index.html` из временного каталога; `GET /app.js` → 200 `text/javascript`; файла нет → 404 `not_found`; медленный запрос (клиент ждёт `threading.Event`) не блокирует параллельный `GET /` — показать падение
- [x] T014 Отдача двух файлов из `static_dir` в `app/server.py`

## Phase 8: Polish

- [x] T015 `sh scripts/check.sh` — полный вывод; ручной прогон quickstart.md в демо-режиме
- [x] T016 Отчёт по задачам с `файл:строка`

## Dependencies & Execution Order

T001 → T002 → T003 → (US1: T004→T005) → (US2: T006→T007, T008→T009) → (US3: T010) → (US4: T011→T012) → (T013→T014) → T015 → T016.
Все задачи в двух файлах, поэтому [P] не ставится: параллельная правка одного файла создаёт конфликты.

## Implementation Strategy

MVP — US1 (успешный POST). Затем отказы (US2), затем ошибки модели (US3), демо (US4) и статика для страницы. Код команды UI не нужен для тестов логики: статику тесты кладут во временный каталог.
