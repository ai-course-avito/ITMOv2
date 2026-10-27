# API contract projection: CONTRACT.md v1.0

Нормативный источник — [общий согласованный контракт](../../../../CONTRACT.md). Эта проекция не расширяет продуктовые решения.

## HTTP интерфейсы

- `GET /` → static/index.html команды UI; `GET /static/*` → её CSS/JS. Доступ только к выделенной static directory.
- `POST /api/reviews`, Content-Type application/json (допустим параметр charset=utf-8), тело ровно `{ "diff": "..." }`.
- Успех 200: `{ "request_id": "<UUID>", "mode": "demo|live", "summary": "...", "risks": [{ "file": "...", "line": 1, "evidence": "+...", "risk": "..." }], "checks": ["..."] }`.
- Ошибка: `{ "request_id": "<UUID>", "error": { "code": "...", "message": "безопасный русский текст" } }`; retryable и частичный результат отсутствуют.

Типы, длины и связи — [data-model.md](../data-model.md); точный конечный список секретов — [spec.md](../spec.md#поддерживаемые-секреты).

| Статус | code | Причина |
| --- | --- | --- |
| 415 | UNSUPPORTED_MEDIA_TYPE | Не JSON content type |
| 400 | INVALID_JSON | Неверный JSON |
| 422 | INVALID_REQUEST | Неверная форма/тип/лишнее поле/пустота |
| 413 | DIFF_TOO_LARGE | >20000 code points |
| 422 | INVALID_DIFF | Невалидная структура |
| 422 | UNSUPPORTED_DIFF | Binary, combined merge, rename-only, Git-экранированный путь |
| 503 | MODEL_NOT_CONFIGURED | Live без полного конфига |
| 504 | MODEL_TIMEOUT | Внешний вызов не завершён за 10 секунд |
| 502 | MODEL_UNAVAILABLE | Transport/provider error |
| 502 | INVALID_MODEL_OUTPUT | Ошибка JSON/структуры/доказательства результата |
| 500 | INTERNAL_ERROR | Непредвиденная ошибка приложения |

Проверки по порядку: content type → JSON → shape/type → size → empty → diff structure → settings → sanitize → analyze. После анализа: parse → sanitize output → validate full structure and evidence. Первый отказ определяет ответ, никакого вызова модели до успешной входной проверки. Timeout 10 секунд ограничивает весь await; серверная отмена распространяется на ожидание HTTPX. UI deadline 15 секунд не меняет серверный контракт.

## Внутренний adapter

Async adapter принимает очищенный diff с правилами/инструкцией формы, возвращает кандидата ModelReview либо безопасно классифицируемую ошибку. ReviewService независимо от режима проверяет финальный ответ. Adapter не формирует request_id и не выбирает режим из diff. Tests могут инъецировать контролируемый adapter без добавления тестовых переключателей в публичный API.

Live: один chat/completions HTTP POST, `model`, `messages`, без streaming и retries. Ответ: `choices[0].message.content` как JSON-строка. URL/model/key берутся из REVIEW_LLM_URL/MODEL/KEY; REVIEW_MODE определяет demo/live. Default demo явно отражён в ответе.
