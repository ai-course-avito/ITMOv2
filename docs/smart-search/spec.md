# Smart Search: Specification

## Purpose
Быстрый поиск по всему репозиторию ITMOv2: код, документация и артефакты практик. Команда предназначена для чтения и анализа, без записи.

## Command
Будет реализовано как `/smart-search` в `.opencode/commands/smart-search.md` (создание команды — отдельная задача). Выполняется в режиме Build и использует только инструменты `glob`, `grep`, `read`.

## Scope
- Диапазон поиска: корень `ITMOv2/`.
- Исключения путей:
  - `**/node_modules/**`
  - `**/.venv/**`
  - `**/__pycache__/**`
  - `practices/practice_03/lab/results/*.jsonl`
- Поддержка синонимов: `unsubscribe|remove|cancel|optout|delete|detach`.

## Tools
- Только read/glob/grep. Без bash, без записи файлов.

## Output Format
- Для каждого совпадения: `file:line` + фрагмент 2–3 строки вокруг совпадения + короткое объяснение (одно предложение).
- Лимит: топ‑10 совпадений.
- Приоритет файлов: `.py > .md > Makefile > .json`.
- Негативный результат: текст «В предоставленных материалах нет ответа» + список проверенных путей/паттернов (маски glob и ключевые слова).

## Examples
- `/smart-search check_pptx` → найдёт `practices/practice_03/check_pptx.py` и цели Makefile, покажет `file:line` и контекст.
- `/smart-search pptx-reader` → найдёт `mcp/pptx-reader/server.py` и упоминания в `opencode.json`.
- `/smart-search unsubscribe` → при отсутствии — негативный ответ с перечислением проверённых мест.
- `/smart-search nonexistent123` → негативный ответ.

## Constraints
- Не изменяет demo/ и код практик 1–4.
- Не создаёт индексы, кеши, не пишет артефакты.
- Результаты проверки фиксируются отдельно (см. DoD и tasks).

## Definition of Done
- Подготовлены `proposal.md`, `design.md`, `tasks.md`.
- Команда документирована и проверена на 3 демо‑сценариях и негативном кейсе.
