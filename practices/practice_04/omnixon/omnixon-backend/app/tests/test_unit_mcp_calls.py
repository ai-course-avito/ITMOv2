"""A failing MCP tool call becomes the tool's result; the agent's answer goes on (ai/mcp_calls.py)."""

import httpx
import pytest
from mcp.shared.exceptions import McpError
from mcp.types import CONNECTION_CLOSED, ErrorData
from pydantic_ai.exceptions import ModelRetry

from ai import mcp_calls
from ai import utils as ai_utils

CONFIG = {"url": "https://user:pw@mcp.example:8443/mcp?token=secret"}


def refusal(text: str) -> ModelRetry:
    """What pydantic-ai raises when the server answered `isError`."""
    return ModelRetry(text)


def protocol_error(code: int, message: str) -> ModelRetry:
    """What pydantic-ai raises from inside `except McpError` (a closed connection, a timeout)."""
    try:
        raise McpError(ErrorData(code=code, message=message))
    except McpError as e:
        try:
            raise ModelRetry(e.error.message)
        except ModelRetry as retry:
            return retry


class Fresh:
    """A new connection made by `connect(config)`: answers with what `results` says, in turn."""

    def __init__(self, results: list):
        self.results = results
        self.made = 0

    def __call__(self, config):
        self.made += 1
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def direct_call_tool(self, name, args):
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(mcp_calls, "MCP_TOOL_RETRY_DELAY", 0)
    monkeypatch.setattr(mcp_calls, "MCP_TOOL_ATTEMPTS", 3)


def first_call(*outcomes):
    """The first attempt goes through pydantic-ai's own `direct_call_tool`."""
    calls = []

    async def call(name, args):
        calls.append((name, args))
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    return call, calls


@pytest.mark.asyncio
async def test_a_tool_that_answers_works_as_before():
    call, calls = first_call({"id": 4})
    process = mcp_calls.safe_tool_calls(CONFIG, Fresh([]))
    assert await process(None, call, "get_agent", {"agent_id": 4}) == {"id": 4}
    assert calls == [("get_agent", {"agent_id": 4})]


@pytest.mark.asyncio
async def test_an_error_the_tool_answered_goes_to_the_model_at_once():
    call, calls = first_call(
        refusal("The service refused get_agent: HTTP 404: Agent not found")
    )
    fresh = Fresh([])
    result = await mcp_calls.safe_tool_calls(CONFIG, fresh)(
        None, call, "get_agent", {"agent_id": 9}
    )
    assert result == (
        "The MCP tool `get_agent` (https://mcp.example:8443/mcp) answered with an error: "
        "The service refused get_agent: HTTP 404: Agent not found"
    )
    assert (
        len(calls) == 1 and fresh.made == 0
    )  # the same arguments would fail the same way


@pytest.mark.asyncio
async def test_a_dropped_connection_is_tried_again_over_a_new_one():
    call, _ = first_call(protocol_error(CONNECTION_CLOSED, "Connection closed"))
    fresh = Fresh([httpx.ConnectError("All connection attempts failed"), {"ok": True}])
    assert await mcp_calls.safe_tool_calls(CONFIG, fresh)(
        None, call, "get_agents", {}
    ) == {"ok": True}
    assert fresh.made == 2


@pytest.mark.asyncio
async def test_after_three_failed_attempts_the_model_gets_what_went_wrong_and_the_answer_goes_on():
    request = httpx.Request("POST", "https://mcp.example:8443/mcp")
    status = httpx.HTTPStatusError(
        "boom",
        request=request,
        response=httpx.Response(500, text="Internal Server Error", request=request),
    )
    call, _ = first_call(httpx.ReadTimeout("timed out"))
    fresh = Fresh(
        [
            protocol_error(408, "Timed out while waiting for response"),
            ExceptionGroup("tg", [status]),
        ]
    )
    result = await mcp_calls.safe_tool_calls(CONFIG, fresh)(
        None, call, "create_agent", {"name": "x"}
    )
    assert result.startswith(
        "The MCP tool `create_agent` (https://mcp.example:8443/mcp) could not be called: 3 attempts failed."
    )
    assert "Last error: HTTP 500 from the MCP server: Internal Server Error." in result
    assert "secret" not in result and "pw" not in result


@pytest.mark.asyncio
async def test_a_message_that_ends_with_a_period_gets_no_second_one():
    call, _ = first_call(protocol_error(408, "Timed out. Waited 2.0 seconds."))
    fresh = Fresh([protocol_error(408, "Timed out. Waited 2.0 seconds.")] * 2)
    result = await mcp_calls.safe_tool_calls(CONFIG, fresh)(None, call, "request", {})
    assert "seconds.." not in result and "Waited 2.0 seconds. Go on" in result


def test_failures_are_described_with_their_codes():
    describe = mcp_calls.describe_failure
    assert describe(McpError(ErrorData(code=-32000, message="Connection closed"))) == (
        "MCP error -32000: Connection closed"
    )
    assert describe(
        ExceptionGroup(
            "g", [httpx.ConnectError("refused"), httpx.ConnectError("refused")]
        )
    ) == ("ConnectError: refused")
    assert describe(TimeoutError()) == "TimeoutError"


def test_every_mcp_server_gets_the_safe_calls():
    server = ai_utils.build_mcp_server({"url": "http://mcp/mcp"})
    assert server.process_tool_call is not None
    assert server.process_tool_call.__qualname__.startswith("safe_tool_calls")


def test_the_model_is_told_which_servers_are_missing_and_why():
    from ai.endpoint import _unavailable_servers_note

    assert _unavailable_servers_note([]) is None
    note = _unavailable_servers_note(
        ["- omnixon (http://mcp:8090/mcp): ConnectError: refused"]
    )
    assert "cannot be reached" in note and "ConnectError: refused" in note
    agent = __import__("ai.agent", fromlist=["generate_agent"]).generate_agent(
        "test", instructions=note
    )
    assert note in agent._instructions
