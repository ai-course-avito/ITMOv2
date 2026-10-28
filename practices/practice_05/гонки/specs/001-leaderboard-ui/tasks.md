---

description: "Task list for 001-leaderboard-ui"
---

# Tasks: Таблица рекордов гонки (UI)

**Input**: Design documents from `specs/001-leaderboard-ui/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md),
[specs/contract.md](../contract.md)

**Tests**: включены — план требует `node --test` для чистых модулей (решение 2026-10-28).
Тесты фронтенда запускаются `cd frontend && npm test`, в `scripts/check.sh` **не** добавляются.

**Organization**: задачи сгруппированы по историям spec.md (US1–US4).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: можно делать параллельно (другой файл, нет зависимостей от незавершённых задач)
- **[Story]**: история из spec.md

## Жёсткие ограничения для всех задач

- `backend/` и `scripts/check.sh` **не менять**.
- В `frontend/src/App.vue` **не менять** `updatePhysics`, `checkLap`, `keepInsideTrack`,
  `CAR_MODELS`, `CAR_COLORS`, `trackConfig`, `onKeyDown`, `onKeyUp`, `scene3d.js` (Принцип II).
  Единственное согласованное изменение логики финиша — тело `declareWinner` (T017).
- Новых npm-зависимостей не добавлять (Принцип I).
- После каждой задачи: `bash scripts/check.sh` → `PASS`; после задач с тестами — `cd frontend && npm test`.
- Если для задачи нужно решение, которого нет в spec/plan/contract, — остановиться и спросить
  человека (Принцип V).

---

## Phase 1: Setup

**Purpose**: тестовый запуск и пустые модули

- [X] T001 Добавить в `frontend/package.json` в `"scripts"` строку `"test": "node --test tests/"`; зависимости не трогать
- [X] T002 [P] Создать `frontend/src/raceLogic.js` — ES-модуль без импорта Vue, с комментарием-заголовком «Чистые функции таблицы рекордов: имя, время, таблица, победитель» и экспортом констант `MAX_NAME_LENGTH = 20`, `MIN_LAP_MS = 3000`, `MAX_LAP_MS = 5999999`
- [X] T003 [P] Создать `frontend/tests/` и файл `frontend/tests/raceLogic.test.js` с импортами `node:test`, `node:assert/strict` и `../src/raceLogic.js`; `cd frontend && npm test` проходит (0 тестов не считается ошибкой)

---

## Phase 2: Foundational — клиент API

**Purpose**: `api.js` нужен историям US3 и US4. Спецификация — [contracts/api-client.md](contracts/api-client.md).

**⚠️ CRITICAL**: US3 и US4 не начинать до завершения фазы

- [X] T004 [P] Написать тесты `frontend/tests/api.test.js` (`node --test`, подменять `globalThis.fetch`, таймеры — через `mock.timers` из `node:test`) на все строки таблицы «Проверки» из `contracts/api-client.md`: 200 → `{ok:true,data}`; reject → `retryable`; нет ответа 5000 мс → `retryable`; 503 → `retryable`; 422 и 413 → `rejected`; внешний `signal.abort()` → `aborted`; тело POST ровно `{"name":"Камила","lap_time_ms":65400}`; 2xx с невалидным JSON → `retryable`. Тесты должны падать до T005
- [X] T005 Реализовать `frontend/src/api.js`: `export const API_BASE = "http://localhost:8000"`, `export const REQUEST_TIMEOUT_MS = 5000`; внутренняя `request(path, init, signal)` с собственным `AbortController`, таймером 5000 мс и пробросом внешнего `signal`; классификация строго по таблице `contracts/api-client.md` («`fetch` отклонён … `retryable`», «`422`, `413`, любой другой `4xx` → `rejected`», «Отменён внешним `signal` → `aborted`»); функции **не бросают** исключений; `export async function getLeaderboard({ signal } = {})` → `GET /leaderboard` без `limit`; `export async function saveRaceResult({ name, lapTimeMs }, { signal } = {})` → `POST /race-results` с телом `{ name, lap_time_ms: lapTimeMs }` и `Content-Type: application/json`. `npm test` — T004 зелёный

**Checkpoint**: клиент API готов и покрыт тестами

---

## Phase 3: User Story 1 — Ввод имени игрока (Priority: P1) 🎯 MVP

**Goal**: у каждого игрока поле «Имя» с «Игрок 1» / «Игрок 2»; имя проверяется при старте и
показывается в HUD и на «Финише».

**Independent Test**: открыть сайт, ввести имя, пройти гонку — имя видно в HUD и в
«ПОБЕДИЛ …!» (quickstart №1–5). Таймер и таблица не нужны.

### Tests for User Story 1

- [X] T006 [P] [US1] Добавить в `frontend/tests/raceLogic.test.js` тесты (падают до T007): `nameLength("🏎️"…)` считает кодовые точки (20 эмодзи «🚗» → 20) (US1-6); `clampName` 25 «🚗» → 20 «🚗» (US1-6); `normalizeName("  Камила   Салис  ") === "Камила Салис"` и табуляция/перевод строки внутри → один пробел (US1-8); `normalizeName("Гонщик 🏎️ №1")` не меняет символы (US1-9); `nameKey("Камила") === nameKey(" камила ")` (US1-7); `validateNames("", "Игрок 2")` → `{p1:"empty",p2:null}`, `validateNames("   ", …)` → `"empty"` (US1-5); `validateNames("Камила"," камила ")` → `{p1:"duplicate",p2:"duplicate"}` (US1-7); `validateNames("Игрок 1","Игрок 2")` → оба `null` (US1-3)

### Implementation for User Story 1

- [X] T007 [US1] Реализовать в `frontend/src/raceLogic.js` по `contracts/ui-components.md`: `nameLength(s) = Array.from(s).length`; `clampName(s, max = MAX_NAME_LENGTH) = Array.from(s).slice(0, max).join("")`; `normalizeName(s) = s.trim().replace(/\s+/g, " ")`; `nameKey(s) = normalizeName(s).toLowerCase()`; `validateNames(n1, n2)` → `{ p1, p2 }` со значениями `null | "empty" | "duplicate"`: `"empty"` если `normalizeName(raw) === ""`, иначе `"duplicate"` у обоих если `nameKey(p1) === nameKey(p2)`. T006 зелёный
- [X] T008 [US1] В `frontend/src/App.vue` (`<script setup>`): импортировать функции из `./raceLogic.js`; добавить `const p1Name = ref("Игрок 1")`, `const p2Name = ref("Игрок 2")`, `const nameErrors = ref({ p1: null, p2: null })`, флаг IME-набора на поле; обработчик `onNameInput(player, event)` — если не идёт `composition`, записывает `clampName(event.target.value)` и сбрасывает ошибку этого игрока (и `"duplicate"` у второго); `compositionend` вызывает тот же обрезатель. `resetGame()` имена **не** сбрасывает (US1-4)
- [X] T009 [US1] В `frontend/src/App.vue` в начале `prepareAndStartRace()`, до `fetch` на `/select-car`: `p1Name.value = normalizeName(p1Name.value)`, то же для `p2Name`; `nameErrors.value = validateNames(...)`; если есть ошибка — `return` без запроса и без отсчёта (US1-5, US1-7, US1-8)
- [X] T010 [US1] В шаблоне `frontend/src/App.vue`, экран `select`, в каждой `.player-card` под `.player-header` добавить `.form-section` с подписью «Имя:», `<input type="text">` (без атрибута `maxlength`), `:value`/`@input`/`@compositionstart`/`@compositionend`, счётчик `{{ nameLength(pXName) }}/20`, класс ошибки на поле и текст «Введите имя» при `nameErrors.pX === "empty"`; над кнопкой «Начать заезд!» — `.error-banner` «Имена игроков должны различаться», если `nameErrors.p1 === "duplicate"`, и подсветка обоих полей (US1-1, US1-5, US1-6, US1-7)
- [X] T011 [US1] В шаблоне `frontend/src/App.vue`, HUD гонки: заменить «Игрок 1 (W/A/S/D):» на `{{ p1Name }} (W/A/S/D):` и «Игрок 2 (Стрелки):» на `{{ p2Name }} (Стрелки):`; в `declareWinner` поле `name` брать из `p1Name.value` / `p2Name.value` вместо строк «Игрок 1/2» (US1-2, US1-3). Остальную логику `declareWinner` в этой задаче не менять
- [X] T012 [US1] Добавить в `<style scoped>` `frontend/src/App.vue` стили поля имени, счётчика и состояния ошибки в существующей палитре (`#8b5cf6`, `#22d3ee`, `.error-banner`); поле не шире карточки

