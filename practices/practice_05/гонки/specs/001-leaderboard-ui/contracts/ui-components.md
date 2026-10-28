# Contract: UI-компоненты и чистые функции

## `Leaderboard.vue` (новый)

Показывается на экранах «Выбор» и «Финиш».

| Prop | Тип | Смысл |
|------|-----|-------|
| `state` | `"loading" \| "empty" \| "data" \| "error"` | состояние блока |
| `board` | `{ entries, total, last_result } \| null` | ответ `GET /leaderboard` |
| `newRecordKey` | `string \| null` | ключ имени для бейджа «Новый рекорд!» (только «Финиш») |

| Event | Когда |
|-------|-------|
| `retry` | нажата «Повторить» в состоянии `error` |

Отрисовка:

| `state` | Что видно |
|---------|-----------|
| `loading` | «Загрузка рекордов…» |
| `empty` | «Пока нет рекордов — станьте первым!» |
| `error` | «Не удалось загрузить рекорды» + кнопка «Повторить» |
| `data` | заголовок «🏆 Рекорды», колонки «Место», «Имя», «Лучшее время» (`formatTime(best_time_ms)`); строка имени `last_result` подсвечена, если оно в `entries`; бейдж «Новый рекорд!» у строки с `newRecordKey`; если `showLastResultRow(board)` — разделитель и строка «Последняя гонка»: `place · name · formatTime(lap_time_ms)` |

Длинное имя обрезается многоточием (`text-overflow: ellipsis`), ширина ≤ контейнера, без
горизонтальной прокрутки до 600 px.

## Изменения `App.vue`

| Место | Что добавляется |
|-------|-----------------|
| Экран «Выбор», карточка игрока | поле «Имя» + счётчик «N/20» + текст ошибки под полем |
| Экран «Выбор», над кнопкой старта | общий текст «Имена игроков должны различаться» |
| Экран «Выбор», под кнопкой старта | `<Leaderboard>` |
| HUD гонки | имена игроков вместо «Игрок 1/2»; по центру таймер `ММ:СС.сс` вместо статичного «ФИНИШ: 1 КРУГ» рядом с ним |
| Экран «Финиш» | «ПОБЕДИЛ {ИМЯ}!», «Время круга: ММ:СС.сс», статус сохранения (+ «Повторить» при `error`), `<Leaderboard>` |

Не меняются: `updatePhysics`, `checkLap`, `keepInsideTrack`, `CAR_MODELS`, `CAR_COLORS`,
`onKeyDown`, `onKeyUp`, `trackConfig`, `scene3d.js`.

## `raceLogic.js` (новый, без Vue)

| Функция | Вход → выход | Сценарии spec |
|---------|--------------|---------------|
| `nameLength(s)` | string → число кодовых точек | US1-6 |
| `clampName(s, max = 20)` | string → string ≤ max кодовых точек | US1-6 |
| `normalizeName(s)` | string → string | US1-8, Edge |
| `nameKey(s)` | string → `normalizeName(s).toLowerCase()` | US1-7, US3-15 |
| `validateNames(n1, n2)` | → `{ p1: null\|"empty"\|"duplicate", p2: … }` | US1-3, US1-5, US1-7 |
| `formatTime(ms)` | int → `"ММ:СС.сс"` (отбрасывание, max `99:59.99`) | US2-2, US2-3, US2-3a, US2-6 |
| `isLapTimeSavable(ms)` | → `3000 ≤ ms ≤ 5 999 999` | US2-6 |
| `pickWinner(candidates, random)` | `[1]`/`[2]`/`[1,2]`, `() → [0,1)` → 1 \| 2 | US2-7 |
| `showLastResultRow(board)` | → boolean | US3-10..12 |
| `highlightKey(board)` | → ключ \| null | US3-11 |

Каждая функция покрывается `frontend/tests/raceLogic.test.js` по указанным сценариям.
