#!/usr/bin/env python3
"""MCP-сервер над TickTick: дедлайны с оценкой трудоёмкости и разбиением на дни.

Протокол: JSON-RPC 2.0 по stdio, одно сообщение на строку. Только стандартная библиотека.
Токен берётся из .env рядом с файлом и в ответы не попадает.
"""

import json
import sys
from datetime import date

import ticktick as tt

SERVER_INFO = {"name": "ticktick-deadlines", "version": "1.0.0"}
DEFAULT_PROTOCOL = "2024-11-05"

TOOLS = [
    {
        "name": "list_projects",
        "description": "Показать списки (проекты) TickTick: их имена и id. "
        "Нужен, чтобы узнать, куда класть задачи.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "add_deadline",
        "description": "Завести учебный дедлайн в TickTick с оценкой трудоёмкости в часах. "
        "Оценка сохраняется в описании задачи и потом используется в whats_urgent и plan.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Предмет или курс"},
                "task": {"type": "string", "description": "Что сдать"},
                "due": {"type": "string", "description": "Дедлайн, ГГГГ-ММ-ДД"},
                "hours_needed": {"type": "number", "description": "Оценка работы в часах"},
                "project": {"type": "string", "description": "Имя списка TickTick (необязательно)"},
            },
            "required": ["subject", "task", "due", "hours_needed"],
        },
    },
    {
        "name": "whats_urgent",
        "description": "Что горит: задачи с дедлайном в ближайшие N дней, отсортированные "
        "не по дате, а по нагрузке — сколько часов в день придётся тратить, чтобы успеть.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "minimum": 1, "maximum": 365, "default": 14},
                "project": {"type": "string", "description": "Ограничить одним списком"},
            },
        },
    },
    {
        "name": "plan",
        "description": "Разбить дедлайн на подзадачи по дням и завести их в TickTick с датами, "
        "чтобы работа заканчивалась в день сдачи.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_query": {"type": "string", "description": "Часть названия задачи"},
                "hours_per_day": {"type": "number", "description": "Сколько часов в день готов тратить"},
                "total_hours": {
                    "type": "number",
                    "description": "Трудоёмкость, если в задаче её нет",
                },
            },
            "required": ["task_query", "hours_per_day"],
        },
    },
]


def ok(text):
    return {"content": [{"type": "text", "text": text}], "isError": False}


def fail(text):
    return {"content": [{"type": "text", "text": f"Ошибка: {text}"}], "isError": True}


def require(arguments, name):
    if name not in arguments:
        raise tt.TickTickError(f"не передан обязательный аргумент {name}")
    return arguments[name]


def find_tasks(query, token=None):
    """Найти задачи по части названия во всех проектах."""
    found = []
    for project in tt.list_projects(token):
        for task in tt.project_tasks(project["id"], token):
            if query.lower() in task.get("title", "").lower():
                found.append((project, task))
    return found


def tool_list_projects(_arguments):
    projects = tt.list_projects()
    if not projects:
        return ok("Списков нет.")
    lines = [f"- {p['name']}  (id {p['id']})" for p in projects]
    return ok("Списки TickTick:\n" + "\n".join(lines))


def tool_add_deadline(arguments):
    subject = str(require(arguments, "subject")).strip()
    task = str(require(arguments, "task")).strip()
    if not subject or not task:
        raise tt.TickTickError("subject и task не должны быть пустыми")
    due = tt.parse_date(require(arguments, "due"), "due")
    hours = tt.check_hours(require(arguments, "hours_needed"), "hours_needed")
    today = date.today()
    if due < today:
        raise tt.TickTickError(f"дедлайн {due.isoformat()} уже прошёл")

    project = tt.resolve_project(arguments.get("project"))
    if not project:
        raise tt.TickTickError("в TickTick нет ни одного списка")

    title = f"{subject}: {task}"
    created = tt.create_task(title, project["id"], due, f"{tt.HOURS_MARKER}{hours:g}")
    days_left = (due - today).days
    per_day = tt.pressure(hours, days_left)
    return ok(
        f"Добавлено в «{project['name']}»: {title}\n"
        f"Дедлайн {due.isoformat()}, осталось дней: {days_left}\n"
        f"Трудоёмкость {hours:g} ч — это {per_day:.1f} ч в день\n"
        f"id задачи: {created.get('id')}"
    )


