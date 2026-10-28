#!/usr/bin/env bash
set -euo pipefail

# Run unittest test suite with explicit discovery root

python -m unittest discover -s practices/practice_04/tests -t . -q | tee practices/practice_04/evidence/.last-check.log
