# MCP-сервер Tetris: сырые вводы и выводы

Здесь показано, что именно уходит MCP-серверу и что он возвращает — без пересказа и
«примерно так». Источник данных — файл `docs/evidence/mcp-transcript.jsonl`: это снятые
подряд JSON-RPC-кадры по stdio (одна пара «запрос → ответ» на строку). Снято командой:

```bash
cd practices/practice_04
/home/rreflector/.hermes/hermes-agent/venv/bin/python mcp_server/mcp_transcript.py docs/evidence/mcp-transcript.jsonl
```

Скрипт поднимает `mcp_server/tetris_mcp.py` подпроцессом, говорит с ним по протоколу
(без SDK, чтобы кадры были видны целиком) и сохраняет всё как есть.

## Как устроено общение: три шага протокола

MCP — это JSON-RPC 2.0 поверх stdin/stdout подпроцесса. Клиент (в живой работе — агент
Hermes, здесь — скрипт) делает три вещи: рукопожатие, запрос списка инструментов и вызовы.

Рукопожатие `initialize` → сервер отвечает, кто он и что умеет:

```json
{"jsonrpc": "2.0", "id": 1, "method": "initialize",
 "params": {"protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "mcp-transcript", "version": "0.1.0"}}}
```

```json
{"result": {"protocolVersion": "2025-11-25",
  "serverInfo": {"name": "tetris", "version": "0.1.0"},
  "capabilities": {"tools": {"listChanged": false},
                   "resources": {"listChanged": false, "subscribe": false},
                   "prompts": {"listChanged": false}, "experimental": {}},
  "instructions": "Инструменты проекта Tetris: спецификация продукта, сборка, тесты, детерминированные симуляции и ASCII-рендер поля. Симуляции запускают build/tetris --headless, поэтому результат совпадает с тем, что видят тесты."}}
```

`tools/list` → шесть инструментов с описаниями и схемами аргументов:

| Инструмент | Что делает | Аргументы |
|---|---|---|
| `info` | состояние проекта: пути, наличие сборки, версии компилятора и CMake, git-ветка | — |
| `spec` | раздел `docs/spec.md` | `section`: `all` \| `product` \| `rules` \| `stories` \| `scoring` \| `cli` \| `json` \| `mcp` \| `tests` |
| `sim` | детерминированный прогон без окна → JSON состояния игры | `seed`, `script`, `max_ticks`, `include_board` |
| `render` | то же, но ASCII-поле текстом | `seed`, `script`, `max_ticks` |
| `build` | `cmake -S . -B build && cmake --build build` | `clean`, `jobs` |
| `test` | `ctest --test-dir build --output-on-failure` с разбором итога | `filter` |

В сессии агента эти инструменты видны как `mcp_tetris_info`, `mcp_tetris_sim` и так далее.

## Успешный вызов: `sim`

Запрос (кадр целиком, как он ушёл серверу):

```json
{"jsonrpc": "2.0", "id": 3, "method": "tools/call",
 "params": {"name": "sim", "arguments": {"seed": 42, "script": "HD HD"}}}
```

Ответ (текст внутри `result.content[0].text`, `isError: false`):

```json
{
  "ok": true,
  "seed": 42,
  "script": "HD HD",
  "state": {
    "seed": 42,
    "tick": 2,
    "score": 78,
    "lines": 0,
    "level": 1,
    "combo": -1,
    "back_to_back": false,
    "game_over": false,
    "hold": null,
    "hold_used": false,
    "active": {"type": "L", "rotation": 0, "x": 3, "y": 20},
    "ghost": {"x": 3, "y": 3},
    "next": ["Z", "O", "J", "S", "I"],
    "board": {
      "width": 10,
      "height": 20,
      "rows": ["..........", "..........", "..........", "..........", "..........",
               "..........", "..........", "..........", "..........", "..........",
               "..........", "..........", "..........", "..........", "..........",
               "..........", "..........", "...IIII...", "....T.....", "...TTT...."]
    },
    "board_hash": "aafee736b2b7b691",
    "holes": 4,
    "events": ["hard_drop"]
  }
}
```

Тот же результат даёт CLI напрямую, то есть агент и тесты смотрят на одно поведение:

```bash
./build/tetris --headless --seed 42 --script "HD HD" --json   # board_hash=aafee736b2b7b691, score=78
```

## Успешный вызов: `render` (ASCII-поле)

Запрос: `{"name": "render", "arguments": {"seed": 42, "script": "L3 CW HD T30 HOLD HD HD"}}`

Ответ (`field` — текст, который агент видит как поле):