def tool_whats_urgent(arguments):
    days = arguments.get("days", 14)
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 365:
        raise tt.TickTickError(f"days: нужно целое от 1 до 365, получено {days!r}")

    today = date.today()
    projects = (
        [tt.resolve_project(arguments["project"])]
        if arguments.get("project")
        else tt.list_projects()
    )

    rows = []
    for project in projects:
        for task in tt.project_tasks(project["id"]):
            if task.get("status"):
                continue
            due = tt.from_api_date(task.get("dueDate"))
            if not due:
                continue
            days_left = (due - today).days
            if days_left > days:
                continue
            hours = tt.read_hours(task.get("content"))
            rows.append(
                {
                    "title": task.get("title", "без названия"),
                    "project": project["name"],
                    "due": due,
                    "days_left": days_left,
                    "hours": hours,
                    "score": tt.pressure(hours or 1.0, days_left),
                }
            )

    if not rows:
        return ok(f"В ближайшие {days} дн. дедлайнов нет.")

    rows.sort(key=lambda r: r["score"], reverse=True)
    lines = [f"Горит в ближайшие {days} дн. (сверху — самое напряжённое):", ""]
    for row in rows:
        when = (
            f"просрочено на {-row['days_left']} дн."
            if row["days_left"] < 0
            else ("сегодня" if row["days_left"] == 0 else f"через {row['days_left']} дн.")
        )
        load = (
            f"{row['hours']:g} ч → {row['score']:.1f} ч/день"
            if row["hours"]
            else "трудоёмкость не указана"
        )
        lines.append(f"- {row['title']}  [{row['project']}]")
        lines.append(f"    {row['due'].isoformat()}, {when}; {load}")
    return ok("\n".join(lines))


def tool_plan(arguments):
    query = str(require(arguments, "task_query")).strip()
    if not query:
        raise tt.TickTickError("task_query не должен быть пустым")
    per_day = tt.check_hours(require(arguments, "hours_per_day"), "hours_per_day", maximum=24)

    matches = find_tasks(query)
    if not matches:
        raise tt.TickTickError(f"задача со словом {query!r} не найдена")
    if len(matches) > 1:
        titles = "\n".join(f"  - {t.get('title')}" for _, t in matches[:10])
        raise tt.TickTickError(f"под {query!r} подходит несколько задач, уточни:\n{titles}")

    project, task = matches[0]
    due = tt.from_api_date(task.get("dueDate"))
    if not due:
        raise tt.TickTickError(f"у задачи «{task.get('title')}» не выставлен дедлайн")

    total = arguments.get("total_hours")
    total = (
        tt.check_hours(total, "total_hours")
        if total is not None
        else tt.read_hours(task.get("content"))
    )
    if not total:
        raise tt.TickTickError(
            "у задачи нет оценки трудоёмкости — передай total_hours или заведи дедлайн через add_deadline"
        )

    schedule = tt.split_plan(total, per_day, due, date.today())
    title = task.get("title", "задача")
    created = []
    for day, hours, index, chunks in schedule:
        subtitle = f"{title} — день {index}/{chunks} ({hours:g} ч)"
        tt.create_task(subtitle, project["id"], day, f"{tt.HOURS_MARKER}{hours:g}")
        created.append(f"  {day.isoformat()}  {hours:g} ч  — день {index}/{chunks}")

    return ok(
        f"«{title}»: {total:g} ч разбито на {len(schedule)} дн. по {per_day:g} ч\n"
        + "\n".join(created)
        + f"\nПодзадачи созданы в списке «{project['name']}»."
    )


HANDLERS = {
    "list_projects": tool_list_projects,
    "add_deadline": tool_add_deadline,
    "whats_urgent": tool_whats_urgent,
    "plan": tool_plan,
}


def handle(message):
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params") or {}
    if msg_id is None:
        return None

    def result(payload):
        return {"jsonrpc": "2.0", "id": msg_id, "result": payload}

    def error(code, text):
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": text}}

    if method == "initialize":
        return result(
            {
                "protocolVersion": params.get("protocolVersion", DEFAULT_PROTOCOL),
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            }
        )
    if method == "ping":
        return result({})
    if method == "tools/list":
        return result({"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        handler = HANDLERS.get(name)
        if handler is None:
            return error(-32602, f"неизвестный tool: {name!r}")
        arguments = params.get("arguments")
        if not isinstance(arguments, dict):
            return result(fail("arguments должен быть объектом"))
        try:
            return result(handler(arguments))
        except tt.TickTickError as exc:
            return result(fail(str(exc)))
        except Exception as exc:  # noqa: BLE001 — сервер не должен падать из-за одного вызова
            return result(fail(f"{type(exc).__name__}: {exc}"))
    return error(-32601, f"метод не поддерживается: {method}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            reply = handle(message)
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
