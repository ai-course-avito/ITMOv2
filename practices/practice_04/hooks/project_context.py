#!/usr/bin/env python3
"""pre_llm_call: в начало каждого хода подкладывает фактическое состояние проекта.

Зачем: агент не должен спрашивать «а тесты-то зелёные?» и не должен помнить про замороженный
интерфейс по памяти — состояние подставляется в контекст и обновляется само. Хук молчит,
если сессия идёт вне practice_04, и всегда остаётся дешёвым: тестовый бинарник прогоняется
за доли секунды, при отсутствии сборки статус просто помечается как «не собран».

Payload (stdin) — JSON хука; ответ (stdout) — {"context": "..."} или {}.
"""

import json
import subprocess
import sys
from pathlib import Path

TEST_BINARY = "build/tetris_tests"
BINARY = "build/tetris"
TEST_TIMEOUT_S = 20


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def project_root(payload: dict) -> Path | None:
    cwd = Path(str(payload.get("cwd") or "."))
    for candidate in [cwd, *cwd.parents]:
        if candidate.name == "practice_04":
            return candidate
    return None


def git(root: Path, *args: str) -> str:
    try:
        done = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=10, cwd=str(root)
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (done.stdout or "").strip()


def tests_status(root: Path) -> str:
    binary = root / TEST_BINARY
    if not binary.exists():
        return "не собраны (make build)"
    try:
        done = subprocess.run(
            [str(binary)], capture_output=True, text=True, timeout=TEST_TIMEOUT_S, cwd=str(root)
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"не запустились: {exc}"
    lines = (done.stdout or "").strip().splitlines()
    return lines[-1] if lines else "нет вывода"


def last_edit_check(root: Path) -> str:
    """Итог автопроверки после последней правки (пишет хук post_edit_check.py)."""
    import json
    import time

    state_file = root / "build" / "last_check.json"
    if not state_file.exists():
        return ""
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    age = time.time() - float(state.get("checked_at") or 0)
    if age > 1800:  # старше получаса — уже не «после правки», не путаем агента
        return ""
    build = "ок" if state.get("build_ok") else ("упала" if state.get("build_ok") is False else "не собрана")
    tests = "ок" if state.get("tests_ok") else ("красные" if state.get("tests_ok") is False else "не запускались")
    detail = state.get("detail")
    text = (
        f" Последняя автопроверка после правки {state.get('path')}: сборка {build}, "
        f"тесты {tests} ({state.get('summary')}, {state.get('seconds')} с)."
    )
    if detail:
        text += f" Вывод:\n{detail}"
    return text



def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        emit({})
        return 0

    root = project_root(payload)
    if root is None:
        emit({})
        return 0

    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD") or "?"
    dirty = len([line for line in git(root, "status", "--porcelain").splitlines() if line.strip()])
    binary_state = "собран" if (root / BINARY).exists() else "не собран"

    context = (
        "[hook project_context] practice_04 (Tetris): "
        f"ветка {branch}; незакоммиченных файлов — {dirty}; сборка {binary_state}; "
        f"тесты: {tests_status(root)}."
        f"{last_edit_check(root)} "
        "Помни: правки include/tetris/** блокируются хуком frozen_headers, "
        "команды записи в git уходят на подтверждение человеку (хук git_gate). "
        "Проверять поведение — через MCP (mcp__tetris__sim / render / test), а не по памяти."
    )
    emit({"context": context})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
