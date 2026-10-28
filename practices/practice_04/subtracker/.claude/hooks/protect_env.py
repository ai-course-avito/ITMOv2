#!/usr/bin/env python3
"""PreToolUse hook: block Write/Edit/Bash that modify secret env files (.env, .env.local, ...).

Reads the hook payload (JSON) from stdin. Exit code 2 blocks the tool call and
sends stderr back to the agent; exit code 0 lets it through.

The Bash check is a best-effort heuristic: it blocks commands that mention a
secrets file AND contain a write-like operation. Reading (cat, grep) is allowed.
"""

import json
import os
import re
import sys

ALLOWED_SUFFIXES = {"example", "sample", "template"}

ENV_TOKEN = re.compile(r"(?:^|[\s/\"'=<>|;&(])(\.env(?:\.[A-Za-z0-9_-]+)?)(?=$|[\s\"';|&<>)])")
SAFE_REDIRECTS = re.compile(r"\d*>&\d+|\d*>>?\s*/dev/null")
WRITE_LIKE = re.compile(
    r"(>|\btee\b|\bsed\b[^|;&]*\s-i|\bperl\b[^|;&]*\s-i"
    r"|\b(?:mv|cp|rm|truncate|dd|install|ln)\b|\b(?:python3?|node|ruby|perl)\b)"
)


def is_protected(file_path: str) -> bool:
    name = os.path.basename(file_path)
    if name == ".env":
        return True
    if name.startswith(".env."):
        return name.rsplit(".", 1)[-1] not in ALLOWED_SUFFIXES
    return False


def protected_target_in_command(command: str):
    if not any(is_protected(m) for m in ENV_TOKEN.findall(command)):
        return None
    if not WRITE_LIKE.search(SAFE_REDIRECTS.sub(" ", command)):
        return None
    return next(m for m in ENV_TOKEN.findall(command) if is_protected(m))


def block(target: str) -> int:
    print(
        f"BLOCKED: {target} is a secrets file. AGENTS.md forbids editing or "
        "committing .env; put variable names in .env.example and ask the user "
        "to set real values themselves.",
        file=sys.stderr,
    )
    return 2


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool_input = payload.get("tool_input") or {}

    file_path = tool_input.get("file_path")
    if file_path and is_protected(file_path):
        return block(file_path)

    command = tool_input.get("command")
    if isinstance(command, str):
        target = protected_target_in_command(command)
        if target:
            return block(target)

    return 0


if __name__ == "__main__":
    sys.exit(main())
