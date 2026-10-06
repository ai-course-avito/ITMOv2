#!/usr/bin/env python3
"""MCP-сервер продукта Tetris — прототип практики 4.

Идея: агент получает наблюдаемое поведение продукта (спека, сборка, тесты,
детерминированные симуляции, ASCII-поле), а не доступ к исходникам. Сервер —
тонкая обёртка: он не содержит правил игры, он вызывает собранный бинарник
`build/tetris` и переиспользует его JSON-контракт (docs/spec.md, раздел 6),
поэтому дублирования логики между C++ и Python нет.

Транспорт: stdio. Регистрация в Hermes:

    hermes mcp add tetris --command /home/rreflector/.hermes/hermes-agent/venv/bin/python \
        --args /home/rreflector/projects/ITMOv2/practices/practice_04/mcp_server/tetris_mcp.py

Инструменты: spec, info, sim, render, build, test (в Hermes видны как
mcp_tetris_spec, mcp_tetris_sim, ...).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from mcp.server.mcpserver import MCPServer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = PROJECT_ROOT / "build"
BINARY = BUILD_DIR / "tetris"
TESTS_BINARY = BUILD_DIR / "tetris_tests"
SPEC_PATH = PROJECT_ROOT / "docs" / "spec.md"

# Ограничения на вывод, чтобы не забивать контекст агента целиком.
MAX_OUTPUT_CHARS = 20000
BUILD_TIMEOUT_S = 300
SIM_TIMEOUT_S = 60

# Соответствие «человеческое имя раздела спецификации» → номер раздела `## N.`
SPEC_SECTIONS = {
    "product": 1,
    "rules": 2,
    "stories": 3,
    "scoring": 4,
    "cli": 5,
    "json": 6,
    "mcp": 7,
    "tests": 8,
}

server = MCPServer(
    name="tetris",
    version="0.1.0",
    instructions=(
        "Инструменты проекта Tetris: спецификация продукта, сборка, тесты, "
        "детерминированные симуляции и ASCII-рендер поля. Симуляции запускают "
        "build/tetris --headless, поэтому результат совпадает с тем, что видят тесты."
    ),
)


def _clip(text: str) -> str:
    """Обрезает длинный вывод, сохраняя начало и конец."""
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    head = text[: MAX_OUTPUT_CHARS // 2]
    tail = text[-MAX_OUTPUT_CHARS // 2 :]
    return f"{head}\n... [обрезано {len(text) - MAX_OUTPUT_CHARS} символов] ...\n{tail}"


def _missing_binary_hint() -> dict:
    return {
        "ok": False,
        "error": "бинарник build/tetris не найден",
        "hint": "вызови инструмент tetris_build (или выполни `make build` в корне проекта)",
        "binary": str(BINARY),
    }


def _run_binary(args: list[str], timeout: int = SIM_TIMEOUT_S) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(BINARY), *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@server.tool()
def info() -> dict:
    """Состояние проекта: пути, наличие сборки, версия компилятора и git-ветка."""
    details: dict = {
        "project_root": str(PROJECT_ROOT),
        "spec_path": str(SPEC_PATH),
        "binary": str(BINARY),
        "binary_exists": BINARY.exists(),
        "tests_binary_exists": TESTS_BINARY.exists(),
    }
    if BINARY.exists():
        details["binary_mtime"] = BINARY.stat().st_mtime
    for name, cmd in (("cxx", ["g++", "--version"]), ("cmake", ["cmake", "--version"])):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            details[name] = out.stdout.splitlines()[0] if out.stdout else ""
        except (OSError, subprocess.SubprocessError):
            details[name] = "недоступно"
    try:
        git = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        details["git_branch"] = git.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        details["git_branch"] = "недоступно"
    return details


@server.tool()
def spec(section: str = "all") -> dict:
    """Спецификация продукта из docs/spec.md.

    section: all | product | rules | stories | scoring | cli | json | mcp | tests
    (product — продукт и границы, rules — правила и определения, stories — user
    stories и критерии приёмки, scoring — таблицы очков, cli — CLI-контракт,
    json — схема JSON, mcp — состав MCP-инструментов, tests — план тестов).
    """
    if not SPEC_PATH.exists():
        return {"ok": False, "error": f"не найден {SPEC_PATH}"}
    text = SPEC_PATH.read_text(encoding="utf-8")
    blocks = re.split(r"^## ", text, flags=re.MULTILINE)
    if section == "all":
        return {"ok": True, "section": "all", "content": _clip(text)}
    number = SPEC_SECTIONS.get(section.strip().lower())
    if number is None:
        return {
            "ok": False,
            "error": f"неизвестный раздел '{section}'",
            "available": sorted(SPEC_SECTIONS),
        }
    for block in blocks:
        if block.startswith(f"{number}."):
            return {"ok": True, "section": section, "content": _clip("## " + block)}
    return {"ok": False, "error": f"раздел {number} не найден в спецификации"}


@server.tool()
def sim(seed: int = 42, script: str = "", max_ticks: int = 20000, include_board: bool = True) -> dict:
    """Детерминированный прогон партии без окна: возвращает JSON состояния игры.

    seed — seed генератора фигур; script — сценарий ввода токенами через пробел
    или запятую (L, R, CW, CCW, 180, D, HD, HOLD, T; суффикс-число повторяет токен:
    D3, T120, L2); max_ticks — предел тиков; include_board — вернуть ли массив
    board (board_hash присутствует всегда).
    """
    if not BINARY.exists():
        return _missing_binary_hint()
    args = ["--headless", "--seed", str(seed), "--ticks", str(max_ticks)]
    if script:
        args += ["--script", script]
    if not include_board:
        args.append("--no-board")
    args.append("--json")
    try:
        done = _run_binary(args)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"симуляция не завершилась за {SIM_TIMEOUT_S} с"}
    if done.returncode != 0:
        return {
            "ok": False,
            "error": f"тетрис вернул код {done.returncode}",
            "stderr": _clip(done.stderr.strip()),
        }
    try:
        state = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"не разобрал JSON: {exc}", "stdout": _clip(done.stdout)}
    return {"ok": True, "seed": seed, "script": script, "state": state}


@server.tool()
def render(seed: int = 42, script: str = "", max_ticks: int = 20000) -> dict:
    """ASCII-поле после прогона сценария (то же, что `tetris --ascii`)."""
    if not BINARY.exists():
        return _missing_binary_hint()
    args = ["--headless", "--seed", str(seed), "--ticks", str(max_ticks), "--ascii"]
    if script:
        args += ["--script", script]
    try:
        done = _run_binary(args)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"прогон не завершился за {SIM_TIMEOUT_S} с"}
    if done.returncode != 0:
        return {"ok": False, "error": f"тетрис вернул код {done.returncode}", "stderr": done.stderr.strip()}
    return {"ok": True, "seed": seed, "script": script, "field": done.stdout.rstrip("\n")}


@server.tool()
def build(clean: bool = False, jobs: int = 0) -> dict:
    """Собрать проект (cmake configure + build). Возвращает вывод и путь бинарника.

    clean=True удаляет каталог build перед сборкой; jobs — число потоков сборки
    (0 — все доступные ядра).
    """
    if clean and BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    jobs = jobs if jobs > 0 else (os.cpu_count() or 2)
    steps: list[str] = []
    for cmd in (
        ["cmake", "-S", ".", "-B", "build", "-DCMAKE_BUILD_TYPE=Release"],
        ["cmake", "--build", "build", "-j", str(jobs)],
    ):
        try:
            done = subprocess.run(
                cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=BUILD_TIMEOUT_S
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"шаг сборки превысил {BUILD_TIMEOUT_S} с", "command": " ".join(cmd)}
        steps.append(f"$ {' '.join(cmd)}\n{done.stdout}{done.stderr}")
        if done.returncode != 0:
            return {
                "ok": False,
                "command": " ".join(cmd),
                "returncode": done.returncode,
                "output": _clip("\n".join(steps)),
                "binary_exists": BINARY.exists(),
            }
    return {
        "ok": True,
        "output": _clip("\n".join(steps)),
        "binary": str(BINARY),
        "binary_exists": BINARY.exists(),
    }


@server.tool()
def test(filter: str = "") -> dict:
    """Запустить ctest в build/ и вернуть разбор итога.

    filter — регулярное выражение ctest -R (пустая строка — все тесты).
    """
    if not BUILD_DIR.exists():
        return {"ok": False, "error": "нет каталога build/", "hint": "сначала вызови tetris_build"}
    cmd = ["ctest", "--test-dir", "build", "--output-on-failure"]
    if filter:
        cmd += ["-R", filter]
    try:
        done = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=BUILD_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"тесты не завершились за {BUILD_TIMEOUT_S} с"}
    summary = ""
    passed = failed = total = None
    for line in done.stdout.splitlines():
        if "tests passed" in line or "tests failed" in line:
            summary = line.strip()
            match = re.search(
                r"(\d+)% tests passed, (\d+) tests failed out of (\d+)", line
            )
            if match:
                failed = int(match.group(2))
                total = int(match.group(3))
                passed = total - failed
        elif re.match(r"^\d+/\d+ Test\s", line.strip()):
            summary = summary or line.strip()
    return {
        "ok": done.returncode == 0,
        "returncode": done.returncode,
        "passed": passed,
        "failed": failed,
        "total": total,
        "summary": summary,
        "output": _clip(done.stdout + done.stderr),
    }


if __name__ == "__main__":
    server.run()
