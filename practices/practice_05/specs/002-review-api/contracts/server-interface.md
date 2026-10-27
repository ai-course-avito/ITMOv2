# Интерфейс модуля `app/server.py` (внутренний)

Внешний HTTP-контракт — только
[specs/contract/review-api.md](../../contract/review-api.md); здесь его не
дублируем. Этот файл описывает Python-интерфейс, на который опираются
тесты и запуск.

## Запуск

```
python3 -m app.server [--fake-model]
REVIEW_PORT=8055   # переменная окружения, необязательна
```

Адрес — всегда `127.0.0.1`. Невалидный `REVIEW_PORT` → сообщение в stderr,
код выхода 2.

## Функции и константы

```text
MAX_REQUEST_BYTES = 1048576
DEFAULT_PORT = 8055
WEB_DIR = <каталог проекта>/web

create_server(port=0, client=None, static_dir=WEB_DIR, verbose=False)
    -> ThreadingHTTPServer, привязанный к ("127.0.0.1", port).
       client=None → OllamaClient(); serve_forever() вызывает вызывающий.

class FakeModelClient:
    complete(system, user) -> str   # фиксированный текст, без сети

resolve_port(environ) -> int        # REVIEW_PORT или DEFAULT_PORT; ValueError
main(argv=None) -> int              # разбор флагов, запуск, код выхода
```
