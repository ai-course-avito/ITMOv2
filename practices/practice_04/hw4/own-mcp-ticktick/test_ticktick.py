"""Тесты расчётов и протокола. Сеть и токен не нужны: API не вызывается."""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

import ticktick as tt

SERVER = Path(__file__).with_name("server.py")


# --- разбор дат --------------------------------------------------------------


def test_parse_date_ok():
    assert tt.parse_date("2026-10-10", "due") == date(2026, 10, 10)


@pytest.mark.parametrize("value", ["10.10.2026", "2026-13-01", "завтра", "", "2026-02-30"])
def test_parse_date_rejects_garbage(value):
    with pytest.raises(tt.TickTickError) as exc:
        tt.parse_date(value, "due")
    assert "due" in str(exc.value)


def test_parse_date_rejects_non_string():
    with pytest.raises(tt.TickTickError):
        tt.parse_date(20261010, "due")


def test_api_date_roundtrip():
    assert tt.from_api_date(tt.to_api_date(date(2026, 10, 10))) == date(2026, 10, 10)


def test_from_api_date_handles_real_response_format():
    assert tt.from_api_date("2026-10-10T09:00:00.000+0000") == date(2026, 10, 10)


@pytest.mark.parametrize("value", [None, "", "мусор"])
def test_from_api_date_returns_none_on_bad_input(value):
    assert tt.from_api_date(value) is None


# --- проверка часов ----------------------------------------------------------


@pytest.mark.parametrize("value", [0, -3, "4", None, True, 5000])
def test_check_hours_rejects_bad_values(value):
    with pytest.raises(tt.TickTickError):
        tt.check_hours(value, "hours_needed")


def test_check_hours_accepts_int_and_float():
    assert tt.check_hours(4, "h") == 4.0
    assert tt.check_hours(2.5, "h") == 2.5


# --- трудоёмкость из описания ------------------------------------------------


def test_read_hours_from_content():
    assert tt.read_hours("hours_needed=6") == 6.0


def test_read_hours_ignores_other_lines():
    assert tt.read_hours("заметка\nhours_needed=2.5\nещё") == 2.5


@pytest.mark.parametrize("content", [None, "", "просто текст", "hours_needed=много"])
def test_read_hours_returns_none_when_absent(content):
    assert tt.read_hours(content) is None


# --- давление ----------------------------------------------------------------


def test_pressure_is_hours_per_remaining_day():
    assert tt.pressure(8, 4) == 2.0


def test_same_date_more_hours_means_more_pressure():
    assert tt.pressure(8, 2) > tt.pressure(1, 2)


def test_closer_deadline_outranks_later_one_with_equal_hours():
    assert tt.pressure(6, 2) > tt.pressure(6, 10)


def test_overdue_outranks_everything_upcoming():
    assert tt.pressure(1, -1) > tt.pressure(24, 1)


def test_due_today_does_not_divide_by_zero():
    assert tt.pressure(5, 0) == 5.0


# --- разбиение на дни --------------------------------------------------------


def test_split_plan_ends_on_the_due_date():
    schedule = tt.split_plan(6, 2, date(2026, 10, 10), date(2026, 10, 1))
    assert [d.isoformat() for d, *_ in schedule] == ["2026-10-08", "2026-10-09", "2026-10-10"]


def test_split_plan_last_chunk_holds_the_remainder():
    schedule = tt.split_plan(5, 2, date(2026, 10, 10), date(2026, 10, 1))
    assert [hours for _, hours, _, _ in schedule] == [2, 2, 1]


def test_split_plan_numbers_days():
    schedule = tt.split_plan(4, 2, date(2026, 10, 10), date(2026, 10, 1))
    assert [(i, n) for *_, i, n in schedule] == [(1, 2), (2, 2)]


def test_split_plan_fits_exactly_into_available_days():
    schedule = tt.split_plan(3, 1, date(2026, 10, 3), date(2026, 10, 1))
    assert len(schedule) == 3


def test_split_plan_refuses_when_time_is_not_enough():
    with pytest.raises(tt.TickTickError) as exc:
        tt.split_plan(20, 2, date(2026, 10, 3), date(2026, 10, 1))
    assert "не успеть" in str(exc.value)
    assert "hours_per_day" in str(exc.value)


