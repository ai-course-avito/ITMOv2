#!/bin/sh
# PostToolUse hook (Edit|Write|MultiEdit): после правки app/, tests/ или mcp_server/ запускает scripts/check.sh
# и возвращает результат агенту по контракту hooks Claude Code:
#   CHECK FAIL -> {"decision": "block", "reason": "<хвост pytest>"}
#   CHECK PASS -> {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "check.sh: CHECK PASS"}}
# Запуск: sh "$CLAUDE_PROJECT_DIR/.claude/hooks/check-after-edit.sh"  (JSON события приходит на stdin)

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
LOG="$ROOT/.claude/hooks/check-after-edit.log"

if [ -n "$PYTHON" ]; then
    PY="$PYTHON"
elif [ -x "$ROOT/.venv/Scripts/python.exe" ]; then
    PY="$ROOT/.venv/Scripts/python.exe"
elif [ -x "$ROOT/.venv/bin/python" ]; then
    PY="$ROOT/.venv/bin/python"
else
    PY="python"
fi
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

INPUT=$(cat)

# Git Bash на Windows: /c/... -> C:/..., чтобы Windows-python правильно сравнил пути
ROOT_PY="$ROOT"
if command -v cygpath >/dev/null 2>&1; then
    ROOT_PY=$(cygpath -m "$ROOT")
fi

# Путь правленого файла, относительно корня проекта, с прямыми слэшами ("" если вне проекта)
REL=$(printf '%s' "$INPUT" | ROOT="$ROOT_PY" "$PY" -c '
import json, os, sys
try:
    data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
    path = (data.get("tool_input") or {}).get("file_path") or ""
    if path:
        root = os.path.normcase(os.path.abspath(os.environ["ROOT"]))
        full = os.path.normcase(os.path.abspath(path))
        rel = os.path.relpath(full, root).replace("\\", "/")
        print("" if rel.startswith("..") else rel)
except Exception:
    pass
')

case "$REL" in
    app/*|tests/*|mcp_server/*) ;;
    *) exit 0 ;;
esac

OUT=$(cd "$ROOT" && sh scripts/check.sh 2>&1)
TS=$(date '+%Y-%m-%d %H:%M:%S')

if printf '%s\n' "$OUT" | tail -n 1 | grep -q '^CHECK PASS'; then
    echo "$TS $REL CHECK PASS" >> "$LOG"
    printf '%s' "check.sh: CHECK PASS" | "$PY" -c '
import json, sys
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": sys.stdin.read()}}))'
else
    echo "$TS $REL CHECK FAIL" >> "$LOG"
    printf '%s\n' "$OUT" | tail -n 25 | REL="$REL" "$PY" -c '
import json, os, sys
tail = sys.stdin.read()
reason = "check.sh: CHECK FAIL после правки " + os.environ["REL"] + ". Хвост вывода pytest:\n" + tail
print(json.dumps({"decision": "block", "reason": reason}))'
fi
exit 0
