# Контракт UI: исход → что видит пользователь

Внешний стык страница ↔ API — только
[specs/contract/review-api.md](../../contract/review-api.md). Этот файл —
обязательства страницы перед пользователем; по нему пишутся тесты
`web/app.test.js` и сквозная проверка.

## Экспорт `web/app.js` (для тестов)

```text
canSubmit(text) -> boolean
interpretResponse(httpStatus, bodyText) -> Outcome
userText(outcome) -> string | null        # null для ok
viewState(outcome) -> {showReview, showStats, message, details}
createReviewer({fetchImpl, timeoutMs = 45000}) -> { review(diff) -> Promise<Outcome> | null }
REQUEST_TIMEOUT_MS = 45000
```

## Обязательства

| Исход | Ревью | Статистика | Основной текст | «Подробнее» |
|---|---|---|---|---|
| `ok` | да | да | — | — |
| `rejected` / `empty_diff` | нет | нет | USER_TEXT.empty_diff | message |
| `rejected` / `diff_too_large` | нет | нет | USER_TEXT.diff_too_large | message |
| `request_error` / `request_too_large` | нет | нет | тот же, что diff_too_large | message |
| `model_error` / `model_*` | нет | да | USER_TEXT[code] | message |
| `request_error` / прочие | нет | нет | USER_TEXT.network | message |
| `network` | нет | нет | USER_TEXT.network | причина (тайм-аут, не JSON…) |

Основной текст никогда не равен `message` сервера.
