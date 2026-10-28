# Configured environment — описание артефактов (проект subtracker)

Проект: трекер подписок (FastAPI, SQLAlchemy async, Postgres). Среда состоит из четырёх артефактов: правила (AGENTS), skills, MCP и hook.

## 1. AGENTS — `AGENTS.md`

**Что это.** Файл правил проекта, который агент читает всегда: стек, структура репозитория, порты, команды запуска, тестов и ruff, конвенции и запреты.

**Зачем.** Чтобы агент не угадывал правила проекта. Ключевые: деньги только `Decimal`, бизнес-логика в сервисах, пользователь видит только свои подписки, тест на каждый эндпоинт, `.env` не коммитить.

## 2. Skills — `.claude/skills/`

**Что это.** Папки с `SKILL.md`. В контексте всегда лежит только `description`, а тело и `references/` подгружаются, когда скилл нужен.

| Скилл | Источник | Когда применять |
|---|---|---|
| `fastapi-arch` | ericrisco/rsc-harness | архитектура и жизненный цикл FastAPI-сервиса: роутеры, DI, async SQLAlchemy, JWT |
| `fastapi-ref` | lynricsy/hyperskills | точные правила механики FastAPI: `Annotated`, `async def` против `def`, `response_model`, lifespan |
| `python-backend-expert` | hieutrtr/ai1-skills | реализация эндпоинтов, моделей и сервисного слоя |
| `pytest-patterns` | hieutrtr/ai1-skills | как писать тесты pytest для FastAPI |
| `task-decomposition` | hieutrtr/ai1-skills | разбиение фичи на проверяемые шаги |

**Зачем эти пять.** Они соответствуют стеку из AGENTS.md: архитектура и правила FastAPI, реализация, тесты, планирование.

## 3. MCP — `.mcp.json`, `tools/mcp-pg/`

**Что это.** MCP-сервер — программа, которую Claude Code запускает при старте сессии. Она подключается к Postgres и отдаёт агенту 5 tools: `query`, `schema`, `table_info`, `explain`, `list_schemas`. `.mcp.json` содержит команду запуска и строку подключения к базе `subtracker`.

**Зачем.** Агент видит реальную схему и данные базы проекта, а не гадает о таблицах.

## 4. Hook — `.claude/settings.json`, `.claude/hooks/`

**Что это.** Автоматическая проверка, которая срабатывает при каждом вызове инструментов. Событие `PreToolUse`, matcher `Write|Edit|Bash`, скрипт `protect_env.py`. Он блокирует (код 2, причина уходит агенту) запись в `.env`, `.env.local`, `.env.production` и т. п., в том числе через Bash. `.env.example` и чтение (`cat`, `grep`) разрешены.

**Зачем.** AGENTS.md запрещает править и коммитить `.env`. Хук делает правило обязательным, а не «если агент вспомнит».

**Ограничение.** Проверка Bash идёт по тексту команды, её можно обойти хитрой конструкцией. Это защита от случайной записи, не от злого умысла.

**Подтверждения:**
- `evidence/hook_unit_tests.txt` — 32 теста (`.claude/hooks/test_protect_env.py`);
- `evidence/hook_command_checks.txt` — точная команда из `settings.json` на примерах;
- `evidence/hook_live_bypass_before_fix.png` — первый живой прогон, обход через Bash;
- `evidence/hook_live_block.png` — живой прогон после исправления, запись заблокирована.
