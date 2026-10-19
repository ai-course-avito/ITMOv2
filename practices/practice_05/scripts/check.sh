#!/usr/bin/env bash
set -euo pipefail

# OpenSpec validation for practice_05
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
project_dir="$(cd "$script_dir/.." && pwd)"

cd "$project_dir"

echo "Running OpenSpec validation (practice_05)..." >&2
npm exec -y @fission-ai/openspec@latest -- validate --all
echo "OpenSpec validation OK" >&2
