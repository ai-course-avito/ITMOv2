#!/usr/bin/env bash
set -euo pipefail

# Simple JSON-RPC over stdio driver to call our MCP tool using jq for formatting.
SCRIPT_DIR="$(dirname "$0")"
SERVER="$SCRIPT_DIR/luckyspin-mcp.js"

call() {
  local METHOD="$1"; shift
  local PARAMS="$1"; shift || true
  node "$SERVER" <<EOF
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
{"jsonrpc":"2.0","id":3,"method":"$METHOD","params":$PARAMS}
EOF
}

echo "--- Successful call (eligible=false same day) ---"
call tools/call '{"name":"luckyspin.bonusEligibility","arguments":{"lastClaimedAt":"2026-10-07T01:00:00Z","now":"2026-10-07T12:00:00Z"}}'

echo "\n--- Successful call (eligible=true next day) ---"
call tools/call '{"name":"luckyspin.bonusEligibility","arguments":{"lastClaimedAt":"2026-10-06T23:30:00Z","now":"2026-10-07T00:10:00Z"}}'

echo "\n--- Error: invalid lastClaimedAt ---"
call tools/call '{"name":"luckyspin.bonusEligibility","arguments":{"lastClaimedAt":"not-a-date"}}'
