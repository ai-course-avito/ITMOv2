#!/bin/sh
# Единый runner проекта: тесты API и MCP-инструмента.
# Вызывается вручную, из хука OpenCode после каждой правки и из AGENTS.md.
cd "$(dirname "$0")/.." || exit 2
PY=".venv/bin/python"
[ -x "$PY" ] || { echo "check: нет .venv — выполните make install"; exit 2; }
"$PY" -m pytest -q -p no:cacheprovider tests
