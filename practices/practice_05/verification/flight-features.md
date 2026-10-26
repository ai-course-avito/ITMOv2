# Flight feature verification

Mocked Ignav; isolated temporary SQLite; no live fare request.

## Backend tests: PASS

```text
..........................                                               [100%]
=============================== warnings summary ===============================
.venv/lib/python3.14/site-packages/fastapi/testclient.py:1
  /Users/emilramazanov/itmo/vibecoding3s/ITMOv2/practices/practice_05/backend/.venv/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
26 passed, 1 warning in 0.96s
```

## After-edit hook tests: PASS

```text
✔ after-edit returns failure to agent, supports before args and patches, skips reports (1196.574542ms)
ℹ tests 1
ℹ suites 0
ℹ pass 1
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1283.731875
```

## Frontend build: PASS

```text
> cheap-flights-frontend@0.1.0 build
> tsc -b && vite build

vite v6.4.3 building for production...
transforming...
✓ 29 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.50 kB │ gzip:  0.35 kB
dist/assets/index-Ci7NowMQ.css    4.49 kB │ gzip:  1.50 kB
dist/assets/index-myd9hKPk.js   232.48 kB │ gzip: 72.51 kB
✓ built in 289ms
```

## Offline A/B scenario: PASS

```text
first=no_previous_price, second=compared, difference=-500.0 RUB (-12.5%), empty=no_current_price, invalid_http=422, mocked_upstream_calls=3, saved_rows=3
```

## Приёмка сортировки — 2026-10-26

После этого запуска пользователь сообщил: «я проверил все отлично работает». Ниже это подтверждение отнесено к условиям приёмки из `docs/features/price-sort.md`. Отдельные снимки интерфейса и журнал сетевых запросов пользователь не предоставлял; runner выше проверяет прежние backend-сценарии и сборку, но не взаимодействие с переключателем.

| Условие | Ожидание | Факт и доказательство |
|---|---|---|
| Первый показ | Выбрано «Сначала дешёвые», цены возрастают | Пользователь подтвердил работу всех условий; исходное значение `ascending` и сортировка проверяются в `frontend/src/App.tsx`. |
| Переключение | «Сначала дорогие» меняет порядок, возврат восстанавливает его | Пользователь подтвердил работу всех условий; переключатель и сортировка есть в `frontend/src/App.tsx`. |
| Равные цены | Исходный взаимный порядок сохраняется | Пользователь подтвердил работу всех условий; вторичным ключом служит индекс карточки из ответа. |
| Без побочных действий | Нет нового запроса или записи истории; форма, сравнение и кеш прежние | Пользователь подтвердил работу всех условий; обработчик выбора меняет только `priceOrder`. Отдельный сетевой журнал не сохранён. |
| Пустой и одиночный ответ | Пустой ответ скрывает выбор; одна карточка показана в обоих режимах | Пользователь подтвердил работу всех условий; существующее сообщение осталось, выбор выводится только при непустом списке. |
| Новый успешный поиск | Выбран порядок «Сначала дешёвые» | Пользователь подтвердил работу всех условий; сброс выполняется после успешного ответа. |
| Ошибка поиска | Сохраняется прежнее сообщение об ошибке | Пользователь подтвердил работу всех условий; runner прошёл ошибочный backend-сценарий. |

Итог: пользователь принял интерфейс. Пошаговые результаты его ручной проверки не записаны.