**Checkpoint**: US1 работает отдельно — quickstart №1–5; `npm test`, `bash scripts/check.sh` → PASS

---

## Phase 4: User Story 2 — Таймер во время гонки (Priority: P1)

**Goal**: таймер `ММ:СС.сс` в HUD во время гонки, «Время круга» на «Финише», случайный
победитель при финише в одном кадре.

**Independent Test**: запустить гонку и наблюдать таймер; финишировать — «Время круга»
совпадает с последним значением таймера (quickstart №6–7, №14). Таблица не нужна.

### Tests for User Story 2

- [X] T013 [P] [US2] Добавить в `frontend/tests/raceLogic.test.js` тесты (падают до T014): `formatTime(0) === "00:00.00"` (US2-2); `formatTime(65400) === "01:05.40"` (US2-3); `formatTime(12346) === "00:12.34"` — отбрасывание, не округление (US2-3a); `formatTime(5999999) === "99:59.99"` и `formatTime(7000000) === "99:59.99"` (US2-6); `isLapTimeSavable(2999) === false`, `(3000) === true`, `(5999999) === true`, `(6000000) === false` (US2-6); `pickWinner([1], () => 0.99) === 1`, `pickWinner([2], () => 0) === 2`, `pickWinner([1,2], () => 0.1) === 1`, `pickWinner([1,2], () => 0.9) === 2` (US2-7)

