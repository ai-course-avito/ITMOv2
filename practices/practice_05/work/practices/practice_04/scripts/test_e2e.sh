#!/usr/bin/env bash
set -euo pipefail

# Run end-to-end checks used by the git post-commit hook
# - Starts a simple HTTP server on :1254 for pages under practices/practice_04
# - Runs Playwright-based JS checks for MathJax and Fourier demo
# - Also runs a local file:// check for the Fourier page

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
WITH_SERVER="${PROJECT_DIR}/.opencode/skills/webapp-testing/scripts/with_server.py"

# Default base URL for tests; can be overridden by env
: "${BASE_URL:=http://localhost:1254}"

cd "${PROJECT_DIR}"

echo "[tests] Running Feature A (MathJax) against ${BASE_URL}/fourier/"
BASE_URL="${BASE_URL}" python3 "${WITH_SERVER}" \
  --server "python3 -m http.server 1254" --port 1254 -- \
  node tests/js/feature_a_mathjax_test.js

echo "[tests] Running Feature B (Fourier partial sums) against ${BASE_URL}/fourier/"
BASE_URL="${BASE_URL}" python3 "${WITH_SERVER}" \
  --server "python3 -m http.server 1254" --port 1254 -- \
  node tests/js/feature_b_fourier_partial_sums_test.js

echo "[tests] Running local file check for Fourier page (no server)"
node tests/js/feature_b_local_test.js

echo "[tests] All checks completed successfully"
