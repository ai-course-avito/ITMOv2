#!/bin/sh
# Project check runner: static page contract + whitespace + JS syntax.
# Usage: sh scripts/check.sh [project_dir]   (default: this project)
# Exit code 0 = all checks pass, 1 = at least one failure.

script_dir=$(cd "$(dirname "$0")" && pwd)
project_dir=$(cd "${1:-$script_dir/..}" && pwd)
status=0

echo "== page contract ($project_dir)"
python3 "$script_dir/check_page.py" "$project_dir" || status=1

echo
echo "== whitespace (git diff --check)"
if git -C "$project_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if git -C "$project_dir" diff --check -- . && git -C "$project_dir" diff --cached --check -- .; then
    echo "PASS  no whitespace errors in changes"
  else
    echo "FAIL  whitespace errors in changes"
    status=1
  fi
else
  echo "SKIP  not a git work tree"
fi

if [ -f "$project_dir/mcp/olympiad_pricing/server.py" ]; then
  echo
  echo "== olympiad-pricing MCP server"
  if mcp_output=$(python3 "$script_dir/test_mcp_pricing.py" "$project_dir" 2>&1); then
    echo "$mcp_output" | tail -1
    echo "PASS  MCP self-test"
  else
    echo "$mcp_output" | grep -E '^FAIL|Error|checks passed'
    echo "FAIL  MCP self-test"
    status=1
  fi
fi

if [ -f "$project_dir/script.js" ]; then
  echo
  echo "== script.js syntax"
  if command -v node >/dev/null 2>&1; then
    if node --check "$project_dir/script.js"; then
      echo "PASS  script.js parses"
    else
      echo "FAIL  script.js has a syntax error"
      status=1
    fi
  else
    echo "SKIP  node not installed"
  fi
fi

echo
if [ "$status" -eq 0 ]; then echo "RESULT: PASS"; else echo "RESULT: FAIL"; fi
exit "$status"
