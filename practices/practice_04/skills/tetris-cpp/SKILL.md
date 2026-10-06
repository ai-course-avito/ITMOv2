---
name: tetris-cpp
description: "Use when working on the practice_04 Tetris C++ project (add a feature, fix the core, run sims, use its MCP server)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [cpp, tetris, cmake, sdl2, mcp, practice-4, vibe-coding]
    related_skills: [hermes-agent, test-driven-development]
---

# Tetris C++ (practice_04): рабочая процедура

Проектный скилл для `~/projects/ITMOv2/practices/practice_04`. Правила проекта лежат в
`AGENTS.md`, поведение продукта — в `docs/spec.md`; этот скилл описывает **как работать**,
а не что за продукт.

## Когда применять

- Добавить фичу или починить ядро Tetris в `practice_04`.
- Нужно прогнать партию без окна (симуляция, регресс, доказательство детерминизма).
- Нужно через MCP узнать спеку/состояние продукта, не читая C++.

## Карта проекта

```
AGENTS.md            правила и гейты (читать первым)
docs/spec.md         источник истины по поведению (SRS, очки, CLI, JSON)
include/tetris/      ЗАМОРОЖЕННЫЙ интерфейс: менять только с согласия человека
src/core/            ядро: без SDL, без вывода в stdout, без std::rand
src/ui/ascii.cpp     ASCII-рендер: используется CLI и MCP-инструментом render
src/ui/sdl_app.cpp   окно SDL2; вся логика — вызовами Game::apply/advance_ticks
src/main.cpp         CLI (--headless/--seed/--script/--ticks/--json/--ascii)
tests/               unit-тесты на своём мини-фреймворке (test_framework.hpp)
mcp_server/          MCP-сервер продукта (stdio) + mcp_smoke.py
```

## Команды

```bash
cd ~/projects/ITMOv2/practices/practice_04
make build                      # cmake configure + build
make test                       # ctest --output-on-failure
make sim SEED=42 SCRIPT="HDHD"  # headless JSON-прогон
make run                        # SDL2-окно
make hooks                      # список хуков + doctor + самопроверка правил
```

Быстрый цикл без cmake (быстрее и проверяет только ядро):

```bash
g++ -std=c++20 -Wall -Wextra -Wpedantic -O1 -Iinclude -o /tmp/core_tests \
    src/core/*.cpp src/ui/ascii.cpp tests/*.cpp && /tmp/core_tests
```

## Процедура добавления фичи (TDD)

1. Найди пункт спеки (`docs/spec.md`) или US/AC, к которому относится фича. Нет пункта —
   сначала обнови спеку, потом код.
2. Напиши падающий тест в `tests/` на новое поведение. Прогони — убедись, что красный
   (иначе тест ничего не проверяет).
3. Реализуй минимально, пока тест не позеленеет. Правь `src/`, не `include/`.
4. Прогони `make test` целиком: регресса быть не должно.
5. Проверь детерминизм: два прогона `make sim SEED=42 SCRIPT="..."` дают одинаковый
   `board_hash`.
6. Обнови `docs/spec.md` (поведение) и `AGENTS.md` (структура), если менялось.

## MCP-инструменты (что использовать вместо чтения кода)

`mcp__tetris__info` → живой ли проект и собран ли;
`mcp__tetris__spec` → раздел спецификации;
`mcp__tetris__sim` (seed, script, max_ticks, include_board) → JSON состояния;
`mcp__tetris__render` → ASCII-поле;
`mcp__tetris__build`, `mcp__tetris__test` → сборка и ctest с разбором итога.

Ручная проверка сервера без агента:
`/home/rreflector/.hermes/hermes-agent/venv/bin/python mcp_server/mcp_smoke.py`.

Важно: пакет `mcp` живёт **в venv Hermes** (`~/.hermes/hermes-agent/venv`), версия 2.0.0 —
это API `mcp.server.mcpserver.MCPServer` (не FastMCP: `mcp.server.fastmcp` там отсутствует).
Системный `python3` пакет `mcp` не видит. Сервер знает только stdio: Hermes поднимает его
как подпроцесс этим же интерпретатором.

