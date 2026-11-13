# Smart Search: Tasks

## Plan
1. Создать команду `/smart-search` в `.opencode/commands/smart-search.md` по `spec.md`.
2. Реализовать поиск: glob → grep → read → ранжирование → форматированный вывод.
3. Тестировать на демо‑сценариях:
   - Демо 1: `check_pptx` (ожидаем: `practices/practice_03/check_pptx.py`, Makefile цели).
   - Демо 2: `pptx-reader` (ожидаем: `mcp/pptx-reader/server.py`, `opencode.json`).
   - Демо 3: `unsubscribe` (ожидаем: негативный ответ в контексте demo, но поиск по всему репо — если совпадений нет, негатив).
   - Негативный: `nonexistent123`.
4. Зафиксировать в `docs/HANDOFF.md` результаты проверки (ссылки и краткие выводы).

## Acceptance
- Вывод соответствует формату (file:line + 2–3 строки + краткое объяснение).
- Лимит топ‑10, приоритет `.py > .md > Makefile > .json` соблюдён.
- Исключения путей применены.
- Негативные кейсы оформлены корректно.
