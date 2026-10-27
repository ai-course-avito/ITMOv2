# Quickstart: HTTP API ревью диффа

Из `practices/practice_05`.

## Автоматическая проверка

```
sh scripts/check.sh
```

Ожидание: `tests/test_server.py` проходит вместе со старыми тестами.

## Ручная проверка в демо-режиме (без Ollama)

```
python3 -m app.server --fake-model
```

В другом терминале:

| Сценарий | Команда | Ожидание |
|---|---|---|
| успех | `curl -s -i -X POST localhost:8055/api/review -H 'Content-Type: application/json' -d '{"diff":"--- a\n+++ b\n+x"}'` | 200, `status: ok`, `stats` |
| пустой дифф | `... -d '{"diff":"  "}'` | 400, `rejected`/`empty_diff` |
| не JSON | `... -d 'oops'` | 400, `request_error`/`invalid_request` |
| неверный метод | `curl -s -i localhost:8055/api/review` | 405, `method_not_allowed` |
| неизвестный путь | `curl -s -i localhost:8055/nope` | 404, `not_found` |
| страница | `curl -s -i localhost:8055/` | 200, `text/html` (если команда UI уже положила `web/index.html`) |

## Ошибка модели

Без `--fake-model` и с остановленной Ollama корректный дифф даёт 502,
`status: error`, `code: model_unavailable` и `stats`.

Связанные документы: [data-model.md](data-model.md),
[contracts/server-interface.md](contracts/server-interface.md).
