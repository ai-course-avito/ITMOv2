---

description: "Task list for 002-leaderboard-logic (backend)"
---

# Tasks: Таблица рекордов гонки (логика)

**Input**: Design documents from `specs/002-leaderboard-logic/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/leaderboard-api.md](contracts/leaderboard-api.md),
[quickstart.md](quickstart.md), общий контракт [../contract.md](../contract.md)

**Tests**: включены — Принцип IV конституции (сценарии бэкенда → pytest) и SC-007 спеки.
Тесты пишутся до реализации своей истории и должны сначала падать.

**Organization**: задачи сгруппированы по историям спеки. **US1 (замер времени и таймер) в эту
фичу не входит** — это клиентский код, `frontend/` не трогаем (plan.md, «Вне этой фичи»).

**Общие правила для всех задач**:

- Менять только `backend/` и корневой `.gitignore`. `frontend/` MUST NOT меняться (Принципы I, II).
- Новых зависимостей нет — только стандартная библиотека, FastAPI, Pydantic.
- Стиль — как в существующих `backend/app/main.py`, `backend/app/models.py`: докстринги и
  комментарии на русском, ruff (`line-length = 100`, правила `E, F, I, UP, B`).
- После каждой задачи: `bash scripts/check.sh` → `PASS` (Принцип III). Тесты не помечать
  `skip`/`xfail`, правила ruff не отключать.
- Пути ниже — от корня репозитория (`гонки/`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: можно выполнять параллельно (другой файл, нет зависимости от незавершённых задач)
- **[Story]**: история спеки (US2, US3, US4)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: подготовка репозитория

- [X] T001 Добавить строку `backend/leaderboard.json` в `.gitignore` (рядом с `backend/error_reports.log`)
- [X] T002 Запустить `bash scripts/check.sh` до изменений и убедиться в `PASS` — исходная точка; если `FAIL`, остановиться и сообщить человеку (Принцип V)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: хранилище, нормализация имени, ранжирование и подключение к FastAPI — нужны всем историям

**⚠️ CRITICAL**: работа над историями начинается только после этой фазы

- [X] T003 Создать `backend/app/leaderboard.py`: модульный докстринг; класс `StorageError(Exception)`; константа `STORAGE_UNAVAILABLE_DETAIL = "Хранилище рекордов недоступно"`; функция `empty_state() -> dict`, возвращающая `{"version": 1, "records": {}, "last_result": None}`; функция `utc_now() -> datetime` (`datetime.now(timezone.utc)`); функция `format_ts(dt) -> str` — UTC ISO 8601 с микросекундами и суффиксом `Z` (например `2026-10-28T10:00:00.000000Z`)
- [X] T004 В `backend/app/leaderboard.py` добавить `normalize_name(value: str) -> str` = `" ".join(value.split())` (research R5: края обрезаются, каждая серия пробельных символов Unicode, включая `\t` и `\n`, → один пробел; других ограничений на символы нет) и `name_key(name: str) -> str` = `name.casefold()`
- [X] T005 В `backend/app/leaderboard.py` добавить `validate_state(data) -> dict`: возвращает `data`, если это `dict` с `version == 1`, `records` — `dict`, где каждое значение — `dict` с `name` (str), `best_time_ms` (int, не bool), `achieved_at` (str), и `last_result` — `None` или `dict` с `name` (str), `lap_time_ms` (int, не bool), `finished_at` (str); иначе `raise StorageError` (data-model.md, «Проверка структуры при чтении»)
- [X] T006 В `backend/app/leaderboard.py` добавить класс `LeaderboardStore(path: Path, clock: Callable[[], datetime] = utc_now)` с `threading.Lock` в `self._lock` и методами: `_load() -> dict` — нет файла → `empty_state()`; `json.JSONDecodeError`, `UnicodeDecodeError`, `OSError` → `StorageError`; затем `validate_state`; `_save(state) -> None` — атомарно: `tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False)`, `json.dump(state, f, ensure_ascii=False)`, `f.flush()`, `os.fsync(f.fileno())`, затем `os.replace(tmp, path)`; при любом исключении удалить временный файл и поднять `StorageError` (research R2). Публичные методы с `self._lock` добавляются в US2/US3
- [X] T007 В `backend/app/leaderboard.py` добавить `rank(records: dict) -> list[str]` — ключи, отсортированные по `(best_time_ms, achieved_at, key)`; место = индекс + 1, номера мест не повторяются (research R8, решение В2)
- [X] T008 В `backend/app/main.py`: импортировать из `app.leaderboard`; добавить `LEADERBOARD_PATH = Path(__file__).resolve().parent.parent / "leaderboard.json"` (рядом с `ERROR_LOG_PATH`), модульный `_store = LeaderboardStore(LEADERBOARD_PATH)`, функцию-зависимость `get_store() -> LeaderboardStore`, и `@app.exception_handler(StorageError)`, возвращающий `JSONResponse(status_code=503, content={"detail": STORAGE_UNAVAILABLE_DETAIL})`; дописать в модульный докстринг абзац про таблицу рекордов
- [X] T009 В `backend/tests/conftest.py` добавить фикстуры: `clock` — подменяемые часы (объект с текущим `datetime` в UTC, начиная с `2026-10-28T10:00:00Z`, и методом `advance(seconds)`); `store(tmp_path, clock)` — `LeaderboardStore(tmp_path / "leaderboard.json", clock=clock.now)`; `client(store)` — `app.dependency_overrides[get_store] = lambda: store`, `yield TestClient(app)`, затем `app.dependency_overrides.clear()`. Существующие тесты (`test_select_car.py`, `test_report_error.py`) не менять
- [X] T010 [P] Создать `backend/tests/test_leaderboard_store.py` с юнит-тестами фундамента: `normalize_name("  Камила  ") == "Камила"`, `normalize_name("Камила   Салис") == "Камила Салис"`, `normalize_name("Камила\tСалис") == "Камила Салис"`; `name_key("КАМИЛА") == name_key("камила")`; `rank` при равном `best_time_ms` ставит выше более ранний `achieved_at`; `_save` + `_load` возвращают то же состояние; `_load` без файла → `empty_state()`

**Checkpoint**: `bash scripts/check.sh` → `PASS`; хранилище и зависимость готовы

---

## Phase 3: User Story 2 - Сохранение результата под именем (Priority: P1) 🎯 MVP

**Goal**: `POST /race-results` сохраняет время победителя и обновляет рекорд имени и последний результат

**Independent Test**: отправить результаты через `client` и проверить ответы и содержимое файла хранилища (без `GET /leaderboard`)

**Вне фичи**: US2-7 (клиент отправляет ровно один POST — победителя) — клиентский код, не реализуется

### Tests for User Story 2 ⚠️

> Написать тесты, убедиться, что они ПАДАЮТ, затем реализовать

- [X] T011 [US2] Создать `backend/tests/test_leaderboard_api.py` с тестами POST (фикстуры `client`, `store`, `clock`): US2-1 — пустое хранилище, `{"name": "Камила", "lap_time_ms": 41250}` → 201, `name == "Камила"`, `lap_time_ms == 41250`, `best_time_ms == 41250`, `is_new_record is True`, `place == 1`; US2-2 — затем 39800 → `best_time_ms == 39800`, `is_new_record is True`; US2-3 — затем 45000 → `best_time_ms == 39800`, `is_new_record is False`; US2-4 — рекорд 39800 в 10:00, `clock.advance(3600)`, снова 39800 → `is_new_record is False`, в файле `achieved_at` остался 10:00; US2-5 — повтор одного запроса дважды → оба 201 с тем же `best_time_ms`, в файле одна запись этого имени; US2-6 — `"Игрок 1"` сохраняется как обычное имя; US2-8 — рекорд «Камила» 39800, затем `{"name": "КАМИЛА", "lap_time_ms": 38000}` → `name == "КАМИЛА"`, `best_time_ms == 38000`, `is_new_record is True`, в файле одна запись с `name == "КАМИЛА"`; US2-9 — рекорд «Камила» 39800, затем `{"name": "камила", "lap_time_ms": 45000}` → `best_time_ms == 39800`, `is_new_record is False`, в файле `name == "Камила"`; US2-10 — заполнить 1000 записей через `store._save` (не POST), затем POST нового имени с временем хуже всех → 201, `place == 1001`, GET → `total == 1001`; нормализация — `"  Камила  "` → ответ `name == "Камила"`; `last_result` в файле после каждого успешного POST = `{"name", "lap_time_ms" этой гонки, "finished_at"}`

### Implementation for User Story 2

- [X] T012 [US2] В `backend/app/models.py` добавить модель `RaceResult` (`model_config = ConfigDict(extra="forbid")`): `name: str`, `lap_time_ms: int = Field(strict=True, ge=3000, le=5_999_999)`; `@field_validator("name")` применяет `normalize_name` и поднимает `ValueError`, если длина результата (`len()`, кодовые точки) не в диапазоне 1–20. Добавить модель ответа `SaveResultResponse`: `name: str`, `lap_time_ms: int`, `best_time_ms: int`, `is_new_record: bool`, `place: int`. Докстринги — в стиле `ErrorReport`
- [X] T013 [US2] В `LeaderboardStore` (`backend/app/leaderboard.py`) добавить `save_result(name: str, lap_time_ms: int) -> dict` — под `self._lock`, строго по алгоритму data-model.md «Алгоритм сохранения результата»: `_load()` (при повреждении `StorageError` до любой записи); рекорд обновляется только если записи нет или `lap_time_ms < best_time_ms` (новое `name`, `best_time_ms`, `achieved_at = format_ts(now)`); иначе запись не меняется; `last_result = {"name", "lap_time_ms", "finished_at": format_ts(now)}` всегда; `_save()`; `place = rank(records).index(key) + 1`; вернуть словарь с полями `SaveResultResponse`
- [X] T014 [US2] В `backend/app/main.py` добавить `@app.post("/race-results", status_code=201)` — обычная функция `def save_race_result(result: RaceResult, store: LeaderboardStore = Depends(get_store)) -> SaveResultResponse`, вызывающая `store.save_result(result.name, result.lap_time_ms)`; докстринг в стиле существующих эндпоинтов

**Checkpoint**: тесты T011 зелёные, `bash scripts/check.sh` → `PASS`

---

## Phase 4: User Story 3 - Получение таблицы рекордов (Priority: P1)

**Goal**: `GET /leaderboard` отдаёт топ-`limit`, `total` и `last_result`

**Independent Test**: наполнить хранилище через `store._save(...)` фикстурным состоянием (без POST) и проверить ответ GET

### Tests for User Story 3 ⚠️

- [X] T015 [US3] Дописать в `backend/tests/test_leaderboard_api.py` тесты GET: US3-1 — пустое хранилище → 200, `{"entries": [], "total": 0, "last_result": None}`; US3-2 — «Аня» 50000, «Боря» 40000, «Вика» 45000 → порядок Боря (place 1), Вика (2), Аня (3), у каждой строки поля `place`, `name`, `best_time_ms`, `achieved_at`; US3-3 — 15 имён → `len(entries) == 10`, места 1–10, `total == 15`; US3-4 — `limit=3` → 3 строки; US3-5 — «Аня» и «Боря» по 40000, у «Ани» `achieved_at` раньше → Аня place 1, Боря place 2, следующее имя place 3; US3-8 — 14 имён, у «Камила» рекорд 55000 (place 13), POST 58730 → `last_result == {"name": "Камила", "lap_time_ms": 58730, "place": 13, "finished_at": ...}`; US3-9 — затем POST «Боря» → `last_result.name == "Боря"`; US3-10 — после POST с 422 `last_result` не изменился
- [X] T016 [P] [US3] Дописать в `backend/tests/test_leaderboard_store.py`: US3-6 — сохранить результаты, создать новый `LeaderboardStore` на том же файле → `get_leaderboard(10)` совпадает, включая `last_result`; US3-7 — два экземпляра хранилища на одном файле: запись через первый видна при чтении через второй

### Implementation for User Story 3

- [X] T017 [US3] В `backend/app/models.py` добавить модели ответа `LeaderboardEntry` (`place: int`, `name: str`, `best_time_ms: int`, `achieved_at: str`), `LastResultOut` (`name: str`, `lap_time_ms: int`, `place: int`, `finished_at: str`) и `Leaderboard` (`entries: list[LeaderboardEntry]`, `total: int`, `last_result: LastResultOut | None`)
- [X] T018 [US3] В `LeaderboardStore` (`backend/app/leaderboard.py`) добавить `get_leaderboard(limit: int) -> dict` — под `self._lock`: `_load()`, `order = rank(records)`, `entries` — первые `limit` ключей с `place = i + 1`, `total = len(records)`, `last_result` — `None` или словарь с `place = order.index(name_key(last_result["name"])) + 1` (место вычисляется при каждом чтении, research R8)
- [X] T019 [US3] В `backend/app/main.py` добавить `@app.get("/leaderboard")` — `def get_leaderboard(limit: int = Query(10, ge=1, le=50), store: LeaderboardStore = Depends(get_store)) -> Leaderboard`, вызывающая `store.get_leaderboard(limit)`

**Checkpoint**: US2 и US3 работают независимо, `bash scripts/check.sh` → `PASS`

---

## Phase 5: User Story 4 - Ошибки и отказ хранилища (Priority: P2)

**Goal**: невалидные данные → 422/413 без записи; сбой хранилища → 503 без потери и порчи данных; одновременные запросы не теряют записи

**Independent Test**: невалидные тела запросов и недоступный/повреждённый файл хранилища в pytest

### Tests for User Story 4 ⚠️

- [X] T020 [US4] Дописать в `backend/tests/test_leaderboard_api.py` тесты ошибок; в каждом проверять, что содержимое файла хранилища (или его отсутствие) после запроса не изменилось: US4-1 — `name = "   "` → 422; US4-2 — имя из 21 символа после обрезки → 422, а из 20 эмодзи → 201 (длина в кодовых точках); US4-3 — `lap_time_ms = 2999` и `6000000` → 422, `3000` и `5999999` → 201; US4-4 — `41250.5`, `"41250"`, `true` → 422; US4-5 — лишнее поле `"place": 1` → 422; US4-6 — тело больше 2048 байт → 413 `{"detail": "Запрос слишком большой"}`; US4-7 — `GET /leaderboard?limit=0` и `limit=51` → 422; US4-9 — файл `{не json` → GET и POST дают 503 `{"detail": "Хранилище рекордов недоступно"}`, байты файла не изменились; файл с `"version": 2` → 503; US4-10 — нет файла → GET 200 с пустой таблицей, файл не создан; US4-11 — 20 POST с разными именами из `concurrent.futures.ThreadPoolExecutor(max_workers=20)` → все 201, затем GET `total == 20`; SC-005 — заполнить 1000 записей через `store._save`, затем `GET /leaderboard` и `POST /race-results` каждый отвечают быстрее 0,5 с (`time.perf_counter()`). US4-12 проверяется задачей T025
- [X] T021 [P] [US4] Дописать в `backend/tests/test_leaderboard_store.py`: US4-8 — сохранить рекорд, затем `monkeypatch.setattr("app.leaderboard.os.replace", ...)` поднимает `OSError` → `save_result` поднимает `StorageError`, прежний файл не изменился, в папке нет оставшихся временных файлов; то же через `client` → 503 `{"detail": "Хранилище рекордов недоступно"}`

### Implementation for User Story 4

- [X] T022 [US4] Прогнать тесты T020–T021; исправить в `backend/app/leaderboard.py` и `backend/app/models.py` только то, что падает (ожидаемые места: проверка `bool` в `validate_state`, удаление временного файла в `_save`, `strict=True` у `lap_time_ms`). Существующий middleware `limit_body_size` в `backend/app/main.py` не менять

**Checkpoint**: все истории работают, `bash scripts/check.sh` → `PASS`

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T023 Запустить `bash scripts/check.sh` (ruff check, ruff format --check, pytest) → `PASS`; при ошибках формата выполнить `ruff format` в `backend/`
- [X] T024 Выполнить ручную проверку из [quickstart.md](quickstart.md), раздел 2 (curl, перезапуск uvicorn, повреждённый файл), затем удалить созданный `backend/leaderboard.json`
- [X] T025 Проверить `git diff --stat frontend/` — пусто (US4-12, FR-020), и `git status` — изменены только `.gitignore`, `backend/app/main.py`, `backend/app/models.py`, `backend/tests/conftest.py` и добавлены `backend/app/leaderboard.py`, `backend/tests/test_leaderboard_api.py`, `backend/tests/test_leaderboard_store.py` (Принципы I, II)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → **Foundational (Phase 2)** → истории → **Polish (Phase 6)**
- T003 → T004, T005, T007 → T006 → T008 → T009 → T010

### User Story Dependencies

- **US2 (P1)**: только Foundational
- **US3 (P1)**: только Foundational (тесты наполняют хранилище напрямую); US3-8…US3-10 используют POST, поэтому эти тесты зелёные после US2
- **US4 (P2)**: после US2 и US3 (проверяет ошибки обоих эндпоинтов)

### Within Each User Story

- Тесты → модели (`models.py`) → метод хранилища (`leaderboard.py`) → эндпоинт (`main.py`)
- US2 и US3 правят одни и те же файлы (`models.py`, `leaderboard.py`, `main.py`, `test_leaderboard_api.py`) — выполнять последовательно

### Parallel Opportunities

- T010 — параллельно с T008/T009 (другой файл)
- T016 — параллельно с T015 (разные файлы тестов)
- T021 — параллельно с T020

---

## Parallel Example: User Story 3

```bash
# Тесты US3 в двух файлах одновременно:
Task: "T015 [US3] тесты GET в backend/tests/test_leaderboard_api.py"
Task: "T016 [US3] тесты перезапуска в backend/tests/test_leaderboard_store.py"
```

---

## Implementation Strategy

### MVP First (US2 + US3)

1. Phase 1 → Phase 2
2. Phase 3 (US2): результаты сохраняются
3. Phase 4 (US3): таблица читается — **MVP**: сервер полностью обслуживает контракт для 201/200
4. **STOP and VALIDATE**: `bash scripts/check.sh` → `PASS`, quickstart раздел 2

### Incremental Delivery

1. US2 → сохранение проверено тестами
2. US3 → таблица и `last_result`
3. US4 → ошибки и отказоустойчивость
4. Polish → ручная проверка и контроль, что фронтенд не тронут

### Вне этой фичи

US1 (FR-001…FR-005: таймер, замер времени, случайный победитель), FR-013 (один POST победителя) и
вся клиентская часть contract.md 2.5–2.7 — отдельная фича фронтенда вместе со спекой UI 001.
