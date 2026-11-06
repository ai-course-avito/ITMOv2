# Research: Веб-страница ревью диффа

Вопросы стыка закрыты контрактом
[specs/contract/review-api.md](../contract/review-api.md); здесь —
технические решения команды UI.

## R1. Один файл скрипта и тестируемость

- **Decision**: `web/app.js` — ES-модуль с `export` чистых функций; в конце
  `if (typeof document !== "undefined") init(document)`. Тесты импортируют
  модуль в Node, где `document` нет, и DOM-код не выполняется.
- **Rationale**: контракт даёт только `GET /app.js` — второго модуля
  страница загрузить не может; так логика проверяется без браузера.
- **Alternatives**: вынести логику в `logic.js` (нужен новый маршрут —
  менять контракт); тестировать только в браузере (ручная проверка вместо
  автоматической).

## R2. Node распознаёт ESM без `package.json`

- **Decision**: не создавать `package.json`; Node 24 определяет ES-модуль
  по синтаксису `import`/`export` (module syntax detection).
- **Проверено** 2026-10-22 на Node v24.22.0 в отдельном каталоге:
  `node --test web/app.test.js` → pass 1.
- **Грабли**: `node --test web/` (каталог) **падает** — Node 24 считает
  аргумент файлом (`✖ web … test failed`). Запуск — glob в кавычках:
  `node --test 'web/*.test.js'`.

## R3. Разбор ответа: тело первично (контракт п.5)

- **Decision**: `interpretResponse(httpStatus, bodyText)` → исход. Сначала
  `JSON.parse`; ошибка разбора, не-объект или `status` вне
  `ok/rejected/error/request_error` → исход `network`. HTTP-код в решении не
  участвует (сохраняется только для «подробнее»).
- **Rationale**: 400/502 несут полезные тела (`rejected`, `error` со
  `stats`); `response.ok` спутал бы ошибку модели с ошибкой сети.

## R4. Тексты для пользователя по `code` (контракт п.6–7)

- **Decision**: таблица `USER_TEXT` в `app.js`; `diff_too_large` и
  `request_too_large` — один текст; неизвестный `code` внутри известного
  `status` → обобщённый текст этого статуса; `message` — только в
  `<details>` «подробнее».
- **Rationale**: FR-009, FR-015; `message` бывает с `[Errno 111]`.

## R5. Тайм-аут 45 с и поздний ответ (контракт п.8)

- **Decision**: контроллер `createReviewer({fetchImpl, timeoutMs})` создаёт
  `AbortController` на запрос и таймер `timeoutMs` (по умолчанию 45000);
  по таймеру — `abort()` и исход `network`. Ответ после abort не
  обрабатывается: `fetch` отклоняется, а флаг завершения не даёт второй
  раз выставить исход.
- **Rationale**: FR-012, SC-005. Подставные `fetchImpl` и малый
  `timeoutMs` делают поведение проверяемым в `node --test` за миллисекунды.

## R6. Один запрос за раз

- **Decision**: контроллер хранит флаг «в полёте»; `review()` при активном
  запросе возвращает `null` и не вызывает `fetchImpl`. Кнопка в DOM ещё и
  `disabled` — две независимые защиты.
- **Rationale**: FR-004, SC-003; проверяется тестом с подставным `fetch`,
  считающим вызовы.

## R7. Пустой ввод не уходит на сервер

- **Decision**: `canSubmit(text)` = `text.trim() !== ""`; кнопка
  `disabled`, пока `canSubmit` ложно; `review()` на пустом вводе сразу
  возвращает исход `rejected/empty_diff` без вызова `fetch`.
- **Rationale**: FR-003, SC-002 (100% — без обращения к серверу).
