# Tasks

**Feature**: practice_05-gamification (Backend)
**Created**: 2026-10-28
**Inputs**: docs/requirements/practice_05-gamification/BACKEND_SPEC.md

## Format

- [ID] [P?] [Story] Description
- [P] indicates parallelizable work

## Phase 1 - Foundations

 - [x] BE-T010 Профиль/вход по имени, уникальность  COMPLETE
  - Endpoints: POST /api/auth/login, GET /api/user/profile
  - Schemas: contracts/schemas/user.json, contracts/schemas/error.json
  - Output: Создание/возврат профиля; уникальные имена; ошибки name_taken/invalid_name
  - Verify: FR-001, FR-013; UI_SPEC Inputs

 - [x] BE-T011 Каталог эмодзи (код + версия), редкость  COMPLETE
  - Endpoints: GET /api/emojis/catalog
  - Schemas: contracts/schemas/emojiCatalogItem.json
  - Output: Каталог с полями code, version, rarity, display_name, icon_ref
  - Verify: FR-011; DATA_CONTRACTS invariants

## Phase 2 - Wheel & Rarity

 - [x] BE-T020 Пул призов: мин. 8 сегментов, ≥1 эмодзи  COMPLETE
  - Endpoints: GET /api/spin/pool
  - Schemas: contracts/schemas/spinPool.json
  - Output: Формирование пула с минимум 8 сегментами и ≥1 эмодзи
  - Verify: FR-003, FR-012; invariants

  - [x] BE-T021 Политика редкости 85/10/5  COMPLETE
  - Endpoints: GET /api/spin/pool (веса), POST /api/spin (применение)
  - Output: Реализация классов редкости и их вероятностей
  - Verify: FR-009; SC-004 (≤15%)

 - [x] BE-T022 Результат спина, списание крутки  COMPLETE
  - Endpoints: POST /api/spin
  - Schemas: contracts/schemas/spinResult.json
  - Output: Генерация результата; уменьшение spins_remaining; ошибки no_spins_left/limit_banner_required
  - Verify: FR-004, FR-007, FR-008

 - [x] BE-T023 Дубли эмодзи: игнор + сообщение  COMPLETE
  - Endpoints: POST /api/spin
  - Output: При выпадении уже доступного эмодзи — duplicate=true; набор не меняется
  - Verify: Edge Cases; USER_STORIES US1-2

## Phase 3 - Limits & Perks

 - [x] BE-T030 Лимит 5/день, сброс по полуночи (UTC + смещение)  COMPLETE
  - Endpoints: GET /api/user/profile, POST /api/spin
  - Output: Учёт 5 круток/сутки; сброс по полуночи локального времени (UTC + смещение)
  - Verify: FR-008; Edge Cases про часовые пояса

 - [x] BE-T031 Перк «мульти-эмодзи» (до 3)  COMPLETE
  - Endpoints: POST /api/tasks/{taskId}/emojis, DELETE /api/tasks/{taskId}/emojis/{code}:{version}
  - Schemas: contracts/schemas/taskEmojiAssignment.json
  - Output: Принятие/валидация до 3 эмодзи/задачу при активном перке; ошибки multi_emoji_not_enabled/already_assigned
  - Verify: FR-014, FR-014a

## Phase 4 - Migration

- [x] BE-T040 Миграция JSON → БД (пропуск + отчёт, отклонение дублей имён)  COMPLETE
  - Inputs: practices/practice_05/project/tasks.json (если актуально), текущие JSON-источники
  - Output: Перенос данных; отчёт о пропусках/дублях; дубли имён отклонены
  - Verify: FR-016; RISKS миграции

## Phase 6 - Storage Refactor (SQLite)

- [x] BE-T060 Перевод на SQLite: схемы Users, EmojiCatalog, UserEmoji, Tasks, TaskEmoji, SpinHistory (опц.)  COMPLETE
  - Output: Централизованное хранение (SQLite); отказ от users.json для рантайма
  - Verify: FR-010; DATA_CONTRACTS

- [x] BE-T061 Миграция users.json → SQLite (пропуск + отчёт)  COMPLETE
  - Inputs: practices/practice_05/project/users.json
  - Output: Скрипт/команда миграции; отчёт о пропусках/дублях; после миграции бек использует SQLite
  - Verify: FR-016; RISKS миграции

## Phase 5 - Invariants

- [x] BE-T050 Инварианты: ≥1 эмодзи в пуле; хранение код+версия  COMPLETE
  - Output: Проверки на уровне сервиса/репозитория; ошибки pool_invalid при нарушении
  - Verify: FR-011, FR-012; contracts/invariants.md

## Verification

- [x] BE-V001 Проверка Acceptance Mapping из BACKEND_SPEC и соответствия contracts/endpoints.md  COMPLETE
  - Use examples: contracts/examples/login_request.json, login_response.json, profile_response.json, catalog_response.json, spin_pool_response.json, spin_result_response.json, spin_no_spins_case.json, spin_duplicate_emoji.json, task_add_emoji_request.json, task_add_emoji_response.json, task_remove_emoji_response.json
