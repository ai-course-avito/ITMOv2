# HANDOFF.md — Состояние проекта «Гонки»

## 1. Что уже сделано
- **Фича A (входная валидация):**
  - Эндпоинт `/select-car` на FastAPI со строгой валидацией Pydantic (`extra="forbid"`) по разрешённым моделям (`racer`, `drifter`, `tank`) и палитре (`red`, `yellow`, `purple`).
  - Эндпоинт `/report-error` для отправки отчётов об ошибках пользователей.
  - Покрыто тестами `pytest` (11 тестов в `backend/tests/`, все зелёные).
- **Игровая механика и UI:**
  - Фронтенд на Vue 3 + Vite.
  - Режим на двух игроков (W/A/S/D и Стрелочки) с выбором машин и цветов.
  - Кольцевая трасса на Canvas с ограничением выезда за бордюры и контролем направления движения.
  - Финальный экран победы по завершении 1 круга с возможностью перезапуска игры.
- **Окружение агента и домашка:**
  - `AGENTS.md` с правилами проекта, стилем кода и контрактами.
  - `SKILLS.md` с обоснованием выбора скиллов и разбором `vue-best-practices`.
  - Локальный skill `race-rules` в `.claude/skills/race-rules/SKILL.md`.
  - Двухуровневая автоматическая проверка: Git hook `hooks/pre-commit` и агентский hook `.claude/settings.json` через runner `scripts/check.sh`.
  - Собственный MCP-сервер `mcp_server.py` с тулами `validate_race_entry` и `simulate_race`, сконфигурированный в `.mcp.json` и покрытый тестами на корректный и ошибочный ввод (`tests/test_mcp_server.py`).
  - Документы для сдачи: `report.md` (отчёт по среде) и `reflection.md` (живая рефлексия).

## 2. Команды для запуска и проверки
- Проверка бэкенда: `bash scripts/check.sh`
- Тесты MCP-сервера: `PYTHONPATH=. /Users/kamilasalyakhova/Documents/itmo/ai-eng/гонки/backend/.venv/bin/pytest tests/test_mcp_server.py`
- Запуск бэкенда: `cd backend && .venv/bin/uvicorn app.main:app --port 8000`
- Запуск фронтенда: `cd frontend && npm run dev`

## 3. Что осталось / следующие шаги
- Интеграция фичи B (таймаут/ошибка зависимости при зависании движка гонки) в бэкенд по сценарию из AGENTS.md.
