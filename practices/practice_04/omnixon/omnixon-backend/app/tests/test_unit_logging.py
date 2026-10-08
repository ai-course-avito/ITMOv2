"""unit logging tests"""

import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from shared import (
    NOW,
)


APP_DIR = Path(__file__).parent.parent  # app/


LOGGING_SCRIPT = """
import logging
import logfire
from core import setup_logging

setup_logging()
logfire.info("hello {who}", who="world", n=3)
logfire.debug("hidden unless debug")
logfire.warning("careful")
logfire.info("nested", data={"a": [1, 2]}, flag=True)
try:
    1 / 0
except ZeroDivisionError:
    logfire.exception("failed {step}", step="divide")
logging.getLogger("uvicorn.error").warning("from uvicorn")
logging.getLogger("some.library").error("from a library")
with logfire.span("work {job}", job="a"):
    pass
print("not json, written by the app itself")
"""


def run_logging_script(**env):
    result = subprocess.run(
        [sys.executable, "-c", LOGGING_SCRIPT],
        capture_output=True,
        text=True,
        cwd=APP_DIR,
        env={**os.environ, **env},
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
    return [json.loads(line) for line in lines]  # every log line is valid JSON


def by_message(records, text):
    found = [r for r in records if text in r["message"]]
    assert len(found) == 1, (text, [r["message"] for r in records])
    return found[0]


def test_logs_are_json_lines_with_the_fields_of_the_call():
    records = run_logging_script()

    assert records[0]["message"] == "Logging is configured"
    hello = by_message(records, "hello world")
    assert hello["level"] == "info"
    assert hello["attributes"] == {"who": "world", "n": 3}
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", hello["timestamp"])
    assert len(hello["trace_id"]) == 32 and len(hello["span_id"]) == 16
    assert not any(key.startswith("logfire") for key in hello["attributes"])

    assert by_message(records, "careful")["level"] == "warn"


def test_nested_attributes_are_json_not_escaped_text():
    nested = by_message(run_logging_script(), "nested")
    assert nested["attributes"] == {"data": {"a": [1, 2]}, "flag": True}


def test_exceptions_are_logged_with_type_message_and_stacktrace():
    failed = by_message(run_logging_script(), "failed divide")
    assert failed["level"] == "error"
    assert failed["exception"]["type"] == "ZeroDivisionError"
    assert "division by zero" in failed["exception"]["message"]
    assert "Traceback" in failed["exception"]["stacktrace"]


def test_standard_logging_records_become_json_too():
    records = run_logging_script()
    assert by_message(records, "from uvicorn")["level"] == "warn"
    assert by_message(records, "from a library")["level"] == "error"


def test_spans_are_logged_once_finished_with_their_duration():
    work = by_message(run_logging_script(), "work a")
    assert work["duration_ms"] >= 0 and work["attributes"] == {"job": "a"}


def test_log_level_decides_what_is_written():
    messages = lambda records: {r["message"] for r in records}

    assert "hidden unless debug" not in messages(
        run_logging_script()
    )  # info is the default
    assert "hidden unless debug" in messages(run_logging_script(LOG_LEVEL="debug"))

    quiet = messages(run_logging_script(LOG_LEVEL="warning"))
    assert "hello world" not in quiet and "careful" in quiet


UNIT_TOKEN = (
    "abc_" + ("Zy9Xw8Vu7Ts6Rq5Po4Nm3Lk2Ji1Hg0FeDcBa" * 2)[:60]
)  # the format of unit tokens
assert len(UNIT_TOKEN) == 64


def test_values_under_sensitive_names_are_masked():
    from core.masking import MASK, mask_value

    data = {
        "token": "abc",
        "Authorization": "Bearer xyz",
        "nested": {
            "api_key": "k",
            "openrouter_api_key": "k",
            "password": "p",
            "ok": "fine",
        },
        "items": [{"secret": "s"}, "plain"],
        "max_tokens": 128,  # a number is not a secret, whatever its name
    }
    assert mask_value(data) == {
        "token": MASK,
        "Authorization": MASK,
        "nested": {
            "api_key": MASK,
            "openrouter_api_key": MASK,
            "password": MASK,
            "ok": "fine",
        },
        "items": [{"secret": MASK}, "plain"],
        "max_tokens": 128,
    }


def test_secrets_are_masked_inside_texts():
    from core.masking import MASK, mask_text

    assert (
        mask_text("Authorization: Bearer abcdef123456")
        == f"Authorization: Bearer {MASK}"
    )
    assert mask_text(f"unit {UNIT_TOKEN} failed") == f"unit {MASK} failed"
    assert mask_text("key sk-or-v1-0123456789abcdefABCDEF here") == f"key {MASK} here"
    assert (
        mask_text("socks5://user:hunter2@10.0.0.1:1080")
        == f"socks5://user:{MASK}@10.0.0.1:1080"
    )
    assert (
        mask_text("nothing secret here, token is not a value")
        == "nothing secret here, token is not a value"
    )


def test_secrets_of_the_deployment_are_masked_wherever_they_appear(monkeypatch):
    from core.masking import MASK, mask_text

    monkeypatch.setenv("INITIAL_API_KEY", "my-very-own-admin-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")  # too short to be told from words
    assert mask_text("key=my-very-own-admin-key;") == f"key={MASK};"
    assert mask_text("x marks the spot") == "x marks the spot"


def test_models_are_logged_without_their_secret_but_the_api_returns_it_when_a_token_is_made():
    from core.masking import MASK, mask_value
    from domain.entities import NewToken

    made = NewToken(
        id=1, name="t", agent_id=2, role="admin", token=UNIT_TOKEN, timestamp=NOW
    )
    masked = mask_value(made)
    assert masked["token"] == MASK and masked["id"] == 1 and masked["role"] == "admin"
    assert UNIT_TOKEN not in str(masked)
    assert (
        made.model_dump()["token"] == UNIT_TOKEN
    )  # the answer to making a token must carry it


def test_arguments_are_masked_by_parameter_name_and_objects_are_not_dumped():
    from core.masking import MASK, mask_arguments, mask_value

    class Secretive:
        def __repr__(self):
            return "holds-the-secret"

    async def get_unit(self, token: str, limit: int = 3, request=None): ...

    arguments = mask_arguments(get_unit, ("db", UNIT_TOKEN), {"request": Secretive()})
    assert arguments == {"token": MASK, "request": "<Secretive>"}
    assert mask_value(Secretive()) == "<Secretive>"


MASKING_SCRIPT = """
import asyncio, logfire
from core import setup_logging, async_logfire_decorator
from domain.entities import NewToken
from datetime import datetime

setup_logging()
TOKEN = %r

@async_logfire_decorator
async def get_unit(token: str):
    return NewToken(id=1, name='t', agent_id=1, role='admin', token=token, timestamp=datetime(2026, 1, 1))

asyncio.run(get_unit(TOKEN))
logfire.info("unit {unit} came with Bearer " + TOKEN, unit=TOKEN, token=TOKEN)
logfire.info("plain " + TOKEN)
try:
    raise RuntimeError("failed for " + TOKEN)
except RuntimeError:
    logfire.exception("boom")
"""


def test_tokens_never_reach_the_log_output():
    result = subprocess.run(
        [sys.executable, "-c", MASKING_SCRIPT % UNIT_TOKEN],
        capture_output=True,
        text=True,
        cwd=APP_DIR,
        env={**os.environ, "LOG_LEVEL": "debug"},  # debug logs every call and result
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "Zy9Xw8Vu7Ts6Rq5Po4Nm3Lk2Ji1Hg0Fe" not in result.stdout + result.stderr
    records = [
        json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")
    ]
    call = next(r for r in records if r["message"].startswith("Function get_unit"))
    assert call["attributes"]["arguments"] == {"token": "***"}
    assert call["attributes"]["result"]["token"] == "***"
    assert call["attributes"]["result"]["id"] == 1  # the rest is still useful
    failed = next(r for r in records if r["message"] == "boom")
    assert "***" in failed["exception"]["message"]


def test_upstream_failures_are_502_or_504_not_500():
    import httpx
    from core import error_response
    from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior

    status, detail = error_response(
        ModelHTTPError(400, "a/b", {"message": "not valid"})
    )
    assert status == 502 and "Model provider error" in detail and "not valid" in detail
    assert error_response(UnexpectedModelBehavior("empty answer"))[0] == 502
    assert (
        error_response(httpx.ConnectError("All connection attempts failed"))[0] == 502
    )
    assert error_response(httpx.ReadTimeout("slow"))[0] == 504
    assert error_response(asyncio.TimeoutError())[0] == 504


def test_exception_groups_are_unwrapped():
    import httpx
    from core import error_response

    group = ExceptionGroup(
        "unhandled errors in a TaskGroup", [httpx.ConnectError("refused")]
    )
    status, detail = error_response(ExceptionGroup("outer", [group]))
    assert status == 502 and "ConnectError" in detail and "refused" in detail


def test_our_own_errors_stay_500():
    from core import error_response

    assert error_response(RuntimeError("boom")) == (500, "boom")
    assert error_response(ExceptionGroup("g", [KeyError("k")]))[0] == 500
