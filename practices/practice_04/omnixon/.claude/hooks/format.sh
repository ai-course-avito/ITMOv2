#!/bin/sh
# PostToolUse hook: format the file that Edit/Write just changed.
# TypeScript/CSS of the panel: its Prettier. Python (backend, library, mcp): ruff format via uvx.
f=$(jq -r '.tool_input.file_path // empty')
fe="$CLAUDE_PROJECT_DIR/omnixon-frontend"
case "$f" in
  "$fe"/src/*.ts|"$fe"/src/*.tsx|"$fe"/src/*.css|"$fe"/e2e/*.ts)
    cd "$fe" && npx --no-install prettier --write --log-level warn "$f" >&2 || exit 2
    ;;
  "$CLAUDE_PROJECT_DIR"/omnixon-backend/*.py|"$CLAUDE_PROJECT_DIR"/omnixon-library/*.py|"$CLAUDE_PROJECT_DIR"/omnixon-mcp/*.py)
    case "$f" in */.venv/*|*/node_modules/*) exit 0 ;; esac
    uvx --quiet ruff format --quiet "$f" >&2 || exit 2
    ;;
  *) exit 0 ;;
esac
