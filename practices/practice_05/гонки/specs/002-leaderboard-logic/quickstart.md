# Quickstart: проверка таблицы рекордов (бэкенд)

Контракт — [contracts/leaderboard-api.md](contracts/leaderboard-api.md), данные —
[data-model.md](data-model.md).

## Предусловия

- Python ≥ 3.10, зависимости из `backend/requirements.txt` (новых нет).
- Сервер запускается одним процессом (без `--workers`).

## 1. Автоматическая проверка (обязательна, Принцип III)

```bash
bash scripts/check.sh
```

Ожидаемо: последняя строка `PASS: ruff + тесты зелёные`.

Сценарии спеки → тесты:

| Сценарии | Файл | Что проверяется |
|----------|------|-----------------|
| US2-1…US2-6, US2-8…US2-10 | `backend/tests/test_leaderboard_api.py` | рекорд, строгое улучшение, равное время, повтор, имена по умолчанию, регистр |
| US3-1…US3-5, US3-8…US3-10 | `backend/tests/test_leaderboard_api.py` | пустая таблица, порядок, `limit`, `total`, равные места, `last_result` |
| US3-6, US3-7 | `backend/tests/test_leaderboard_store.py` | новый экземпляр хранилища на том же файле видит те же данные |
| US4-1…US4-7 | `backend/tests/test_leaderboard_api.py` | 422 / 413, хранилище не изменилось |
| US4-8…US4-10 | `backend/tests/test_leaderboard_store.py` и `…_api.py` | 503 при записи и при повреждённом файле, файл не тронут; нет файла → пусто |
| US4-11 | `backend/tests/test_leaderboard_api.py` | 20 параллельных POST → `total = 20` |
| Edge Cases (пробелы, `\t`, эмодзи) | `backend/tests/test_leaderboard_api.py` | нормализация и подсчёт длины в кодовых точках |

## 2. Ручная проверка

```bash
cd backend && uvicorn app.main:app --port 8000
```

В другом терминале:

```bash
curl -s localhost:8000/leaderboard
# → {"entries":[],"total":0,"last_result":null}   (если backend/leaderboard.json ещё нет)

curl -s -X POST localhost:8000/race-results -H 'Content-Type: application/json' \
  -d '{"name":"  Камила  ","lap_time_ms":41250}'
# → 201, "name":"Камила","best_time_ms":41250,"is_new_record":true,"place":1

curl -s -X POST localhost:8000/race-results -H 'Content-Type: application/json' \
  -d '{"name":"камила","lap_time_ms":45000}'
# → 201, "best_time_ms":41250,"is_new_record":false

curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:8000/race-results \
  -H 'Content-Type: application/json' -d '{"name":"Камила","lap_time_ms":"41250"}'
# → 422

curl -s localhost:8000/leaderboard
# → одна строка «Камила» 41250, last_result — 45000
```

Перезапустить uvicorn и снова запросить `/leaderboard` — данные те же (US3-6).

Повреждённый файл: записать в `backend/leaderboard.json` строку `{не json`, запросить
`/leaderboard` → 503 `{"detail":"Хранилище рекордов недоступно"}`, содержимое файла не изменилось.
После проверки удалить файл.

## 3. Что не меняется

`git diff --stat frontend/` — пусто (Принципы I и II: фронтенд, физика и управление не тронуты).
