#!/usr/bin/env python3
"""Проверка структуры RCTF-промпта. Stdlib, без зависимостей.

Использование:
    python3 check_prompt.py prompt.md
    cat prompt.md | python3 check_prompt.py -

Код возврата: 0 — ошибок нет, 1 — есть ошибки, 2 — файл не прочитан.
Проверяется форма, а не смысл: скрипт не знает, верные ли факты в Context.
"""

import re
import sys

BLOCKS = {
    "Role": ("role", "роль"),
    "Context": ("context", "контекст"),
    "Task": ("task", "задача", "задание"),
    "Format": ("format", "формат"),
}
REQUIRED = ("Context", "Task", "Format")

HEADER = re.compile(
    r"^\s*(?:[#>*\-\s]*)(?:\*\*)?\s*([A-Za-zА-Яа-яЁё]+)\s*(?:\*\*)?\s*[:：]\s*(.*)$"
)

VAGUE = [
    "качественн", "подробно", "детально", "красив", "максимально",
    "как можно лучше", "профессиональн", "идеальн", "хорошо и",
    "best effort", "high quality", "in detail", "as good as",
]
PUFFERY = [
    "гениальн", "мирового уровня", "лучший", "лучшая", "выдающийся",
    "легендарн", "непревзойдённ", "непревзойденн", "world-class", "10x",
    "topmost", "the best",
]
EXPERIENCE = re.compile(r"\b\d+[-\s]*(?:лет|год|years)", re.I)
CONCRETE_FORMAT = [
    "таблиц", "список", "пункт", "строк", "слов", "абзац", "шаг", "колон",
    "json", "csv", "markdown", "yaml", "файл", "схем", "раздел", "этап",
    "bullet", "table", "list", "words", "steps", "columns",
]
PLACEHOLDERS = ["todo", "вставь сюда", "xxx", "<...>", "тут текст", "lorem ipsum"]

MULTI_ACTION = re.compile(r"[,;]\s*(?:а\s+)?(?:также|ещё|еще|и\s+(?:затем|потом|после))")
INDIRECT_START = ("мне нужно", "я хочу", "хотелось бы", "можешь", "не мог бы", "надо бы")


def parse_blocks(text):
    """Вернуть {имя блока: содержимое} по заголовкам вида 'Role:' / '## Context:'."""
    blocks, current, buffer = {}, None, []
    for line in text.splitlines():
        match = HEADER.match(line)
        name = None
        if match:
            word = match.group(1).strip().lower()
            for canonical, aliases in BLOCKS.items():
                if word in aliases:
                    name = canonical
                    break
        if name:
            if current:
                blocks[current] = "\n".join(buffer).strip()
            current, buffer = name, [match.group(2)]
        elif current:
            buffer.append(line)
    if current:
        blocks[current] = "\n".join(buffer).strip()
    return blocks


def check(text):
    """Вернуть список (уровень, блок, сообщение). Уровень: ERROR или WARN."""
    issues = []
    blocks = parse_blocks(text)

    for name in REQUIRED:
        if name not in blocks:
            issues.append(("ERROR", name, "блок отсутствует"))
        elif not blocks[name]:
            issues.append(("ERROR", name, "блок пустой"))

    if "Role" not in blocks:
        issues.append(
            ("WARN", "Role", "роль не указана — это нормально для фактических задач")
        )

    role = blocks.get("Role", "")
    if role:
        lowered = role.lower()
        for word in PUFFERY:
            if word in lowered:
                issues.append(
                    ("WARN", "Role", f"украшение «{word}» — убрать, пользы не даёт")
                )
        if EXPERIENCE.search(role):
            issues.append(("WARN", "Role", "стаж в роли не помогает — убрать"))
        if len(role) > 200:
            issues.append(
                ("WARN", "Role", f"слишком длинная ({len(role)} симв.), хватит одного предложения")
            )

    context = blocks.get("Context", "")
    task = blocks.get("Task", "")
    if context and len(context) < 40:
        issues.append(("WARN", "Context", "слишком короткий: добавь факты и ограничения"))
    if context and task:
        c_words = {w for w in re.findall(r"\w{5,}", context.lower())}
        t_words = {w for w in re.findall(r"\w{5,}", task.lower())}
        if t_words and len(c_words & t_words) / len(t_words) > 0.7:
            issues.append(("WARN", "Context", "почти повторяет Task — нужны новые факты"))

    if task:
        sentences = [s for s in re.split(r"[.!?\n]+", task) if s.strip()]
        if len(sentences) > 3:
            issues.append(("WARN", "Task", "несколько действий — оставь одно"))
        if MULTI_ACTION.search(task) or re.search(r"\n\s*[2-9][.)]", task):
            issues.append(("WARN", "Task", "перечисление действий — разбей на отдельные промпты"))
        if task.lower().lstrip().startswith(INDIRECT_START):
            issues.append(("WARN", "Task", "начни с глагола действия: «составь», «сравни»"))

    fmt = blocks.get("Format", "")
    if fmt and not any(marker in fmt.lower() for marker in CONCRETE_FORMAT):
        issues.append(
            ("ERROR", "Format", "нет конкретики: задай структуру (таблица, список, JSON) или объём")
        )

    lowered_all = text.lower()
    for name, body in blocks.items():
        for word in VAGUE:
            if word in body.lower():
                issues.append(("WARN", name, f"размытое «{word}» — заменить числом или структурой"))
    for word in PLACEHOLDERS:
        if word in lowered_all:
            issues.append(("ERROR", "—", f"остался незаполненный кусок «{word}»"))

    return issues


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip())
        return 2
    source = argv[1]
    try:
        text = sys.stdin.read() if source == "-" else open(source, encoding="utf-8").read()
    except OSError as exc:
        print(f"Не удалось прочитать {source}: {exc}", file=sys.stderr)
        return 2

    issues = check(text)
    if not issues:
        print("OK: промпт собран по RCTF, замечаний нет.")
        return 0

    for level, block, message in issues:
        print(f"{level:<5} {block:<8} {message}")
    errors = sum(1 for level, _, _ in issues if level == "ERROR")
    warns = len(issues) - errors
    print(f"\nИтого: ошибок {errors}, предупреждений {warns}.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
