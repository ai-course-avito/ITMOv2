#!/usr/bin/env bash
set -euo pipefail

# Run end-to-end checks used by the git post-commit hook
# - Starts a simple HTTP server on :8001 for pages under practices/practice_04
# - Runs Playwright-based JS checks for MathJax and Fourier demo
# - Also runs a local file:// check for the Fourier page

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Project dir is the parent of scripts/
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
WITH_SERVER="${PROJECT_DIR}/.opencode/skills/webapp-testing/scripts/with_server.py"

cd "${PROJECT_DIR}"

# Ensure BASE_URL matches the test server port used below
export BASE_URL="http://localhost:8001"

# Pick Python interpreter
if command -v python >/dev/null 2>&1; then
  PY=python
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  echo "[tests] ERROR: Neither 'python' nor 'python3' found in PATH" >&2
  exit 127
fi

echo "[tests] Running Feature A (MathJax) against $BASE_URL/fourier/"
"$PY" "${WITH_SERVER}" \
  --server "$PY -m http.server 8001" --port 8001 -- \
  node tests/js/feature_a_mathjax_test.js

echo "[tests] Running Feature B (Fourier partial sums) against $BASE_URL/fourier/"
"$PY" "${WITH_SERVER}" \
  --server "$PY -m http.server 8001" --port 8001 -- \
  node tests/js/feature_b_fourier_partial_sums_test.js

echo "[tests] Running local file check for Fourier page (no server)"
node tests/js/feature_b_local_test.js

echo "[tests] All checks completed successfully"
