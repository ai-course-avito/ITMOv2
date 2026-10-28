# Recon: Практика 4

Дата: 2026-10-07

Выводы по проекту в рамках каталога `practices/practice_04`:

- Есть минимальный исходный код: `src/calc.py` с функциями `add`, `avg`, `median`.
- Есть тесты на `unittest`: `tests/test_calc.py` покрывают `add`, `avg`, `median` и кейсы ошибок.
- Единая команда проверки: `bash practices/practice_04/scripts/check.sh` (внутри `python -m unittest -q`), вывод сохраняется в `evidence/.last-check.log`.
- Настроен skill-шаблон `skills/test-runner` (скрипт запуска тестов) — требует заполнения `SKILL.md`.
- Реализован локальный MCP сервер `mcp/file_summary_server.py` (JSON-RPC по stdin/stdout) с методом `file_summary(path)`.
- В корне есть `AGENTS.md` с правилами для агента.
- В `opencode.json` требуется привести JSON в валидный вид и корректно разместить `hooks` и `mcp` подключения.

CHECK_COMMANDS: `bash practices/practice_04/scripts/check.sh`.

Принятые допущения (см. также `evidence/decisions.md`):

- STACK: Python 3.x + unittest, без внешних зависимостей.
- FEATURE_A: округление результата `avg(values, ndigits=None)`.
- FEATURE_B: функция `median(values)`.
- SKILL: "test-runner" — запускает проверку и сохраняет лог.
- MCP tool: `file_summary(path)` — размер, строки, SHA256.
