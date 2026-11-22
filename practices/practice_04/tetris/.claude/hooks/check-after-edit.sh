#!/bin/sh
# Хук Claude Code (PostToolUse на Edit|Write|MultiEdit).
# Если правка задела файл проекта tetris, запускает sh scripts/check.sh этого
# проекта и возвращает результат агенту: PASS — как additionalContext,
# FAIL — через stderr с кодом 2 (Claude Code показывает его модели).
# Корень берётся из пути файла, поэтому хук работает и в git worktree.
FILE=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty')
case "$FILE" in
  */practices/practice_04/tetris/*) ROOT="${FILE%%/practices/practice_04/tetris/*}/practices/practice_04/tetris" ;;
  *) exit 0 ;;
esac
OUT=$(sh "$ROOT/scripts/check.sh" 2>&1)
CODE=$?
TAIL=$(printf '%s\n' "$OUT" | grep -vE '^(ℹ|#) (duration_ms|cancelled|skipped|todo|suites)' | tail -n 15)
STATUS=PASS; [ "$CODE" -eq 0 ] || STATUS="FAIL (exit $CODE)"
printf '%s %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${FILE#"$ROOT"/}" "$STATUS" >> "$ROOT/.claude/hooks/check-after-edit.log"
MSG=$(printf '[check-after-edit] sh scripts/check.sh → %s\n%s' "$STATUS" "$TAIL")
if [ "$CODE" -eq 0 ]; then
  jq -n --arg t "$MSG" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $t}}'
  exit 0
fi
printf '%s\n' "$MSG" >&2
exit 2
