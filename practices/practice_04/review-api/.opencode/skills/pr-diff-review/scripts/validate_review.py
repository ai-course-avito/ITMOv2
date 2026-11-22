"""Валидатор ответа ревью в формате OUT-1.

Проверяет структуру (summary, risks ≤ 3, checks) и, если передан --diff,
что каждый риск указывает на файл из diff, а `evidence` дословно стоит
в строке нового файла с указанным номером. Код выхода 0 — ответ принят.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def new_file_lines(diff_text: str) -> dict[str, dict[int, str]]:
    """file -> {номер строки нового файла: содержимое} для строк контекста и добавленных."""
    result: dict[str, dict[int, str]] = {}
    current, line = None, 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            path = raw[4:].strip()
            current = path[2:] if path.startswith("b/") else path
            result.setdefault(current, {})
        elif raw.startswith("--- "):
            continue
        elif (m := HUNK.match(raw)):
            line = int(m.group(1))
        elif current and (raw.startswith("+") or raw.startswith(" ")):
            result[current][line] = raw[1:]
            line += 1
    return result


def validate(review: dict, diff_text: str | None) -> list[str]:
    errors = []
    if not isinstance(review.get("summary"), str) or not review["summary"].strip():
        errors.append("summary: нужна непустая строка")
    risks = review.get("risks")
    if not isinstance(risks, list):
        errors.append("risks: нужен массив")
        risks = []
    if len(risks) > 3:
        errors.append(f"risks: {len(risks)} элементов, максимум 3 (OUT-1)")
    checks = review.get("checks")
    if not isinstance(checks, list) or not checks or not all(isinstance(c, str) and c.strip() for c in checks):
        errors.append("checks: нужен непустой массив непустых строк")
    extra = set(review) - {"summary", "risks", "checks"}
    if extra:
        errors.append(f"лишние поля верхнего уровня: {sorted(extra)}")

    lines = new_file_lines(diff_text) if diff_text is not None else None
    for i, risk in enumerate(risks, 1):
        where = f"risks[{i}]"
        if not isinstance(risk, dict):
            errors.append(f"{where}: нужен объект")
            continue
        for key, kind in (("file", str), ("line", int), ("evidence", str), ("risk", str)):
            if not isinstance(risk.get(key), kind) or (kind is str and not risk[key].strip()):
                errors.append(f"{where}.{key}: нужно поле типа {kind.__name__}")
        if lines is None or not isinstance(risk.get("line"), int) or not isinstance(risk.get("evidence"), str):
            continue
        file_lines = lines.get(risk.get("file"))
        if file_lines is None:
            errors.append(f"{where}.file: {risk.get('file')!r} нет в diff (файлы: {sorted(lines)})")
            continue
        actual = file_lines.get(risk["line"])
        if actual is None:
            errors.append(f"{where}.line: строки {risk['line']} нет среди строк {risk['file']} в diff")
        elif risk["evidence"].strip() not in actual:
            errors.append(f"{where}.evidence: не найдено в {risk['file']}:{risk['line']} (там: {actual.strip()!r})")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("review")
    parser.add_argument("--diff")
    args = parser.parse_args()
    try:
        review = json.loads(Path(args.review).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: не удалось прочитать JSON: {exc}")
        return 1
    diff_text = Path(args.diff).read_text(encoding="utf-8") if args.diff else None
    errors = validate(review, diff_text)
    for err in errors:
        print(f"FAIL: {err}")
    if errors:
        return 1
    print(f"OK: {args.review} соответствует OUT-1, {len(review['risks'])} риск(а) подтверждены строками diff")
    return 0


if __name__ == "__main__":
    sys.exit(main())
