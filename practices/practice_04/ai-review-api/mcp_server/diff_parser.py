"""Разбор unified diff без внешних зависимостей (и без зависимости от mcp).

Главная функция: inspect_diff(diff, max_bytes) -> dict.
При плохом входе бросает DiffInspectError (подкласс ValueError) с понятным текстом.
"""

from __future__ import annotations

import re
from typing import Any

DEFAULT_MAX_BYTES = 100000

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class DiffInspectError(ValueError):
    """Входные данные не годятся для разбора."""


def _clean_path(raw: str) -> str | None:
    """Путь из строки ---/+++ : без таймстемпа, кавычек и префикса a/ b/. None = /dev/null."""
    p = raw.split("\t", 1)[0].strip()
    if len(p) >= 2 and p[0] == '"' and p[-1] == '"':
        p = p[1:-1]
    if p == "/dev/null":
        return None
    if p.startswith(("a/", "b/")):
        p = p[2:]
    return p


def _paths_from_git_header(rest: str) -> tuple[str, str]:
    """'a/x b/y' -> ('x', 'y'). Для путей с пробелами ищем одинаковые половины."""
    if rest.startswith('"') and '" "' in rest:
        left, right = rest.split('" "', 1)
        return _clean_path(left + '"') or "", _clean_path('"' + right) or ""
    if rest.startswith("a/") and " b/" in rest:
        for i in range(len(rest)):
            if rest.startswith(" b/", i):
                left, right = rest[2:i], rest[i + 3 :]
                if left == right:
                    return left, right
        i = rest.rindex(" b/")
        return rest[2:i], rest[i + 3 :]
    parts = rest.split(" ", 1)
    if len(parts) == 2:
        return _clean_path(parts[0]) or "", _clean_path(parts[1]) or ""
    return rest, rest


class _File:
    def __init__(self, old: str | None, new: str | None) -> None:
        self.old = old
        self.new = new
        self.old_null = False  # ---  /dev/null  (файл создан)
        self.new_null = False  # +++  /dev/null  (файл удален)
        self.renamed = False
        self.added_flag = False
        self.deleted_flag = False
        self.binary = False
        self.minus_seen = False
        self.hunks = 0
        self.added = 0
        self.removed = 0

    def to_dict(self) -> dict[str, Any]:
        if self.deleted_flag or self.new_null:
            status = "deleted"
        elif self.added_flag or self.old_null:
            status = "added"
        elif self.renamed:
            status = "renamed"
        else:
            status = "modified"
        path = self.old if status == "deleted" else (self.new or self.old)
        d: dict[str, Any] = {
            "path": path or "(unknown)",
            "status": status,
            "added": self.added,
            "removed": self.removed,
            "binary": self.binary,
        }
        if status == "renamed":
            d["old_path"] = self.old
        return d


def parse_unified_diff(diff: str) -> list[dict[str, Any]]:
    """Возвращает список файлов. Бросает DiffInspectError, если это не похоже на diff."""
    lines = diff.split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    files: list[_File] = []
    cur: _File | None = None
    old_left = new_left = 0  # сколько строк текущего ханка еще ожидаем

    for raw in lines:
        line = raw[:-1] if raw.endswith("\r") else raw

        if old_left > 0 or new_left > 0:
            if line.startswith("diff --git "):
                old_left = new_left = 0  # обрезанный ханк: дальше читаем как заголовок
            elif cur is not None:
                if line.startswith("+"):
                    cur.added += 1
                    new_left -= 1
                elif line.startswith("-"):
                    cur.removed += 1
                    old_left -= 1
                elif line.startswith("\\"):
                    pass  # "\ No newline at end of file"
                else:  # контекст (пустая строка тоже контекст)
                    old_left -= 1
                    new_left -= 1
                old_left, new_left = max(old_left, 0), max(new_left, 0)
                continue

        if line.startswith("diff --git "):
            old, new = _paths_from_git_header(line[len("diff --git ") :])
            cur = _File(old, new)
            files.append(cur)
        elif line.startswith("--- ") and (cur is None or cur.minus_seen or cur.hunks):
            # diff без заголовка git: новый файл начинается с ---
            cur = _File(None, None)
            files.append(cur)
            cur.minus_seen = True
            p = _clean_path(line[4:])
            cur.old, cur.old_null = p, p is None
        elif line.startswith("--- ") and cur is not None:
            cur.minus_seen = True
            p = _clean_path(line[4:])
            cur.old_null = p is None
            if p is not None:
                cur.old = p
        elif line.startswith("+++ ") and cur is not None and not cur.hunks:
            p = _clean_path(line[4:])
            cur.new_null = p is None
            if p is not None:
                cur.new = p
        elif line.startswith("@@") and cur is not None:
            m = _HUNK_RE.match(line)
            if m:
                cur.hunks += 1
                old_left = int(m.group(2)) if m.group(2) is not None else 1
                new_left = int(m.group(4)) if m.group(4) is not None else 1
        elif cur is not None:
            if line.startswith("new file mode"):
                cur.added_flag = True
            elif line.startswith("deleted file mode"):
                cur.deleted_flag = True
            elif line.startswith("rename from "):
                cur.renamed = True
                cur.old = _clean_path(line[len("rename from ") :])
            elif line.startswith("rename to "):
                cur.renamed = True
                cur.new = _clean_path(line[len("rename to ") :])
            elif line.startswith("Binary files ") or line.startswith("GIT binary patch"):
                cur.binary = True
                if line.startswith("Binary files ") and " and " in line and line.endswith(" differ"):
                    # "Binary files a/x and /dev/null differ"
                    body = line[len("Binary files ") : -len(" differ")]
                    left, right = body.split(" and ", 1)
                    if _clean_path(left) is None:
                        cur.old_null = True
                    if _clean_path(right) is None:
                        cur.new_null = True

    if not files:
        raise DiffInspectError(
            "Не нашел ни одного признака unified diff: нет строк 'diff --git', '--- ' / '+++ ' "
            "и заголовков ханков '@@ -a,b +c,d @@'. Передай вывод 'git diff' как есть."
        )
    return [f.to_dict() for f in files]


def inspect_diff(diff: Any, max_bytes: Any = DEFAULT_MAX_BYTES) -> dict[str, Any]:
    """Проверяет вход и возвращает сводку по diff."""
    if not isinstance(diff, str):
        raise DiffInspectError(f"diff должен быть строкой, получено: {type(diff).__name__}.")
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int):
        raise DiffInspectError(f"max_bytes должен быть целым числом, получено: {type(max_bytes).__name__}.")
    if max_bytes <= 0:
        raise DiffInspectError(f"max_bytes должен быть больше 0, получено: {max_bytes}.")
    if diff == "":
        raise DiffInspectError("diff пустой (пустая строка): нечего разбирать.")
    if diff.strip() == "":
        raise DiffInspectError("diff состоит только из пробелов/переводов строк: нечего разбирать.")

    files = parse_unified_diff(diff)
    size = len(diff.encode("utf-8", errors="replace"))
    too_large = size > max_bytes
    return {
        "files": files,
        "total_files": len(files),
        "total_added": sum(f["added"] for f in files),
        "total_removed": sum(f["removed"] for f in files),
        "size_bytes": size,
        "max_bytes": max_bytes,
        "too_large": too_large,
        # пустой и невалидный diff сюда не доходят: для них бросается ошибка
        "would_be_accepted": not too_large,
    }
