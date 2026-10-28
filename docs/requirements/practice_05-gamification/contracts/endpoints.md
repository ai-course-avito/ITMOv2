# Contracts

**Feature**: practice_05-gamification — Internal UI ↔ Backend Contracts
**Created**: 2026-10-28

## Contract List

| Name | Type | Inputs | Outputs | Notes |
|------|------|--------|---------|-------|
| POST /api/auth/login | API | { name } | User profile | Создать/вернуть профиль; имя уникально |
| GET /api/user/profile | API | – | User profile | Текущий профиль и лимиты |
| GET /api/emojis/catalog | API | – | EmojiCatalog[] | Справочник (код+версия, редкость) |
| GET /api/spin/pool | API | – | SpinPool | ≥1 эмодзи в пуле |
| POST /api/spin | API | – | SpinResult | Списывает 1 крутку |
| POST /api/tasks/{taskId}/emojis | API | TaskEmojiAssignment | Task with emojis | Учитывает перк мульти-эмодзи |
| DELETE /api/tasks/{taskId}/emojis/{code}:{version} | API | – | Task with emojis | Снять эмодзи с задачи |

## Contract Details

### POST /api/auth/login
- Type: API
- Purpose: Вход по имени; создать профиль при первом входе; обеспечить уникальность имён (идемпотентно: создать-или-вернуть).
- Inputs: { name: string }
- Outputs: User profile (см. schemas/user.json)
- Errors: invalid_name
- Auth/Permissions: нет токенов; имя как идентификатор сессии (локальная среда)

### GET /api/user/profile
- Type: API
- Purpose: Получить профиль, остаток круток, признаки перков, время до сброса.
- Inputs: –
- Outputs: User profile
- Errors: not_found

### GET /api/emojis/catalog
- Type: API
- Purpose: Получить каталог эмодзи (код + версия, редкость, отображение).
- Inputs: –
- Outputs: EmojiCatalog[]
- Errors: –

### GET /api/spin/pool
- Type: API
- Purpose: Получить пул призов для текущего раунда колеса (мин. 8 сегментов; ≥1 эмодзи).
- Inputs: –
- Outputs: SpinPool
- Errors: –

### POST /api/spin
- Type: API
- Purpose: Выполнить спин; вернуть результат; списать крутку.
- Inputs: –
- Outputs: SpinResult
- Errors: no_spins_left, limit_banner_required, pool_invalid (если нет ≥1 эмодзи), duplicate_handled (информ. флаг в результате)

### POST /api/tasks/{taskId}/emojis
- Type: API
- Purpose: Добавить эмодзи к задаче с учётом правил мульти-эмодзи.
- Inputs: TaskEmojiAssignment (см. schemas/taskEmojiAssignment.json)
- Outputs: Task with emojis (см. examples)
- Errors: emoji_locked, multi_emoji_not_enabled, already_assigned, not_found

### DELETE /api/tasks/{taskId}/emojis/{code}:{version}
- Type: API
- Purpose: Снять эмодзи с задачи.
- Inputs: –
- Outputs: Task with emojis (обновлённый список)
- Errors: not_found
