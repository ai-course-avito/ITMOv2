# Tasks

**Feature**: practice_05-gamification (UI)
**Created**: 2026-10-28
**Inputs**: docs/requirements/practice_05-gamification/UI_SPEC.md

## Format

- [ID] [P?] [Story] Description
- [P] indicates parallelizable work

## Phase 1 - Foundations

- [x] UI-T010 Кнопка «ИГРАТЬ» и баннер при 0 круток  COMPLETE
  - Files: practices/practice_05/project/static/index.html, practices/practice_05/project/static/script.js, practices/practice_05/project/static/styles.css
  - Inputs: GET /api/user/profile (contracts/endpoints.md), schemas/user.json
  - Output: Видимая кнопка «ИГРАТЬ» (правый верхний угол); при spins_remaining=0 нажатие вызывает полноэкранный баннер
  - Verify: FR-002, FR-007; UI_SPEC Acceptance Mapping (кнопка/баннер)

- [x] UI-T011 [P] Экран/оверлей колеса: визуал, анимация, отображение пула с ≥1 эмодзи  COMPLETE
  - Files: practices/practice_05/project/static/index.html, practices/practice_05/project/static/script.js, practices/practice_05/project/static/styles.css
  - Inputs: GET /api/spin/pool, schemas/spinPool.json
  - Output: Оверлей/экран «колеса» с анимацией; визуально отрисован пул (мин. 8 сегментов), ≥1 сегмент с эмодзи
  - Verify: FR-003, FR-012; нейтральные визуальные эффекты (UI_SPEC)

- [x] UI-T012 Показ результата спина; сообщение о дубле  COMPLETE
  - Files: practices/practice_05/project/static/script.js, practices/practice_05/project/static/index.html
  - Inputs: POST /api/spin, schemas/spinResult.json
  - Output: Показ результата (эмодзи/«странный» приз), обновление счётчика круток; при duplicate=true показывается сообщение «эмодзи уже разблокировано»
  - Verify: FR-004, FR-009; правило дублей «игнор + сообщение» (UI_SPEC)

## Phase 2 - Tasks UI

- [x] UI-T020 Выбор эмодзи в форме создания/редактирования задач  COMPLETE
  - Files: practices/practice_05/project/static/index.html, practices/practice_05/project/static/script.js, practices/practice_05/project/static/styles.css
  - Inputs: GET /api/emojis/catalog (для списка), GET /api/user/profile (для доступности), schemas/emojiCatalogItem.json, schemas/user.json
  - Output: Элемент управления «добавить эмодзи»; выпадение списка эмодзи, доступные норм, недоступные серым (или скрыть); назначение эмодзи отображается перед задачей
  - Verify: FR-006, FR-006a, FR-006b; US3 сценарии 1,4

- [x] UI-T021 Состояния недоступности: серые (или скрыть), подсказки  COMPLETE
  - Files: practices/practice_05/project/static/styles.css, practices/practice_05/project/static/script.js
  - Inputs: UI_SPEC решения; contracts/schemas/emojiCatalogItem.json
  - Output: Визуальные состояния для недоступных эмодзи; подсказки/тултипы о способе их разблокировки
  - Verify: FR-006b; Edge case «если нельзя серым — скрыть» (Acceptance Criteria)

- [x] UI-T022 Отображение эмодзи перед задачей; снятие метки  COMPLETE
  - Files: practices/practice_05/project/static/index.html, practices/practice_05/project/static/script.js
  - Inputs: DELETE /api/tasks/{taskId}/emojis/{code}:{version}, schemas/taskEmojiAssignment.json (для структуры), schemas/emojiCatalogItem.json
  - Output: Эмодзи видны перед задачами; возможность снять эмодзи и обновить отображение
  - Verify: FR-006; US3 сценарии 1,2

- [x] UI-T023 «Добавить ещё эмодзи»: неактивно без перка; до 3 при перке  COMPLETE
  - Files: practices/practice_05/project/static/index.html, practices/practice_05/project/static/script.js
  - Inputs: GET /api/user/profile (has_multi_emoji), POST /api/tasks/{taskId}/emojis, schemas/user.json, schemas/taskEmojiAssignment.json
  - Output: Кнопка «добавить ещё эмодзи» неактивна без перка; активируется при has_multi_emoji=true; обеспечивает предел до 3 эмодзи/задачу
  - Verify: FR-014, FR-014a; US3 сценарий 3,5

## Phase 3 - Polish

- [x] UI-T030 Документация UX-состояний  COMPLETE
- [x] UI-T031 Доработка иконографики и цветов «казино»-кнопки  COMPLETE

## Verification

- [x] UI-V001 Проверка Acceptance Mapping из UI_SPEC (FR-002,3,4,6,6a,6b,7,12,14a)
  - Use examples: contracts/examples/spin_pool_response.json, spin_result_response.json, spin_no_spins_case.json, spin_duplicate_emoji.json, catalog_response.json, profile_response.json
