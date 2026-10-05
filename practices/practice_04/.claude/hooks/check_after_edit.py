"""PostToolUse hook: run scripts/check.sh after Claude edits a project file.

FAIL -> exit 2 with the runner output on stderr, so Claude sees it and must react.
PASS -> exit 0 with a short note added to Claude's context.
Each run is logged (time, tool, file, exit code; no file contents) to .claude/check-hook.log.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path(__file__).resolve().parents[2])).resolve()

try:
  event = json.load(sys.stdin)
except ValueError:
  sys.exit(0)

tool = event.get("tool_name", "")
file_path = (event.get("tool_input") or {}).get("file_path", "")
if not file_path:
  sys.exit(0)

target = Path(file_path).resolve()
if project_dir not in target.parents:
  sys.exit(0)  # edit outside this project: nothing to check
if target.name == "check-hook.log":
  sys.exit(0)

result = subprocess.run(["sh", str(project_dir / "scripts" / "check.sh")],
                        capture_output=True, text=True, cwd=project_dir, timeout=50)

relative = target.relative_to(project_dir)
with open(project_dir / ".claude" / "check-hook.log", "a", encoding="utf-8") as log:
  log.write(f"{datetime.now().isoformat(timespec='seconds')}\t{tool}\t{relative}\texit={result.returncode}\n")

if result.returncode != 0:
  failures = [line for line in result.stdout.splitlines() if line.startswith("FAIL")]
  print(f"scripts/check.sh FAILED after {tool} on {relative}:", file=sys.stderr)
  print("\n".join(failures) or result.stdout[-2000:], file=sys.stderr)
  print("Fix the cause; do not weaken the runner (docs/style-guide.md, rule 4).", file=sys.stderr)
  sys.exit(2)

summary = next((line for line in result.stdout.splitlines() if "checks passed" in line), "")
print(json.dumps({
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": f"scripts/check.sh PASS after {tool} on {relative} ({summary})",
  }
}))
sys.exit(0)
