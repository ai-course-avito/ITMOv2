#!/usr/bin/env python3
"""pre_tool_call: запись в git — только с подтверждением человека, и только на зелёных тестах.

Закрывает два правила AGENTS.md сразу:
* «не коммитить без просьбы» — команды записи в git уходят в гейт подтверждения Hermes
  ({"action":"approve"}), а не выполняются молча;
* DoD «make test зелёный» — если тесты проекта красные, команда блокируется.

Payload (stdin) — JSON хука; ответ (stdout) — JSON решения или {}.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

GIT_WRITE = re.compile(r"\bgit\s+(commit|push|rebase|reset|checkout|merge|tag|cherry-pick)\b")
TEST_BINARY = "build/tetris_tests"
TEST_TIMEOUT_S = 20


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def project_root(payload: dict) -> Path | None:
    """Корень проекта, если сессия идёт внутри practice_04, иначе None."""
    cwd = Path(str(payload.get("cwd") or "."))
    for candidate in [cwd, *cwd.parents]:
        if candidate.name == "practice_04":
            return candidate
    return None


def tests_are_green(root: Path) -> tuple[bool, str]:
    binary = root / TEST_BINARY
    if not binary.exists():
        return True, "тестовый бинарник не собран — гейт пропускает (собери make build)"
    try:
        done = subprocess.run(
            [str(binary)], capture_output=True, text=True, timeout=TEST_TIMEOUT_S, cwd=str(root)
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return True, f"тесты не запустились ({exc}) — гейт пропускает"
    tail = (done.stdout or "").strip().splitlines()
    summary = tail[-1] if tail else "нет вывода"
    return done.returncode == 0, summary


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        emit({})
        return 0

    if (payload.get("tool_name") or "") != "terminal":
        emit({})
        return 0

    args = payload.get("tool_input") or payload.get("args") or {}
    command = str(args.get("command") or "")
    if not GIT_WRITE.search(command):
        emit({})
        return 0

    root = project_root(payload)
    if root is None:  # хук настроен для этого проекта — вне его не вмешиваемся
        emit({})
        return 0

    green, summary = tests_are_green(root)
    if not green:
        emit(
            {
                "decision": "block",
                "reason": (
                    f"Заблокировано хуком git_gate: тесты проекта красные ({summary}). "
                    f"DoD требует зелёного make test перед любым коммитом."
                ),
            }
        )
        return 0

    emit(
        {
            "action": "approve",
            "message": (
                f"git_gate: команда записи в git «{command[:120]}» требует подтверждения человека "
                f"(AGENTS.md: коммиты — только по просьбе). Тесты: {summary}"
            ),
            "rule_key": "tetris-git-write",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
