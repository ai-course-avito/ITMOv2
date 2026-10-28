# Data Model: Таблица рекордов гонки (UI)

Клиентские сущности и состояния. Форматы HTTP — в [specs/contract.md](../contract.md) §2.4;
здесь только то, что хранит и показывает фронтенд.

## PlayerName (на каждого из двух игроков)

| Поле | Тип | Правило |
|------|-----|---------|
| `raw` | string | Значение поля ввода; начальное «Игрок 1» / «Игрок 2»; ≤ 20 кодовых точек |
| `error` | `null \| "empty" \| "duplicate"` | Выставляется при «Начать заезд!», сбрасывается при вводе |

- `normalize(raw) = raw.trim().replace(/\s+/g, " ")` — записывается в `raw` при старте.
- `key(name) = normalize(name).toLowerCase()`.
- `"empty"`: `normalize(raw) === ""` → «Введите имя».
- `"duplicate"` (у обоих): `key(p1) === key(p2)` → «Имена игроков должны различаться».
- Сохраняется между «Новая игра» → «Выбор» (живёт в состоянии вкладки).

## RaceClock / таймер

| Поле | Тип | Правило |
|------|-----|---------|
| `phase` | `"idle" \| "countdown" \| "running" \| "finished" \| "aborted"` | Совпадает с контрактом 2.7 |
| `startMs` | number \| null | `performance.now()` в момент окончания отсчёта |
| `elapsedMs` | number | `now − startMs`, обновляется каждый кадр в `running` |
| `lapTimeMs` | int \| null | `Math.round(now − startMs)` кадра финиша |

Переходы (соответствие существующему `gameState`):

```
idle(select) ──«Начать заезд!»──► countdown ──отсчёт=0──► running(racing)
running ──финиш (1 или 2 машинки в кадре)──► finished(gameover)
running ──ошибка 3D──► aborted (racing + sceneError)
finished ──«Новая игра»──► idle ; aborted ──«Назад к выбору»──► idle
```

`phase` выводится из `gameState` + `sceneError`; отдельной переменной не требуется.

## Winner

| Поле | Тип | Правило |
|------|-----|---------|
| `player` | 1 \| 2 | `pickWinner(frameFinishers, random)`; при двух кандидатах — 50/50 |
| `name` | string | Нормализованное имя игрока (вместо «Игрок N») |
| `model`, `color`, `hex` | как сейчас | без изменений |
| `lapTimeMs` | int | см. RaceClock |

## SaveStatus (экран «Финиш»)

`"saving" | "saved" | "error" | "rejected" | "out_of_range"`

| Значение | Текст | «Повторить» |
|----------|-------|-------------|
| `saving` | «Сохраняем результат…» | нет |
| `saved` | «Результат сохранён ✓» | нет |
| `error` | «Не удалось сохранить результат» | да |
| `rejected` | «Результат не сохранён: некорректные данные» | нет |
| `out_of_range` | «Результат не сохранён: время вне допустимого диапазона» | нет |

Вместе с `saved` хранится ответ POST (`name`, `is_new_record`) — для бейджа «Новый рекорд!».

## LeaderboardView

| Поле | Тип | Правило |
|------|-----|---------|
| `state` | `"loading" \| "empty" \| "data" \| "error"` | `empty`, если `entries.length === 0` |
| `board` | ответ `GET /leaderboard` \| null | `{ entries, total, last_result }` |
| `highlightKey` | string \| null | ключ имени `last_result`, если оно в `entries` |
| `newRecordKey` | string \| null | только на «Финише»: ключ из ответа POST при `is_new_record` и имени в `entries` |
| `showLastRow` | boolean | `last_result != null && last_result.place > entries.length` |

Загружается: при входе на «Выбор», после завершения сохранения на «Финише», по «Повторить».

## ApiResult (результат клиента API)

`{ ok: true, data } | { ok: false, kind: "retryable" | "rejected" | "aborted" }` —
классификация в [contracts/api-client.md](contracts/api-client.md).
