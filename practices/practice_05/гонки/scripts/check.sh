#!/usr/bin/env bash
# Детерминированный runner проекта «Гонки».
# Запускается вручную (`bash scripts/check.sh`) и автоматически — hook'ом
# агента после каждой правки файлов бэкенда (.claude/settings.json, PostToolUse).
#
# Никакой LLM-оценки — только статический lint, формат и тесты. Одинаковый
# код всегда даёт одинаковый результат (PASS/FAIL).

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"

cd "$ROOT/backend" || exit 1

if [ -d ".venv/bin" ]; then
  export PATH="$ROOT/backend/.venv/bin:$PATH"
fi

fail=0

echo "→ ruff check..."
if command -v ruff >/dev/null 2>&1; then
  ruff check . || fail=1
  echo "→ ruff format --check..."
  ruff format --check . || fail=1
else
  echo "ruff не найден в PATH, пропускаем lint"
fi

echo "→ pytest..."
if [ -f ".venv/bin/pytest" ]; then
  .venv/bin/pytest tests/ -q || fail=1
else
  python3 -m pytest tests/ -q || fail=1
fi

if [ "$fail" -ne 0 ]; then
  echo "FAIL: проверка не прошла (см. вывод выше)"
  exit 1
fi

echo "PASS: ruff + тесты зелёные"
exit 0
