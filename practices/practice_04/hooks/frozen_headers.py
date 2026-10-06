#!/usr/bin/env python3
"""pre_tool_call: замороженный интерфейс нельзя править молча (файлы и шелл).

AGENTS.md (раздел 5) объявляет `include/tetris/**` интерфейсом, который меняет только
архитектор. Раньше это было обещание в документе — теперь это гейт:

* инструменты правки файлов (write_file/patch) проверяются по пути;
* терминал проверяется по признакам записи в этот путь: `>`, `>>`, `tee`, `sed -i`,
  `cp`, `mv`, `rm`, `truncate`, `dd`, `install`, `patch`. Чтение (`cat`, `grep`, `ls`
  по тому же пути) не блокируется — иначе гейт мешал бы исследованиям.

Разрешить осознанно:  HERMES_ALLOW_FROZEN_HEADERS=1 hermes chat
Payload (stdin)  — см. docs/user-guide/features/hooks.md, «JSON wire protocol».
Ответ (stdout)   — {"decision":"block","reason":"..."} либо {} для no-op.
"""

import json
import os
import re
import sys
from pathlib import Path

FROZEN_MARKER = "practice_04/include/tetris/"
ALLOW_ENV = "HERMES_ALLOW_FROZEN_HEADERS"
EDIT_TOOLS = {"write_file", "patch", "multi_edit", "str_replace", "edit_file"}

# Признаки записи в шелле. Список намеренно узкий: только то, что реально меняет файл.
TERMINAL_WRITE = re.compile(
    r"(>>?\s*\S*include/tetris/|\btee\b[^|]*include/tetris/|\bsed\b[^|]*-i[^|]*include/tetris/"
    r"|\b(cp|mv|rm|truncate|dd|install|patch)\b[^|]*include/tetris/)"
)


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def block_reason(where: str) -> str:
    return (
        f"Заблокировано хуком frozen_headers: {where} — часть замороженного интерфейса "
        f"(AGENTS.md, раздел 5: «заголовки — интерфейс»). Правку интерфейса согласует человек; "
        f"чтобы разрешить её осознанно, запусти сессию с {ALLOW_ENV}=1 и обнови доки "
        f"(docs/spec.md, AGENTS.md) вместе с заголовком."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        emit({})  # не наша забота: пусть решает обычная логика Hermes
        return 0

    if os.environ.get(ALLOW_ENV) == "1":
        emit({})
        return 0

    tool = payload.get("tool_name") or ""
    args = payload.get("tool_input") or payload.get("args") or {}

    if tool in EDIT_TOOLS:
        raw_path = args.get("path") or args.get("file_path") or args.get("file") or ""
        if not raw_path:
            emit({})
            return 0
        cwd = payload.get("cwd") or os.getcwd()
        candidate = Path(str(raw_path))
        if not candidate.is_absolute():
            candidate = Path(cwd) / candidate
        if FROZEN_MARKER in str(candidate):
            emit({"decision": "block", "reason": block_reason(raw_path)})
            return 0
        emit({})
        return 0

    if tool == "terminal":
        command = str(args.get("command") or "")
        if TERMINAL_WRITE.search(command):
            emit({"decision": "block", "reason": block_reason(f"команда «{command[:140]}»")})
            return 0
        emit({})
        return 0

    emit({})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