## Хуки проекта (что тебя остановит)

Три shell-хука Hermes подключены в `~/.hermes/config.yaml` и указывают на скрипты в
`hooks/` этого проекта — правила `AGENTS.md` стали механическими:

- `hooks/frozen_headers.py` (`pre_tool_call`, matcher `write_file|patch|terminal`, `fail_closed`)
  — правка `include/tetris/**` блокируется и файловыми инструментами, и шеллом. Если правка
  интерфейса действительно согласована человеком, сессия запускается как
  `HERMES_ALLOW_FROZEN_HEADERS=1 hermes chat`, и тогда обновляются и доки (`docs/spec.md`,
  `AGENTS.md`), и заголовок.
- `hooks/git_gate.py` (`pre_tool_call`, matcher `terminal`) — `git commit/push/rebase/...`
  уходят в гейт подтверждения человека; при красных тестах команда блокируется. В одноразовом
  режиме (`hermes chat -q`) подтверждать некому, поэтому команда не выполняется — это ожидаемо.
- `hooks/project_context.py` (`pre_llm_call`) — в каждый ход подкладывает состояние проекта
  (ветка, незакоммиченные файлы, сборка, итог тестов). Не пересказывай эти числа «по памяти»:
  они и так в контексте и обновляются сами.

Проверка и отладка: `make hooks` (список + doctor + самопроверка правил),
`hermes hooks test pre_tool_call --for-tool write_file`. Consent хранится в
`~/.hermes/shell-hooks-allowlist.json`; на новой машине хуки нужно подтвердить заново
(`--accept-hooks` или `hooks_auto_accept: true`). Правка самого скрипта consent не снимает —
`hermes hooks doctor` показывает mtime drift.

## Грабли (проверено на этом проекте)

- **Буфер — 4 строки, а не 2.** Вертикальные состояния I занимают 4 клетки: с буфером в
  2 строки поворот I сразу после спавна выбрасывает фигуру за поле. `Board::kHeight == 24`.
- **Ядро не знает про SDL и не печатает.** Любой `printf`/`cout` в `src/core/` ломает
  JSON-контракт CLI и MCP.
- **Случайность только через `PieceBag` с явным seed.** `std::rand`, `time()` и статические
  счётчики убивают воспроизводимость — два прогона разойдутся по `board_hash`.
- **Спавн и lock out.** Бокс спавна: `x = 3`, нижняя строка бокса на `y = 20` (буфер).
  Фигура, уложившаяся целиком при `y >= 20`, — lock out (game over), даже если поле пустое.
- **Вылеты SRS — покомпонентная таблица.** Знаки у I и у JLSTZ разные; генерация таблицы
  формулой из одной строки даёт неверные вылеты. Таблица — в `docs/spec.md`, раздел 2.
- **Сборка без дисплея.** `make test` и `make sim` не должны требовать SDL/дисплея: только
  `make run` открывает окно, а при недоступном SDL он возвращает код 1, не падает.
- **Токены сценария разделяются пробелом или запятой.** `HDHDHD` — это один неизвестный
  токен: CLI теперь выходит с кодом 2. Не склеивать токены в одну строку без разделителей и
  не «ремонтировать» падающий сценарий его ослаблением.
- **Файловые операции — не в `sdl_app.cpp`.** Хранение рекорда живёт в `tetris::highscore`
  (`src/ui/highscore.cpp`, без SDL) именно для того, чтобы покрываться unit-тестами; не
  возвращать файловый код в SDL-модуль.
- **Проверять текст на случайные CJK-символы** перед сдачей:
  `grep -rlP '[\x{4e00}-\x{9fff}]' .`

## Гейты перед «готово»

`make build` без предупреждений, `make test` зелёный, `make sim` детерминирован,
`hermes mcp test tetris` отвечает, `mcp_tetris_sim` возвращает JSON, в `docs/` и `AGENTS.md`
нет расхождений с кодом. Теста нет — задача не готова (см. DoD в `AGENTS.md`).
