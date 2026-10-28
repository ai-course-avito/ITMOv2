# Data Model: Таблица рекордов гонки (логика)

Источник требований — [spec.md](spec.md) (FR-006…FR-018) и [../contract.md](../contract.md) 2.1–2.4.

## Входные данные

### RaceResult — тело `POST /race-results`

| Поле | Тип | Правила | Ошибка |
|------|-----|---------|--------|
| `name` | string | нормализация: `" ".join(name.split())`; длина 1–20 кодовых точек | 422 |
| `lap_time_ms` | int (строгий) | 3000 ≤ x ≤ 5 999 999; строка, дробное, bool отклоняются | 422 |
| *лишние поля* | — | `extra="forbid"` | 422 |

Производное значение: **ключ имени** `key = name.casefold()` (после нормализации).

## Хранимые данные (файл `backend/leaderboard.json`)

```json
{
  "version": 1,
  "records": {
    "камила": {
      "name": "Камила",
      "best_time_ms": 39800,
      "achieved_at": "2026-10-28T10:00:00.000000Z"
    }
  },
  "last_result": {
    "name": "Камила",
    "lap_time_ms": 45000,
    "finished_at": "2026-10-28T11:00:00.000000Z"
  }
}
```

### NameRecord — значение в `records`, ключ словаря — ключ имени

| Поле | Тип | Смысл |
|------|-----|-------|
| `name` | string | Написание имени при установке текущего рекорда |
| `best_time_ms` | int | Лучшее время круга |
| `achieved_at` | string, UTC ISO 8601 | Когда установлен текущий рекорд |

Число записей не ограничено (FR-012).

### LastResult — `last_result`, один на всё хранилище или `null`

| Поле | Тип | Смысл |
|------|-----|-------|
| `name` | string | Нормализованное имя из последнего успешного POST |
| `lap_time_ms` | int | Время именно этой гонки |
| `finished_at` | string, UTC ISO 8601 | Когда результат сохранён |

### Проверка структуры при чтении

Файл считается корректным, если: это объект; `version == 1`; `records` — объект, каждое значение
содержит `name` (str), `best_time_ms` (int), `achieved_at` (str); `last_result` — `null` или объект
с `name` (str), `lap_time_ms` (int), `finished_at` (str). Иначе — `StorageError` → 503, файл не
меняется. Отсутствие файла = `{"version": 1, "records": {}, "last_result": null}`.

## Алгоритм сохранения результата (под блокировкой)

```text
state = load()                         # нет файла → пустое; повреждён → StorageError (503)
key = name.casefold(); now = clock()
rec = state.records.get(key)
if rec is None or lap_time_ms < rec.best_time_ms:      # строго меньше (FR-010)
    state.records[key] = {name, best_time_ms: lap_time_ms, achieved_at: now}
    is_new_record = True
else:
    is_new_record = False              # равное или худшее время: рекорд, написание, achieved_at не меняются
state.last_result = {name, lap_time_ms, finished_at: now}   # при каждом успешном POST (FR-013a)
save(state)                            # атомарно; OSError → StorageError (503)
place = rank(state).index(key) + 1
return {name, lap_time_ms, best_time_ms: state.records[key].best_time_ms, is_new_record, place}
```

Повтор того же запроса: время равно рекорду → `is_new_record = false`, рекорд не меняется
(безопасный повтор, US2-5); `last_result.finished_at` обновляется.

## Ранжирование

`rank(state)` — ключи, отсортированные по `(best_time_ms, achieved_at, key)`; место = позиция + 1,
номера мест не повторяются (В2). Время всегда пишется в одном фиксированном формате
`YYYY-MM-DDTHH:MM:SS.ffffffZ`, поэтому сравнение строк `achieved_at` совпадает с хронологическим.

## Выходные данные

- **LeaderboardEntry**: `place` (int), `name`, `best_time_ms` (int), `achieved_at`.
- **LastResultOut**: `name`, `lap_time_ms`, `place` (текущее место имени по лучшему времени),
  `finished_at`; или `null`.
- **Leaderboard**: `entries` (первые `limit` строк ранжирования), `total` (число записей),
  `last_result`.
- **SaveResultResponse**: `name`, `lap_time_ms`, `best_time_ms`, `is_new_record`, `place`.

Точные схемы и примеры — [contracts/leaderboard-api.md](contracts/leaderboard-api.md).