### Implementation for User Story 2

- [X] T014 [US2] Реализовать в `frontend/src/raceLogic.js`: `formatTime(ms)` — `ms` ограничить `[0, MAX_LAP_MS]`, `mm = Math.floor(ms/60000)`, `ss = Math.floor(ms/1000) % 60`, `cs = Math.floor(ms/10) % 100`, каждое `padStart(2,"0")`, результат `` `${mm}:${ss}.${cs}` ``; `isLapTimeSavable(ms) = Number.isInteger(ms) && ms >= MIN_LAP_MS && ms <= MAX_LAP_MS`; `pickWinner(candidates, random)` — один кандидат → он; два → `random() < 0.5 ? candidates[0] : candidates[1]`. T013 зелёный
- [X] T015 [US2] В `frontend/src/App.vue` добавить состояние часов: `let raceStartMs = null`, `const elapsedMs = ref(0)`, `const lapTimeMs = ref(null)`, `let frameFinishers = []`. В `startCountdown()` там, где `countdown <= 0` и `gameState = "racing"`, перед `runGameLoop()` поставить `raceStartMs = performance.now()`, `elapsedMs.value = 0`, `frameFinishers = []`, `lapTimeMs.value = null` (US2-1, US2-2)
- [X] T016 [US2] В `runGameLoop()` `frontend/src/App.vue`: первой строкой после проверки `gameState` взять `const now = performance.now()`; после `updatePhysics()` вызвать `resolveFinish(now)` и, если гонка завершилась, `return` без `drawScene()`; иначе `elapsedMs.value = now - raceStartMs`. Тело `updatePhysics()` не менять (US2-2, US2-8)
- [X] T017 [US2] В `frontend/src/App.vue` изменить **только тело** `declareWinner(playerNum)`: вместо заполнения `winner` и `gameState = "gameover"` — `if (!frameFinishers.includes(playerNum)) frameFinishers.push(playerNum)`. Добавить функцию `resolveFinish(now)`: если `frameFinishers` пуст — `false`; иначе `const player = pickWinner(frameFinishers, Math.random)`, `lapTimeMs.value = Math.round(now - raceStartMs)`, заполнить `winner.value` как раньше (имя из `p1Name/p2Name`, модель, цвет, hex) + `lapTimeMs`, `gameState.value = "gameover"`, `true`. `checkLap` не трогать (US2-7, FR-014, FR-015)
- [X] T018 [US2] В `initCars()` `frontend/src/App.vue` дополнительно сбрасывать `frameFinishers = []`; строки сброса координат/скорости не менять
- [X] T019 [US2] В шаблоне `frontend/src/App.vue`, HUD гонки: центральный `.hud-item` показывает `{{ formatTime(elapsedMs) }}` (подпись «🏁 1 КРУГ» оставить мелким текстом рядом), только при `!sceneError` (US2-2, US2-5); на экране `gameover` под «Болид: …» добавить строку «Время круга: {{ formatTime(winner.lapTimeMs) }}» (US2-4)
- [X] T020 [US2] Проверить Принцип II: `git diff -- frontend/src/App.vue` не содержит изменённых строк внутри `updatePhysics`, `checkLap`, `keepInsideTrack`, `CAR_MODELS`, `CAR_COLORS`, `trackConfig`, `onKeyDown`, `onKeyUp` (quickstart §4); если есть — откатить их

