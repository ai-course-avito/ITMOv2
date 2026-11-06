# Contract: клиент API (`frontend/src/api.js`)

HTTP-формат — [specs/contract.md](../../contract.md) §2.4–2.5. Этот файл фиксирует, как
фронтенд его вызывает.

## Константы

| Имя | Значение |
|-----|----------|
| `API_BASE` | `"http://localhost:8000"` |
| `REQUEST_TIMEOUT_MS` | `5000` |

## `getLeaderboard({ signal? }) → Promise<ApiResult>`

- `GET {API_BASE}/leaderboard` (без `limit` — по умолчанию 10).
- `200` → `{ ok: true, data: { entries, total, last_result } }`.

## `saveRaceResult({ name, lapTimeMs }, { signal? }) → Promise<ApiResult>`

- `POST {API_BASE}/race-results`, `Content-Type: application/json`,
  тело `{ "name": name, "lap_time_ms": lapTimeMs }` — ровно два поля.
- `201` → `{ ok: true, data: { name, lap_time_ms, best_time_ms, is_new_record, place } }`.
- Вызывающий код **не** вызывает функцию, если `lapTimeMs` вне `[3000, 5 999 999]`.

## Классификация (`classify`)

| Исход | `kind` |
|-------|--------|
| `fetch` отклонён (сеть, CORS, сервер выключен) | `retryable` |
| Нет ответа за 5000 мс (таймаут) | `retryable` |
| `503`, любой другой `5xx` | `retryable` |
| `422`, `413`, любой другой `4xx` | `rejected` |
| Отменён внешним `signal` («Новая игра») | `aborted` |
| Ответ 2xx с невалидным JSON | `retryable` |

- Текст `detail` сервера не используется.
- Функции не бросают исключений — всегда возвращают `ApiResult`.
- Таймаут и внешний `signal` объединяются: внешняя отмена → `aborted`, свой таймер → `retryable`.

## Проверки (`frontend/tests/api.test.js`, `node --test`, `fetch` подменён)

| Given | When | Then |
|-------|------|------|
| `fetch` отвечает 200 с таблицей | `getLeaderboard()` | `ok: true`, `data` как в ответе |
| `fetch` отклоняется | `getLeaderboard()` | `kind: "retryable"` |
| `fetch` не отвечает | прошло 5000 мс | `kind: "retryable"` |
| ответ 503 | `saveRaceResult(...)` | `kind: "retryable"` |
| ответ 422 / 413 | `saveRaceResult(...)` | `kind: "rejected"` |
| внешний `signal` отменён | `saveRaceResult(...)` | `kind: "aborted"` |
| — | `saveRaceResult({name:"Камила", lapTimeMs:65400})` | тело запроса ровно `{"name":"Камила","lap_time_ms":65400}` |