```json
{
  "ok": true,
  "seed": 42,
  "script": "L3 CW HD T30 HOLD HD HD",
  "field": "TETRIS\n+----------+\n|..........|\n|..........|\n|..........|\n|..........|\n|..........|\n|..........|\n|..........|\n|..........|\n|..........|\n|..........|\n|..........|\n|..........|\n|..........|\n|..........|\n|....::....|\n|....::....|\n|...ZZ.....|\n|T...ZZ....|\n|TT...L....|\n|T..LLL....|\n+----------+\nScore: 116\nLines: 0  Level: 1\nHold: I\nNext: J S I O T"
}
```

В развёрнутом виде это то самое поле, которое видит игрок (20 строк, как в `field` выше):

```text
TETRIS
+----------+
|..........|
|..........|
|..........|
|..........|
|..........|
|..........|
|..........|
|..........|
|..........|
|..........|
|..........|
|..........|
|..........|
|..........|
|....::....|
|....::....|
|...ZZ.....|
|T...ZZ....|
|TT...L....|
|T..LLL....|
+----------+
Score: 116
Lines: 0  Level: 1
Hold: I
Next: J S I O T
```

## Успешные вызовы: `test` и `info`

`test` возвращает не только «успех», но и разобранный итог:

```json
{"ok": true, "returncode": 0, "passed": 1, "failed": 0, "total": 1,
 "summary": "100% tests passed, 0 tests failed out of 1",
 "output": "Internal ctest changing into directory: .../practice_04/build\nTest project .../build\n    Start 1: core\n1/1 Test #1: core .............................   Passed    0.00 sec\n\n100% tests passed, 0 tests failed out of 1\n"}
```

`info` подтверждает, что сервер отвечает про реальную сборку, а не про свои предположения:

```json
{"project_root": "/home/rreflector/projects/ITMOv2/practices/practice_04",
 "spec_path": ".../docs/spec.md",
 "binary": ".../build/tetris",
 "binary_exists": true,
 "tests_binary_exists": true,
 "binary_mtime": 1791387869.7798529,
 "cxx": "g++ (Debian 14.2.0-19) 14.2.0",
 "cmake": "cmake version 3.31.6",
 "git_branch": "practice_4"}
```

## Ошибочные входы: три разных вида отказа

**1. Значение, которого нет в предметной области.** Запрос `sim` со сценарием `"XX HD"`:

```json
{"ok": false,
 "error": "тетрис вернул код 2",
 "stderr": "tetris: неизвестный токен сценария: \"XX\" (см. --help, раздел --script)\nПодсказка: tetris --help"}
```

Сервер не придумывает своё сообщение — он прокидывает текст ошибки самого CLI, поэтому
агент видит ту же формулировку, что и человек в терминале. `isError: false`: это
корректный ответ инструмента про некорректный ввод.

**2. Неверный тип аргумента** — отказ до вызова функции, на уровне схемы. Запрос
`sim` с `"seed": "сорок два"`:

```text
Error executing tool sim: 1 validation error for simArguments
seed
  Input should be a valid integer, unable to parse string as an integer
  [type=int_parsing, input_value='сорок два', input_type=str]
```

Здесь `isError: true` — это ошибка протокола: агент сразу понимает, что аргумент надо
исправить, а не искать причину в продукте.

**3. Неизвестный вариант аргумента.** Запрос `spec` с `"section": "нет-такого"`:

```json
{"ok": false,
 "error": "неизвестный раздел 'нет-такого'",
 "available": ["cli", "json", "mcp", "product", "rules", "scoring", "stories", "tests"]}
```

Список допустимых значений — самое полезное, что можно вернуть агенту: он не угадывает,
а берёт одно из перечисленных.

Есть и четвёртый случай, предусмотренный кодом: если `build/tetris` не собран,
`sim` и `render` отвечают `{"ok": false, "error": "бинарник build/tetris не найден",
"hint": "вызови инструмент tetris_build (или выполни `make build`)"}` — то есть не падают,
а подсказывают следующий шаг.

## Что из этого следует

- Инструменты отдают наблюдаемое поведение продукта, а не исходники: агент получает
  `board_hash`, поле и итог тестов, не читая C++.
- Контракт общий: `sim` через MCP и `--json` в CLI дают одинаковые числа (совпадающий
  `board_hash`), потому что сервер вызывает тот же бинарник.
- Ошибки спроектированы, а не случайны: текст от продукта, проверка типов от схемы,
  список допустимых значений, подсказка про сборку. Агент на каждом отказе знает, что делать.

## Как воспроизвести

```bash
cd practices/practice_04
make build
/home/rreflector/.hermes/hermes-agent/venv/bin/python mcp_server/mcp_smoke.py     # короткая проверка
/home/rreflector/.hermes/hermes-agent/venv/bin/python mcp_server/mcp_transcript.py docs/evidence/mcp-transcript.jsonl   # сырой протокол заново
hermes mcp test tetris                                                            # рукопожатие из Hermes
```
