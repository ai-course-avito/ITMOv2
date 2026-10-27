# Tasks: Логика проверяемого ревью PR

**Input**: Design documents from `/specs/002-review-logic/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/api.md](contracts/api.md), CONTRACT.md v1.0 и разрешение координатора на код.

**Tests**: Unit/API проверки требуются спецификацией и планом приёмки. Все 14 задач выполнены; фактические результаты проверки записаны в quickstart.md. Писать проверки сценария до его реализации, убедиться, что они выявляют отсутствующее поведение.

**Organization**: Задачи сгруппированы по пользовательским историям. Все пути — относительно project. Backend владеет app/, tests/test_logic.py, tests/test_api.py; static/ ведёт UI, requirements/Makefile/README/tests/test_e2e.py — root.

## Format: `[ID] [P?] [Story] Description`

[P] означает разные файлы и отсутствие зависимости между отмеченными задачами внутри текущей фазы. Маркер не разрешает добавлять агентов сверх команды пользователя.

## Path Conventions

Один project: app/ и tests/, статические файлы в static/. Entry point app.api:app. make test запускает tests.test_logic и tests.test_api; общий runner ведёт root.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Минимальная структура и конфигурация без DB.

- [X] T001 Создать app/__init__.py и app/config.py: REVIEW_MODE=demo|live, default demo; REVIEW_LLM_URL/MODEL/KEY обязательны только для live, конфигурация не попадает в ответ/журнал.
- [X] T002 Создать app/api.py с app.api:app, фабрикой приложения для инъекции сервиса, безопасной общей формой request_id/error(code,message) без retryable и точными HTTP-кодами contracts/api.md; подключить GET / и /static/* к файлам команды UI.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Индекс diff и приватность до любого внешнего анализа.

- [X] T003 [P] Создать app/diff.py: несколько файлов, ---/+++, @@, частичные counts, /dev/null, LF/CRLF, old для - и new для +/контекста; индекс file/line/prefixed text, line int>0; отклонить неподдерживаемые diff/пути и не читать файлы по входным путям.
- [X] T004 [P] Создать app/secrets.py с точным конечным покрытием из spec.md: присваивания token/password/passwd/secret/api_key, Bearer, ghp_/github_pat_/sk- с ≥8 символами и четыре вида PEM PRIVATE KEY; сохранять строки/префиксы, обработать незакрытый PEM, рекурсивно маскировать строковые значения ответа.

**Checkpoint**: До завершения маскирования нельзя включать live adapter.

## Phase 3: User Story 1 - Проверяемое ревью (Priority: P1)

**Goal**: Успешное demo-ревью учебного diff с проверенными цитатами.

**Independent Test**: Учебный diff + fake/demo adapter → 200, mode demo, три раздела; 0/3 риска допустимы, неверный результат отклонён целиком.

### Tests for User Story 1

- [X] T005 [US1] Добавить в tests/test_logic.py и tests/test_api.py случаи учебного partial hunk, new/old координат, 0/3/4 рисков, неверного file/line/evidence, null/RULE-only, лишних полей и повторного маскирования перед final evidence check; без сети.

### Implementation for User Story 1

- [X] T006 [US1] Создать app/review.py: кандидаты ровно summary/risks/checks; summary непустая после trim ≤1500 code points, risks 0–3 объекта ровно file/line/evidence/risk, file непустой из diff, line int>0 не bool, evidence точная строка очищенного diff с префиксом ≤20000, risk непустая ≤1000, checks 1–10 непустых строк ≤500; parse→mask→final structure/evidence validation, null и RULE-only запрещены.
- [X] T007 [US1] Создать demo adapter в app/llm.py по трём детерминированным правилам research.md и подключить POST /api/reviews в app/api.py: UUID request_id и mode добавляет сервер, правила используют только реально найденные строки, нет совпадений → risks=[] с непустыми summary/checks, никакого ложного live.

**Checkpoint**: MVP успешного пути тестируется отдельно; публичную готовность до остальных проверок не заявлять.

## Phase 4: User Story 2 - Вход и секреты (Priority: P2)

**Goal**: Ошибки входа до модели и маскирование заявленных секретов.

**Independent Test**: Fake adapter записывает полученный prompt/число вызовов; границы и секреты проверяются без внешнего провайдера.

### Tests for User Story 2

- [X] T008 [US2] Добавить в tests/test_logic.py и tests/test_api.py 20000/20001 code points, emoji, CRLF, пустоту, типы/лишние поля, неверный content type/JSON/diff и все согласованные секреты; проверить отсутствие вызова при отказе и исходных значений в outbound/ответе.

### Implementation for User Story 2

- [X] T009 [US2] Завершить в app/api.py и app/review.py порядок content type→JSON→shape/type→size→empty→diff→settings→mask→analyze: ровно diff string, 1–20000 Unicode code points до trim/нормализации и не только пробелы; 413 при превышении, остальные статусы по contracts/api.md, без автоматического преобразования типов.

## Phase 5: User Story 3 - Контролируемые сбои (Priority: P3)

**Goal**: Live adapter с общим deadline и безопасными ошибками, без скрытого fallback.

**Independent Test**: MockTransport/fake adapter дают timeout, cancellation, transport error, invalid content; все случаи контролируются, вызов один, исходные тексты провайдера не раскрываются.

### Tests for User Story 3

- [X] T010 [US3] Добавить в tests/test_logic.py и tests/test_api.py проверки полного live-конфига/503, transport/provider errors, invalid upstream envelope/JSON, общего deadline и распространения отмены; проверить отсутствие повторов/fallback и журнал ровно request_id/duration_ms/status.

### Implementation for User Story 3

- [X] T011 [US3] Реализовать async HTTPX chat/completions adapter в app/llm.py: REVIEW_LLM_URL полный endpoint, model/messages, ключ только в Authorization, один запрос без redirects/retries; разобрать choices[0].message.content; HTTP/transport→MODEL_UNAVAILABLE, неверный content→INVALID_MODEL_OUTPUT.
- [X] T012 [US3] В app/review.py ограничить общий await `asyncio.timeout(10)`, timeout→504 MODEL_TIMEOUT, cancellation распространить; inject deadline только во внутренних тестах, production 10 секунд; сохранять один вызов и фактический mode demo|live.
- [X] T013 [US3] Завершить safe error/log boundary в app/api.py: request_id UUID на каждый API ответ, неизвестная ошибка→500 INTERNAL_ERROR без stack trace/внешнего текста, журнал только request_id/duration_ms/status; не сохранять diff/response и не включать секретные debug logs.

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T014 Выполнить scenarios specs/002-review-logic/quickstart.md через tests/test_logic.py и tests/test_api.py, передать root результаты и app.api:app для tests/test_e2e.py; исправления в своей области, результаты и невыполненный live честно отметить в specs/002-review-logic/quickstart.md.

## Dependencies & Execution Order

Setup → foundation → US1 → US2 → US3 → polish. T003/T004 независимы; T006 зависит от обоих. T007 зависит от T006. Внутри каждой истории тестовые сценарии задаются перед реализацией. US2/US3 проверяются независимо с fake adapter, хотя в единой небольшой кодовой базе выполняются последовательно для избежания одновременных правок api.py/review.py.

Внешние зависимости: root устанавливает зависимости и создаёт runner; UI предоставляет static/index.html, app.js, styles.css. Браузерная приёмка начинается после готовности обеих реализаций. Root остаётся владельцем tests/test_e2e.py.

## Parallel Example: User Story 1

Пока логика проверяет T005–T007 в app/ и tests/test_logic.py, команда UI может реализовать представление успешного результата в static/. Между backend-задачами US1 есть зависимости, поэтому они не помечены [P].

## Parallel Example: User Story 2

Backend пишет проверки маскирования tests/test_logic.py; UI независимо проверяет локальную длину/пустоту static/app.js по тому же контракту. Общие файлы не редактируются параллельно.

## Parallel Example: User Story 3

Backend проверяет timeout/cancellation, UI независимо реализует состояние ошибки/15-секундное ожидание. Итоговый e2e остаётся последовательным после обеих частей.

## Implementation Strategy

MVP — US1 с безопасными foundation (парсер/маскирование) и fake/demo adapter. Затем US2 подтверждает отказ до внешнего анализа, US3 добавляет live и устойчивость. Только после всех 14 задач и совместной приёмки возможен отчёт о завершённой фиче. Реальный LLM нельзя объявлять проверенным по подмене. Коммиты выполняет root, этот план не даёт отдельному агенту разрешения менять git.
