# MCP-сервер проекта (прототип практики 4)

`tetris_mcp.py` — MCP-сервер продукта на stdio-транспорте. Он даёт агенту
**наблюдаемое поведение продукта**: спецификацию, сборку, тесты, детерминированные
симуляции и ASCII-поле. Правил игры в Python нет — сервер вызывает собранный
`build/tetris` и переиспользует его JSON-контракт (`docs/spec.md`, раздел 6),
поэтому логика не дублируется и не расходится между C++ и Python.

## Инструменты

| Инструмент | Имя в сессии агента | Что делает |
|---|---|---|
| `info` | `mcp__tetris__info` | пути проекта, наличие сборки, версии g++/cmake, git-ветка |
| `spec` | `mcp__tetris__spec` | раздел спецификации (`all`, `rules`, `scoring`, `stories`, `cli`, `json`, `mcp`, `tests`) |
| `sim` | `mcp__tetris__sim` | прогон `build/tetris --headless --json` → состояние игры |
| `render` | `mcp__tetris__render` | прогон `--ascii` → поле текстом |
| `build` | `mcp__tetris__build` | `cmake -S . -B build && cmake --build build` |
| `test` | `mcp__tetris__test` | `ctest --test-dir build --output-on-failure` с разбором итога |

## Подключение к Hermes

Сервер использует Python из окружения Hermes (там уже установлен пакет `mcp`):

```bash
hermes mcp add tetris \
  --command /home/rreflector/.hermes/hermes-agent/venv/bin/python \
  --args /home/rreflector/projects/ITMOv2/practices/practice_04/mcp_server/tetris_mcp.py

hermes mcp list          # сервер в списке
hermes mcp test tetris   # рукопожатие и список инструментов
```

Конфигурация попадает в `~/.hermes/config.yaml` (секция `mcp_servers`), поэтому
добавлять её в репозиторий не нужно. Инструменты подхватываются при следующем
запуске агента.

## Ручная проверка без агента

Рукопожатие JSON-RPC можно проверить напрямую (см. `scripts/mcp_smoke.py`):
скрипт поднимает сервер как подпроцесс, выполняет `initialize`,
`tools/list` и один вызов `sim`, и печатает результат.

## Границы ответственности

Инструменты только читают исходники (спецификацию) и запускают сборку/тесты/
симуляции. Они не пишут в репозиторий и не меняют код — правки делает агент
через обычные файловые инструменты (см. `AGENTS.md`, раздел 6).
