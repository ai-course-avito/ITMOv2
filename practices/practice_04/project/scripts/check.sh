#!/usr/bin/env sh
set -e
cd "$(dirname "$0")/.."
.venv/bin/python -m pytest tests/ -v
