"""Клиент TickTick Open API и расчёты поверх него. Только стандартная библиотека.

Чистые функции (разбор дат, давление, разбиение на дни) вынесены отдельно,
чтобы их можно было тестировать без сети и без токена.
"""

import json
import math
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_URL = "https://api.ticktick.com/open/v1"
ENV_PATH = Path(__file__).with_name(".env")
HOURS_MARKER = "hours_needed="
MAX_HOURS = 1000
OVERDUE_BASE = 10_000


class TickTickError(Exception):
    """Ошибка входных данных или ответа API — показывается пользователю как текст."""


# --- чистая логика -----------------------------------------------------------


def parse_date(value, field):
    if not isinstance(value, str):
        raise TickTickError(f"{field}: ожидается строка вида ГГГГ-ММ-ДД, получено {value!r}")
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise TickTickError(f"{field}: неверная дата {value!r}, нужен формат ГГГГ-ММ-ДД")


def to_api_date(day, hour=9):
    return f"{day.isoformat()}T{hour:02d}:00:00+0000"


def from_api_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def check_hours(value, field, maximum=MAX_HOURS):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TickTickError(f"{field}: ожидается число, получено {value!r}")
    if value <= 0:
        raise TickTickError(f"{field}: должно быть больше нуля, получено {value}")
    if value > maximum:
        raise TickTickError(f"{field}: слишком много ({value}), максимум {maximum}")
    return float(value)


def pressure(hours_needed, days_left):
    """Нагрузка: сколько часов в день придётся тратить, чтобы успеть.

    Просрочка всегда важнее любого будущего дедлайна, поэтому ей даётся база
    заведомо выше максимально достижимой нагрузки (MAX_HOURS часов за один день).
    """
    if days_left < 0:
        return OVERDUE_BASE + (-days_left) * 10 + hours_needed
    return hours_needed / max(days_left, 1)


def read_hours(content):
    """Достать оценку трудоёмкости из описания задачи."""
    for line in (content or "").splitlines():
        line = line.strip()
        if line.startswith(HOURS_MARKER):
            try:
                return float(line[len(HOURS_MARKER):])
            except ValueError:
                return None
    return None


def split_plan(total_hours, hours_per_day, due, today):
    """Разбить работу на дни так, чтобы последний кусок пришёлся на дедлайн."""
    chunks = math.ceil(total_hours / hours_per_day)
    days_left = (due - today).days + 1
    if days_left <= 0:
        raise TickTickError(f"дедлайн {due.isoformat()} уже прошёл, планировать нечего")
    if chunks > days_left:
        raise TickTickError(
            f"не успеть: нужно {chunks} дн. по {hours_per_day} ч, а до дедлайна {days_left} дн. "
            f"Увеличь hours_per_day минимум до {math.ceil(total_hours / days_left)}"
        )
    start = due - timedelta(days=chunks - 1)
    remaining = total_hours
    schedule = []
    for index in range(chunks):
        hours = min(hours_per_day, remaining)
        schedule.append((start + timedelta(days=index), round(hours, 2), index + 1, chunks))
        remaining -= hours
    return schedule


# --- доступ к API ------------------------------------------------------------


def load_token():
    token = os.environ.get("TICKTICK_ACCESS_TOKEN", "").strip()
    if not token and ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("TICKTICK_ACCESS_TOKEN="):
                token = line.split("=", 1)[1].strip()
                break
    if not token:
        raise TickTickError(
            "нет TICKTICK_ACCESS_TOKEN: впиши личный токен в .env (Settings > Account > API Token)"
        )
    return token


def api(method, path, body=None, token=None):
    token = token or load_token()
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        BASE_URL + path,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise TickTickError("TickTick отклонил токен (401): он истёк или неверен")
        detail = exc.read().decode(errors="replace")[:200]
        raise TickTickError(f"TickTick ответил {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        raise TickTickError(f"нет связи с TickTick: {exc.reason}")


def list_projects(token=None):
    projects = api("GET", "/project", token=token)
    return [{"id": p["id"], "name": p.get("name", "")} for p in projects]


def resolve_project(name, token=None):
    projects = list_projects(token)
    if not name:
        return projects[0] if projects else None
    for project in projects:
        if project["name"].lower() == name.lower():
            return project
    known = ", ".join(p["name"] for p in projects) or "нет ни одного"
    raise TickTickError(f"проект {name!r} не найден. Доступны: {known}")


def project_tasks(project_id, token=None):
    data = api("GET", f"/project/{project_id}/data", token=token)
    return data.get("tasks") or []


def create_task(title, project_id, due, content=None, token=None):
    body = {"title": title, "projectId": project_id, "dueDate": to_api_date(due)}
    if content:
        body["content"] = content
    return api("POST", "/task", body, token=token)
