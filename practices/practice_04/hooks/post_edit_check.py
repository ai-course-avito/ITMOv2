#!/usr/bin/env python3
"""post_tool_call: после правки кода проекта прогоняет сборку и тесты автоматически.

Закрывает правило `AGENTS.md` («задача не готова без зелёного `make test`»): агент не
обязан помнить, что после правки нужно проверять, — проверка запускается хуком.

Как результат попадает к агенту: событие `post_tool_call` наблюдающее, его stdout
Hermes игнорирует (см. docs/user-guide/features/hooks.md, «Shipped plugin-hook
catalog»). Поэтому хук пишет итог в `build/last_check.json`, а `project_context.py`
(событие `pre_llm_call`) читает файл и подкладывает строку в следующий ход агента.

Что делает:
* молчит, если сессия идёт вне `practice_04` или правка не влияет на сборку (`.md`, `.txt`);
* собирает проект инкрементально (`cmake --build build -j`) и прогоняет `build/tetris_tests`;
* при падении сборки сохраняет хвост вывода компилятора — агент видит ошибку текстом;
* всегда печатает `{}` и завершается кодом 0: ничего не блокирует.

Payload (stdin) — JSON хука. Ответ (stdout) — `{}` (событие наблюдающее).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

EDIT_TOOLS = {"write_file", "patch", "multi_edit", "str_replace", "edit_file"}
BUILD_SUFFIXES = {".cpp", ".cc", ".cxx", ".hpp", ".h"}
BUILD_FILENAMES = {"CMakeLists.txt", "Makefile", "CMakeCache.txt"}
STATE_FILE = "build/last_check.json"
BUILD_TIMEOUT_S = 180
TEST_TIMEOUT_S = 30
STATE_TTL_S = 1800


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def project_root(payload: dict) -> Path | None:
    """Корень проекта, если сессия идёт внутри practice_04, иначе None."""
    cwd = Path(str(payload.get("cwd") or "."))
    for candidate in [cwd, *cwd.parents]:
        if candidate.name == "practice_04":
            return candidate
    return None


def edited_path(payload: dict, root: Path) -> Path | None:
    """Путь правки, если он внутри проекта и влияет на сборку."""
    args = payload.get("tool_input") or payload.get("args") or {}
    raw = args.get("path") or args.get("file_path") or args.get("file") or ""
    if not raw:
        return None
    candidate = Path(str(raw))
    if not candidate.is_absolute():
        candidate = Path(str(payload.get("cwd") or ".")) / candidate
    try:
        candidate.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    if candidate.suffix in BUILD_SUFFIXES or candidate.name in BUILD_FILENAMES:
        return candidate
    return None


def run(cmd: list[str], root: Path, timeout: int) -> tuple[bool, str, str]:
    try:
        done = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=str(root)
        )
    except subprocess.TimeoutExpired:
        return False, f"таймаут {timeout} с", ""
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"не запустилось: {exc}", ""
    output = ((done.stdout or "") + (done.stderr or "")).strip()
    return done.returncode == 0, output, _tail(output)


def _tail(text: str, lines: int = 12, limit: int = 1500) -> str:
    tail = "\n".join(text.strip().splitlines()[-lines:])
    return tail[-limit:]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        emit({})
        return 0

    if (payload.get("tool_name") or "") not in EDIT_TOOLS:
        emit({})
        return 0

    root = project_root(payload)
    if root is None:
        emit({})
        return 0

    target = edited_path(payload, root)
    if target is None:
        emit({})  # правка не про сборку (документация, конфиги агента и т.п.)
        return 0

    started = time.perf_counter()
    build_dir = root / "build"

    if not (build_dir / "CMakeCache.txt").exists():
        state = {
            "path": str(target.relative_to(root)),
            "build_ok": None,
            "tests_ok": None,
            "summary": "сборка не сконфигурирована — выполни `make build`",
            "seconds": round(time.perf_counter() - started, 2),
            "checked_at": time.time(),
        }
    else:
        build_ok, _, build_tail = run(
            ["cmake", "--build", "build", "-j", str(max(1, os.cpu_count() or 2))],
            root,
            BUILD_TIMEOUT_S,
        )
        if not build_ok:
            state = {
                "path": str(target.relative_to(root)),
                "build_ok": False,
                "tests_ok": None,
                "summary": "сборка упала, тесты не запускались",
                "detail": build_tail,
                "seconds": round(time.perf_counter() - started, 2),
                "checked_at": time.time(),
            }
        else:
            tests_ok, tests_output, _ = run(
                [str(build_dir / "tetris_tests")], root, TEST_TIMEOUT_S
            )
            lines = tests_output.strip().splitlines()
            state = {
                "path": str(target.relative_to(root)),
                "build_ok": True,
                "tests_ok": tests_ok,
                "summary": lines[-1] if lines else "нет вывода тестов",
                "seconds": round(time.perf_counter() - started, 2),
                "checked_at": time.time(),
            }
            if not tests_ok:
                state["detail"] = _tail(tests_output)

    try:
        (root / STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
        (root / STATE_FILE).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass

    emit({})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