**Checkpoint**: US1 + US2 работают — quickstart №6–7, №14; `npm test`, `bash scripts/check.sh` → PASS

---

## Phase 5: User Story 3 — Таблица рекордов (Priority: P2)

**Goal**: на «Выборе» (и позже на «Финише») таблица: 4 состояния, топ-10, подсветка,
строка «Последняя гонка».

**Independent Test**: наполнить сервер `curl` (quickstart №13), открыть сайт — строки,
сортировка, «Последняя гонка», пустое состояние и ошибка/«Повторить» (quickstart №1, №9, №10, №13).

### Tests for User Story 3

- [X] T021 [P] [US3] Добавить в `frontend/tests/raceLogic.test.js` тесты (падают до T022): `showLastResultRow({entries: 10 строк, last_result: {place: 13, …}}) === true` (US3-10); `place: 4` при 10 строках → `false` (US3-11); `last_result: null` → `false` (US3-12); `highlightKey` возвращает `nameKey(last_result.name)`, если имя есть в `entries` по ключу (в т. ч. «КАМИЛА» против «Камила»), иначе `null` (US3-11, US3-15); `leaderboardState(null, "loading") === "loading"`, пустой `entries` → `"empty"`, непустой → `"data"` (US3-1, US3-4)

### Implementation for User Story 3

