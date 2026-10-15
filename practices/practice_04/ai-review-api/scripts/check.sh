#!/bin/sh
# Единственный runner проверки: python -m pytest -q из корня проекта.
# Python: $PYTHON, иначе .venv, иначе python из PATH.
cd "$(dirname "$0")/.." || { echo "CHECK FAIL"; exit 1; }

if [ -n "$PYTHON" ]; then
    PY="$PYTHON"
elif [ -x ".venv/Scripts/python.exe" ]; then
    PY=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
else
    PY="python"
fi

if "$PY" -m pytest -q; then
    echo "CHECK PASS"
    exit 0
else
    echo "CHECK FAIL"
    exit 1
fi