def test_split_plan_refuses_past_deadline():
    with pytest.raises(tt.TickTickError) as exc:
        tt.split_plan(4, 2, date(2026, 10, 1), date(2026, 10, 5))
    assert "прошёл" in str(exc.value)


# --- протокол ----------------------------------------------------------------


class Session:
    def __init__(self):
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=SERVER.parent,
            env={"PATH": "/usr/bin:/bin", "TICKTICK_ACCESS_TOKEN": "fake-token-for-tests"},
        )
        self._id = 0

    def request(self, method, params=None):
        self._id += 1
        message = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            message["params"] = params
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline())

    def call(self, name, arguments):
        return self.request("tools/call", {"name": name, "arguments": arguments})["result"]

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=10)


@pytest.fixture
def session():
    s = Session()
    s.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}})
    yield s
    s.close()


def test_initialize_reports_server_name():
    s = Session()
    reply = s.request("initialize", {"protocolVersion": "2024-11-05"})
    s.close()
    assert reply["result"]["serverInfo"]["name"] == "ticktick-deadlines"


def test_tools_list_exposes_four_tools(session):
    tools = session.request("tools/list")["result"]["tools"]
    assert [t["name"] for t in tools] == ["list_projects", "add_deadline", "whats_urgent", "plan"]
    add = next(t for t in tools if t["name"] == "add_deadline")
    assert add["inputSchema"]["required"] == ["subject", "task", "due", "hours_needed"]


@pytest.mark.parametrize(
    "arguments, fragment",
    [
        ({"subject": "БД", "task": "лаба", "due": "вчера", "hours_needed": 4}, "due"),
        ({"subject": "БД", "task": "лаба", "due": "2026-10-10", "hours_needed": -2}, "больше нуля"),
        ({"subject": "БД", "task": "лаба", "due": "2020-01-01", "hours_needed": 4}, "прошёл"),
        ({"subject": "БД", "task": "лаба", "hours_needed": 4}, "due"),
        ({"subject": "", "task": "лаба", "due": "2030-01-01", "hours_needed": 4}, "пустыми"),
    ],
)
def test_add_deadline_rejects_bad_input_before_touching_network(session, arguments, fragment):
    result = session.call("add_deadline", arguments)
    assert result["isError"] is True
    assert fragment in result["content"][0]["text"]


@pytest.mark.parametrize("days", [0, 400, "семь", True])
def test_whats_urgent_validates_days(session, days):
    result = session.call("whats_urgent", {"days": days})
    assert result["isError"] is True
    assert "days" in result["content"][0]["text"]


@pytest.mark.parametrize(
    "arguments, fragment",
    [
        ({"task_query": "лаба", "hours_per_day": 0}, "больше нуля"),
        ({"task_query": "лаба", "hours_per_day": 30}, "максимум 24"),
        ({"task_query": "", "hours_per_day": 2}, "пустым"),
        ({"hours_per_day": 2}, "task_query"),
    ],
)
def test_plan_validates_input(session, arguments, fragment):
    result = session.call("plan", arguments)
    assert result["isError"] is True
    assert fragment in result["content"][0]["text"]


def test_unknown_tool_is_protocol_error(session):
    assert session.request("tools/call", {"name": "drop_all", "arguments": {}})["error"]["code"] == -32602


def test_unknown_method_is_protocol_error(session):
    assert session.request("resources/list")["error"]["code"] == -32601


def test_garbage_line_does_not_kill_server(session):
    session.proc.stdin.write("не json\n")
    session.proc.stdin.flush()
    assert json.loads(session.proc.stdout.readline())["error"]["code"] == -32700
    assert session.request("ping")["result"] == {}


def test_missing_token_is_reported_clearly(monkeypatch, tmp_path):
    monkeypatch.delenv("TICKTICK_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(tt, "ENV_PATH", tmp_path / "nope.env")
    with pytest.raises(tt.TickTickError) as exc:
        tt.load_token()
    assert "TICKTICK_ACCESS_TOKEN" in str(exc.value)