- [X] T022 [US3] Реализовать в `frontend/src/raceLogic.js`: `showLastResultRow(board) = !!board && board.last_result != null && board.last_result.place > board.entries.length`; `highlightKey(board)` — ключ `last_result.name`, если какой-то `entries[i].name` даёт тот же `nameKey`, иначе `null`; `leaderboardState(board, status)` — `status` `"loading" | "error"` возвращается как есть, иначе `board.entries.length === 0 ? "empty" : "data"`. T021 зелёный
- [X] T023 [US3] Создать `frontend/src/Leaderboard.vue` (`<script setup>`) по `contracts/ui-components.md`: props `state: "loading" | "empty" | "data" | "error"`, `board`, `newRecordKey: string | null`; emit `retry`. Тексты дословно: «Загрузка рекордов…», «Пока нет рекордов — станьте первым!», «Не удалось загрузить рекорды» + кнопка «Повторить», заголовок «🏆 Рекорды», колонки «Место», «Имя», «Лучшее время» (`formatTime(best_time_ms)`); строка с `nameKey(name) === highlightKey(board)` — класс подсветки; у строки с `nameKey(name) === newRecordKey` — бейдж «Новый рекорд!»; при `showLastResultRow(board)` — разделитель, подпись «Последняя гонка» и строка `place · name · formatTime(lap_time_ms)` (US3-1..US3-15)
- [X] T024 [US3] Стили в `<style scoped>` `frontend/src/Leaderboard.vue`: таблица на всю ширину контейнера, имя — `overflow: hidden; text-overflow: ellipsis; white-space: nowrap`, без горизонтальной прокрутки до 600 px; подсветка и бейдж в палитре проекта (US3-9, Edge Cases)
- [X] T025 [US3] В `frontend/src/App.vue`: импорт `Leaderboard.vue` и `getLeaderboard`; состояние `const board = ref(null)`, `const boardStatus = ref("loading")`, `let boardController = null`; функция `loadLeaderboard()` — отменяет предыдущий `boardController`, ставит `"loading"`, вызывает `getLeaderboard({ signal })`; `ok` → `board = data`, `boardStatus = "ready"`; `kind === "aborted"` → ничего; иначе `boardStatus = "error"`. Вызывать в `onMounted` и в `resetGame()` (US3-1, US3-4, US3-5, US3-6)
- [X] T026 [US3] В шаблоне `frontend/src/App.vue`, экран `select`, под кнопкой «Начать заезд!» вставить `<Leaderboard :state="leaderboardState(board, boardStatus)" :board="board" :new-record-key="null" @retry="loadLeaderboard" />`; кнопка старта и выбор машинок работают в любом состоянии таблицы (FR-011)

**Checkpoint**: таблица на «Выборе» работает — quickstart №1, №9, №10, №13; `npm test`, `bash scripts/check.sh` → PASS

---

## Phase 6: User Story 4 — Сохранение результата после гонки (Priority: P2)

**Goal**: на «Финише» сохранение времени победителя со статусом, «Повторить», обновлением
таблицы и корректной «Новой игрой» во время запроса.

**Independent Test**: финишировать при работающем и при остановленном бэкенде; нажать
«Новая игра» во время сохранения (quickstart №8, №11, №12).

### Implementation for User Story 4

- [X] T027 [US4] В `frontend/src/App.vue`: импорт `saveRaceResult`, `isLapTimeSavable`, `nameKey`; состояние `const saveStatus = ref(null)` со значениями `"saving" | "saved" | "error" | "rejected" | "out_of_range"` (data-model.md), `const newRecordKey = ref(null)`, `let finishController = null`, `let finishGeneration = 0`
- [X] T028 [US4] В `frontend/src/App.vue` функция `async function saveAndRefresh()`: `const gen = ++finishGeneration`; `finishController = new AbortController()`; если `!isLapTimeSavable(winner.value.lapTimeMs)` → `saveStatus = "out_of_range"`, POST **не** отправлять (US2-6, FR-013a); иначе `saveStatus = "saving"`, `await saveRaceResult({ name: winner.value.name, lapTimeMs: winner.value.lapTimeMs }, { signal })`; если `gen !== finishGeneration` или `kind === "aborted"` — выйти; `ok` → `"saved"` и `newRecordKey = data.is_new_record ? nameKey(data.name) : null`; `kind === "rejected"` → `"rejected"`; иначе `"error"`; **после любого исхода** (кроме отмены) — `loadLeaderboard()` (US4-1..US4-3, US4-7, US4-9, FR-013)
- [X] T029 [US4] В `frontend/src/App.vue` вызывать `saveAndRefresh()` сразу после перехода в `gameover` в `resolveFinish` (T017); «Повторить» на «Финише» вызывает `saveAndRefresh()` повторно (US4-4)
- [X] T030 [US4] В `resetGame()` `frontend/src/App.vue`: `finishGeneration++`, `finishController?.abort()`, `saveStatus = null`, `newRecordKey = null` — до вызова `loadLeaderboard()` (US4-5, US4-8, FR-013b)
- [X] T031 [US4] В шаблоне `frontend/src/App.vue`, экран `gameover`, под «Время круга»: статус дословно — `saving` «Сохраняем результат…», `saved` «Результат сохранён ✓», `error` «Не удалось сохранить результат» + кнопка «Повторить», `rejected` «Результат не сохранён: некорректные данные» (без «Повторить»), `out_of_range` «Результат не сохранён: время вне допустимого диапазона»; кнопка «Новая игра» доступна всегда; ниже — `<Leaderboard :state="leaderboardState(board, boardStatus)" :board="board" :new-record-key="newRecordKey" @retry="loadLeaderboard" />` (US3-7, US3-8, US4-1..US4-7)
- [X] T032 [US4] Стили статусов сохранения в `<style scoped>` `frontend/src/App.vue` (успех / ошибка / нейтральный) в палитре проекта

