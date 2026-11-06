# Research: HTTP API ревью диффа

Все «NEEDS CLARIFICATION» закрыты контрактом
[specs/contract/review-api.md](../contract/review-api.md); здесь — только
технические решения команды логики.

## R1. Сервер: `ThreadingHTTPServer` + `BaseHTTPRequestHandler`

- **Decision**: `http.server.ThreadingHTTPServer` с собственным классом
  обработчика.
- **Rationale**: стандартная библиотека (принцип I); поток на соединение
  закрывает FR-012 — запрос, ждущий модель до 30 с, не блокирует остальные.
- **Alternatives**: `HTTPServer` (однопоточный — нарушает FR-012);
  `asyncio`-сервер вручную (больше кода, `review_diff` всё равно
  синхронный); `wsgiref` (не даёт управлять отказом до чтения тела удобнее,
  чем `BaseHTTPRequestHandler`).

## R2. Инъекция клиента модели и каталога статики

- **Decision**: фабрика `create_server(port, client, static_dir)` строит
  класс обработчика через замыкание/атрибуты сервера; `main()` решает,
  какого клиента подставить (`OllamaClient` или `FakeModelClient` при
  `--fake-model`).
- **Rationale**: тот же приём, что у `review_diff(diff, client=None)`;
  тесты поднимают сервер с `ExplodingClient`, `TimeoutClient` и т.п. и
  временным каталогом статики.
- **Alternatives**: глобальная переменная клиента (тесты мешают друг другу
  в потоках); подмена через `unittest.mock.patch` (хрупко, проверяет
  реализацию, а не поведение).

## R3. Лимит тела 1 МиБ без чтения тела

- **Decision**: читать `Content-Length`; если заголовка нет или он не целое
  неотрицательное число — `invalid_request` (400); если больше
  `MAX_REQUEST_BYTES = 1048576` — `request_too_large` (413) **без вызова
  `rfile.read`**, с `close_connection = True` (непрочитанное тело нельзя
  оставлять в keep-alive соединении).
- **Rationale**: контракт п.4: «отказ до чтения тела по `Content-Length`».
- **Alternatives**: читать тело кусками до лимита (лишний код; заголовок и
  так обязателен для `fetch` со строковым телом); `Transfer-Encoding:
  chunked` не поддерживается — без `Content-Length` это `invalid_request`.

## R4. Отображение ответа и ошибок

- **Decision**: `{"ok": 200, "rejected": 400, "error": 502}[result["status"]]`;
  тело — словарь `review_diff` как есть, `json.dumps(ensure_ascii=False)`,
  `Content-Type: application/json; charset=utf-8`. Ошибки HTTP-слоя —
  одна функция `_send_request_error(code)` с таблицей code → HTTP-код и
  `message` для разработчика.
- **Rationale**: FR-002/FR-003, контракт п.3–4; единая точка — меньше
  шансов разойтись с таблицей контракта.
- **Alternatives**: исключения как управляющий поток — запутаннее.

## R5. Как тесты остаются «без сети» (принцип III)

- **Decision**: сервер в тесте слушает `127.0.0.1:0`, запросы — через
  `http.client.HTTPConnection` к нему же; клиент модели всегда подставной.
- **Rationale**: принцип III запрещает реальное сетевое соединение к
  внешним сервисам и ожидание настоящей модели; loopback к собственному
  тестовому серверу — это и есть проверяемый объект (сквозной HTTP-путь).
- **Alternatives**: вызывать обработчик без сокета (не проверяет
  HTTP-разбор, заголовки, коды — главное в этой фиче); `urllib` (кидает
  исключение на 4xx/5xx — неудобно читать тело; `http.client` проще).

## R6. Методы и пути

- **Decision**: `do_GET`, `do_POST`, `do_PUT`, `do_DELETE`, `do_PATCH`
  маршрутизируют одинаково: путь `/api/review` + не `POST` → 405;
  неизвестный путь → 404; `GET /` → `web/index.html`
  (`text/html; charset=utf-8`); `GET /app.js` → `web/app.js`
  (`text/javascript; charset=utf-8`). Query string отбрасывается при
  маршрутизации. Отсутствующий файл статики → 404 `not_found`.
- **Rationale**: контракт п.1, п.4; `HEAD` и `OPTIONS` не реализуем —
  `BaseHTTPRequestHandler` ответит 501 сам, контракт их не упоминает.
- **Alternatives**: `SimpleHTTPRequestHandler` для статики — отдаёт весь
  каталог и листинг, шире, чем два файла из контракта.

## R7. Демо-режим и порт

- **Decision**: `python3 -m app.server [--fake-model]`; порт из
  `REVIEW_PORT` (по умолчанию 8055), невалидное значение — понятная ошибка
  и код выхода 2. `FakeModelClient.complete()` возвращает фиксированный
  текст «демо-режим» и не открывает сокетов.
- **Rationale**: контракт п.1, п.9; FR-010, FR-011, FR-013.
- **Alternatives**: переменная окружения для демо — контракт выбрал флаг.

## R8. Журнал запросов

- **Decision**: `log_message` пишет в stderr только если сервер создан с
  `verbose=True` (по умолчанию для `main()`), тесты создают тихий сервер.
- **Rationale**: чистый вывод `check.sh`; в демо видно запросы.
