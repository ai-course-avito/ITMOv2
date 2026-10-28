#!/usr/bin/env bash
# Run the backend locally without Docker.
# Usage: ./scripts/dev.sh [--seed]
set -euo pipefail
cd "$(dirname "$0")/.."

uv run python -m scripts.check_db
uv run alembic upgrade head
if [[ "${1:-}" == "--seed" ]]; then
  uv run python -m scripts.seed
fi
exec uv run uvicorn app.main:app --reload --port 8000