**Checkpoint**: все истории работают — quickstart §3 полностью; `npm test`, `bash scripts/check.sh` → PASS

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T033 [P] Обновить `frontend/README.md`: раздел «Тесты» — `npm test` (`node --test`), не входит в `scripts/check.sh`
- [X] T034 `cd frontend && npm run build` — сборка без ошибок и предупреждений Vue
- [X] T035 Прогнать `cd frontend && npm test` и `bash scripts/check.sh` — оба зелёные; результат записать в отчёт задачи
- [X] T036 Пройти все ручные сценарии [quickstart.md](quickstart.md) §3 (№1–14) и §4 (Принцип II); несовпадения — в отчёт, без самостоятельного изменения спеки
- [X] T037 Проверить соответствие правилам проекта навыком `race-rules` (модели, палитра, `<script setup>`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → сразу
- **Foundational (Phase 2)** → после Setup; блокирует US3, US4
- **US1 (Phase 3)** → после Setup (от Phase 2 не зависит)
- **US2 (Phase 4)** → после US1: T017/T019 используют `p1Name/p2Name`, правки в том же `App.vue`
- **US3 (Phase 5)** → после Phase 2; правки `App.vue` (T025–T026) — после US2, чтобы не править файл параллельно
- **US4 (Phase 6)** → после US2 (время круга, `resolveFinish`) и US3 (`Leaderboard.vue`, `loadLeaderboard`)
- **Polish (Phase 7)** → после всех историй

### Story graph

```
Setup ─┬─► US1 ─► US2 ─┬─► US3(App.vue) ─► US4 ─► Polish
       └─► Foundational ┘        ▲
                 └─► T021–T024 ──┘  (raceLogic + Leaderboard.vue — параллельно с US1/US2)
```

### Within each story

- тесты (`[P]`) → реализация в `raceLogic.js` → правки `App.vue` / компонента
- `App.vue` правится строго последовательно (один файл)

## Parallel Opportunities

- T002, T003 — разные файлы
- T004 (api-тесты) параллельно с US1 (T006–T007)
- T021–T024 (`raceLogic` таблицы + `Leaderboard.vue`) параллельно с US1/US2, т. к. не трогают `App.vue`
- T006, T013, T021 пишутся в один файл тестов — **не** параллельно между собой, но параллельно с задачами в других файлах

### Parallel Example: Foundational + US1

```text
Агент A: T004 → T005  (frontend/tests/api.test.js, frontend/src/api.js)
Агент B: T006 → T007 → T008 … (raceLogic.test.js, raceLogic.js, App.vue)
```

### Parallel Example: US3 компоненты во время US2

```text
Агент A: T013 → T014 → T015 … T020 (App.vue, таймер)
Агент B: T023 → T024 (Leaderboard.vue) — после T021–T022
```

## Implementation Strategy

### MVP (US1)

1. Phase 1 → Phase 3 (US1)
2. Проверить quickstart №1–5 — имена работают, гонка как раньше
3. `npm test`, `bash scripts/check.sh` → PASS

### Incremental Delivery

1. + US2 → таймер и «Время круга» (quickstart №6–7, №14)
2. + Phase 2 + US3 → таблица на «Выборе» (№1, №9, №10, №13)
3. + US4 → сохранение и таблица на «Финише» (№8, №11, №12)
4. Polish → сборка, полный quickstart
