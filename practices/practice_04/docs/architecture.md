# Архитектура Tetris (practice_04)

Документ описывает слои продукта, поток данных и границы ответственности.
Спецификация поведения — `docs/spec.md`, контракт работы агентов — `AGENTS.md`.

---

## 1. Слои

| Слой | Каталог | Зависит от | Отвечает за |
|---|---|---|---|
| Ядро | `include/tetris/core`, `src/core` | только стандартная библиотека | правила игры: поле, фигуры, SRS-вылеты, 7-bag, гравитация, lock delay, hold, очки, T-spin |
| Сериализация | `src/core/serialize.cpp` | ядро | `GameSnapshot` → JSON (схема раздела 6 `docs/spec.md`) и `board_hash` |
| ASCII-рендер | `src/ui/ascii.cpp` | ядро | `GameSnapshot` → человекочитаемое поле (`--ascii`, MCP `tetris_render`) |
| CLI | `src/main.cpp` | ядро, сериализация, ASCII, SDL-фронтенд | разбор аргументов раздела 5, headless-прогон, коды выхода |
| SDL-фронтенд | `src/ui/sdl_app.cpp` | SDL2, ядро | окно, ввод с клавиатуры, отрисовка, HUD |
| MCP | `mcp_server/tetris_mcp.py` | собранный `build/tetris` | инструменты-обёртки над CLI для агента |

Ключевое ограничение: ядро не знает про SDL и не печатает в stdout. UI-слои
работают только на чтение — им доступен `Game::snapshot()`, `Game::apply()`,
`Game::advance_ticks()` и `Game::reset()`. Заголовки в `include/tetris/`
заморожены: сигнатуры меняет только архитектор (человек).

## 2. Поток данных

Ввод приходит из одного из двух источников и сходится в одной точке — `Game::apply()`:

- headless: строка `--script "L2CWHOLDHDT30"` разбирается в токены
  (`action_from_token`, `action_repeat_from_token`) и применяется к ядру;
  после каждого токена выполняется один тик гравитации (`T` сам является тиком);
- SDL: `SDL_KEYDOWN` в `sdl_app.cpp` отображается на `Action` (стрелки, X/Z/A,
  Space, C/LShift, R, P, Esc/Q), а `Game::advance_ticks(1)` вызывается из
  игрового цикла с частотой `config.fps`.

```text
ввод (скрипт | SDL-событие)
        │
        ▼
   Game::apply(Action)  ──►  Game::advance_ticks(1)
        │
        ▼
   Game::snapshot() : GameSnapshot
        │
        ├──► to_json()       ──► stdout (--json, по умолчанию в headless)
        ├──► render_ascii()  ──► stdout (--ascii) / MCP tetris_render
        └──► render_frame()  ──► окно SDL2 (призрак, hold, next, HUD)
```

Детерминизм держится на том, что единственный источник случайности — `PieceBag`
с явным `uint64_t seed` (xorshift64\*). При одинаковых `seed` и сценарии
`board_hash` совпадает побитово (AC-4.2).

## 3. Диаграмма компонентов

```plantuml
@startuml tetris-architecture
!theme plain
skinparam componentStyle rectangle
skinparam shadowing false

package "practice_04" {

  package "include/tetris/core (замороженный интерфейс)" as HDR {
    [types.hpp] as H_types
    [board.hpp] as H_board
    [pieces.hpp] as H_pieces
    [bag.hpp] as H_bag
    [scoring.hpp] as H_scoring
    [game.hpp] as H_game
    [serialize.hpp] as H_serialize
  }

  package "src/core" as CORE {
    [board.cpp] as C_board
    [pieces.cpp] as C_pieces
    [bag.cpp] as C_bag
    [scoring.cpp] as C_scoring
    [game.cpp <b>Game, run_script</b>] as C_game
    [serialize.cpp <b>to_json</b>] as C_serialize
  }

  package "src/ui" as UI {
    [ascii.cpp <b>render_ascii</b>] as U_ascii
    [sdl_app.cpp <b>run_sdl</b>] as U_sdl
  }

  [src/main.cpp\n<b>CLI: --headless / --seed / --script / --ticks / --json / --ascii / --no-board</b>] as CLI

  package "tests (ctest)" as TESTS {
    [tetris_tests\ntest_framework.hpp] as TESTBIN
  }
}

cloud "SDL2 2.32 (pkg-config)" as SDL2
node "MCP-сервер\nmcp_server/tetris_mcp.py" as MCP
actor "Игрок" as Player
actor "LLM-агент" as Agent

Player --> U_sdl : клавиатура
Agent --> MCP : tools

CLI --> C_game : run_script(seed, script, ticks)
CLI --> C_serialize : to_json(snapshot, include_board)
CLI --> U_ascii : render_ascii(snapshot)
CLI --> U_sdl : run_sdl(game, config)
CLI ..> HDR : только публичный API

U_sdl --> C_game : apply(Action) / advance_ticks(1) / snapshot()
U_sdl --> SDL2 : SDL_Init, SDL_CreateWindow,\nSDL_CreateRenderer, SDL_RenderFillRect
U_ascii --> C_game : snapshot()

C_game --> C_board
C_game --> C_pieces
C_game --> C_bag
C_game --> C_scoring
C_serialize --> C_game

TESTBIN --> C_game
TESTBIN --> C_pieces
TESTBIN --> C_board
TESTBIN --> C_bag
TESTBIN --> C_scoring
TESTBIN --> C_serialize
TESTBIN --> U_ascii
TESTBIN -[hidden]- SDL2 : тесты headless,\nSDL не линкуется

MCP --> CLI : build/tetris --headless --json

note right of CLI
  Коды выхода (раздел 5):\n  0 — прогон выполнен (в т.ч. game over)\n  1 — ошибка инициализации SDL\n  2 — ошибка аргументов
end note

note bottom of U_sdl
  Логика игры не дублируется:\nSDL-цикл только читает snapshot()
  и вызывает apply()/advance_ticks().
  SDL_ttf нет — текст рисуется
  пиксельным шрифтом 3x5 из прямоугольников.
end note

@enduml
```

## 4. Сборка

- `CMakeLists.txt` — C++20, `-Wall -Wextra -Wpedantic`, две цели:
  - `tetris`: `src/main.cpp`, `src/ui/sdl_app.cpp`, `src/ui/ascii.cpp`, `src/core/*.cpp`; линкует SDL2;
  - `tetris_tests`: `tests/*.cpp`, `src/ui/ascii.cpp`, `src/core/*.cpp`; SDL2 не линкует.
- `src/core/*.cpp` и `tests/*.cpp` подключаются через `file(GLOB_RECURSE ... CONFIGURE_DEPENDS)`,
  чтобы конфигурация не падала на ещё не созданных файлах.
- `enable_testing()` + `add_test(NAME core COMMAND tetris_tests)` — тесты запускаются `ctest`.
- `Makefile` — обёртка (`build`, `test`, `sim`, `run`, `clean`, `help`).
