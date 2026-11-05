#!/usr/bin/env bash
set -euo pipefail

LOG=practices/practice_04/evidence/03-skill-run.log
bash practices/practice_04/scripts/check.sh | tee "$LOG"

exit 0
