"""unit tests of the failures of tools and MCP servers: none of them ends the agent's answer (ai/capabilities/mcp.py, tool_failures.py)"""

import fakeredis
import httpx
import pytest
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData
from pydantic_ai import Agent, ToolFailed
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ModelRequest, ToolReturnPart
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset

from ai.capabilities import McpServers, ToolFailures
from ai.capabilities.mcp import GuardedServer, ServerStatus, toolset_from_config
from ai.deps import RunDeps
from ai.failures import describe_failure, server_label
from infrastructure.mcp_health import McpHealth, RedisHealthStore, key_of

URL = "https://user:pw@mcp.example:8443/mcp?token=secret"
CONFIG = {"url": URL}


@pytest.fixture
def health():
    return McpHealth(down_seconds=30)


class Fake:
    """What pydantic-ai's MCP toolset is to the guard: calls that go as `outcomes` says, in turn."""

    def __init__(self, *outcomes, enter=None):
        self.outcomes, self.calls, self.entered, self.enter = list(outcomes), [], 0, enter

    async def __aenter__(self):
        self.entered += 1
        if self.enter:
            raise self.enter
        return self

    async def __aexit__(self, *args):
        return None

    async def call_tool(self, name, args, ctx, tool):
        self.calls.append((name, args))
        outcome = self.outcomes[min(len(self.calls), len(self.outcomes)) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def get_tools(self, ctx):
        return {"t": object()}

    async def get_instructions(self, ctx):
        return None


def guard(fake, health, attempts=3, config=CONFIG):
    status = ServerStatus("omnixon", config["url"], key_of(config))
    return GuardedServer(fake, status, health, attempts, retry_delay=0)


def protocol_error(code, message):
    return McpError(ErrorData(code=code, message=message))


@pytest.mark.asyncio
async def test_a_tool_that_answers_works_as_before(health):
    fake = Fake({"id": 4})
    assert await guard(fake, health).call_tool("get_agent", {"agent_id": 4}, None, None) == {"id": 4}
    assert fake.calls == [("get_agent", {"agent_id": 4})]


@pytest.mark.asyncio
async def test_an_error_the_tool_answered_is_the_tools_result_at_once_not_a_failure_to_get_through(health):
    for answered in (ToolFailed("The service refused get_agent: HTTP 404"), ModelRetry("fix the arguments")):
        fake = Fake(answered)
        with pytest.raises(type(answered)):
            await guard(fake, health).call_tool("get_agent", {"agent_id": 9}, None, None)
        assert len(fake.calls) == 1  # the same arguments would fail the same way


@pytest.mark.asyncio
async def test_a_call_that_did_not_get_through_is_tried_again(health):
    fake = Fake(protocol_error(-32000, "Connection closed"), httpx.ConnectError("refused"), {"ok": True})
    assert await guard(fake, health).call_tool("get_agents", {}, None, None) == {"ok": True}
    assert len(fake.calls) == 3


@pytest.mark.asyncio
async def test_after_all_attempts_the_model_gets_what_went_wrong_and_the_answer_goes_on(health):
    request = httpx.Request("POST", "https://mcp.example:8443/mcp")
    server_error = httpx.HTTPStatusError(
        "boom", request=request, response=httpx.Response(500, text="Internal Server Error", request=request)
    )
    fake = Fake(httpx.ReadTimeout("timed out"), protocol_error(408, "Timed out. Waited 2.0 seconds."), ExceptionGroup("tg", [server_error]))
    with pytest.raises(ToolFailed) as failed:
        await guard(fake, health).call_tool("create_agent", {"name": "x"}, None, None)
    message = str(failed.value)
    assert message.startswith("The MCP tool `create_agent` of omnixon (https://mcp.example:8443/mcp) could not be called: 3 attempts failed.")
    assert "Last error: HTTP 500 from the server: Internal Server Error." in message
    assert "secret" not in message and "pw" not in message and ".." not in message


@pytest.mark.asyncio
async def test_a_server_that_cannot_be_connected_to_gives_no_tools_and_says_why_to_the_model(health):
    fake = Fake(enter=ExceptionGroup("connect", [httpx.ConnectError("All connection attempts failed")]))
    server = guard(fake, health)
    await server.__aenter__()
    assert await server.get_tools(None) == {}
    note = await server.get_instructions(None)
    assert "omnixon (https://mcp.example:8443/mcp) cannot be reached" in note and "ConnectError: All connection attempts failed" in note
    assert "secret" not in note
    await server.__aexit__(None, None, None)  # nothing was entered: nothing to leave

    # the next request does not even try it
    other = Fake()
    again = guard(other, health)
    await again.__aenter__()
    assert other.entered == 0 and await again.get_tools(None) == {}


@pytest.mark.asyncio
async def test_a_server_that_is_up_is_entered_and_asked_for_its_tools(health):
    fake = Fake()
    server = guard(fake, health)
    await server.__aenter__()
    assert fake.entered == 1 and set(await server.get_tools(None)) == {"t"}
    assert server.status.down_because is None


@pytest.mark.asyncio
async def test_an_agent_with_a_dead_mcp_server_still_answers_and_knows_it_is_missing(health):
    seen = []

    from pydantic_ai.models.function import FunctionModel
    from pydantic_ai.messages import ModelResponse, TextPart

    def respond(messages, info):
        seen.append((info.instructions, [t.name for t in info.function_tools]))
        return ModelResponse(parts=[TextPart("I could not reach the server.")])

    agent = Agent(
        FunctionModel(respond),
        deps_type=RunDeps,
        capabilities=[ToolFailures(), McpServers(servers=[("omnixon", {"url": "http://127.0.0.1:1/mcp"})], health=health, retry_delay=0)],
    )
    result = await agent.run("hi", deps=RunDeps(None, None, None))
    assert result.output == "I could not reach the server."
    instructions, tools = seen[0]
    assert "omnixon (http://127.0.0.1:1/mcp) cannot be reached" in instructions and tools == []
    assert await health.why_down(key_of({"url": "http://127.0.0.1:1/mcp"}))  # and the next request leaves it alone


def test_failures_are_described_with_their_codes_and_without_secrets():
    assert describe_failure(protocol_error(-32000, "Connection closed")) == "MCP error -32000: Connection closed"
    assert describe_failure(
        ExceptionGroup("g", [httpx.ConnectError("refused"), httpx.ConnectError("refused")])
    ) == "ConnectError: refused"
    assert describe_failure(TimeoutError()) == "TimeoutError"
    assert server_label(URL) == "https://mcp.example:8443/mcp"


def test_a_server_is_its_config_so_other_headers_are_another_server():
    a, b = key_of({"url": "http://m/mcp", "headers": {"A": "1"}}), key_of({"url": "http://m/mcp", "headers": {"A": "2"}})
    assert a != b and a == key_of({"headers": {"A": "1"}, "url": "http://m/mcp"})
    assert "http" not in a  # only a fingerprint is kept


@pytest.mark.asyncio
async def test_a_dead_server_comes_back_after_a_while():
    local = McpHealth(down_seconds=0.05)
    await local.mark_down("x", "refused")
    assert await local.why_down("x") == "refused"
    import asyncio

    await asyncio.sleep(0.1)
    assert await local.why_down("x") is None


@pytest.mark.asyncio
async def test_replicas_share_which_servers_are_down_through_redis():
    server = fakeredis.FakeServer()
    a = McpHealth(30, shared=RedisHealthStore(fakeredis.FakeAsyncRedis(server=server, decode_responses=True)))
    b = McpHealth(30, shared=RedisHealthStore(fakeredis.FakeAsyncRedis(server=server, decode_responses=True)))
    await a.mark_down("srv", "ConnectError: refused")
    assert await b.why_down("srv") == "ConnectError: refused"  # a replica that never tried it knows
    assert await b.why_down("other") is None


@pytest.mark.asyncio
async def test_redis_that_is_down_does_not_break_the_requests():
    import redis.asyncio as redis

    client = redis.Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2, decode_responses=True)
    broken = McpHealth(30, shared=RedisHealthStore(client))
    await broken.mark_down("srv", "refused")  # logged, and remembered in the process
    assert await broken.why_down("srv") == "refused"


def _failing_tool(error):
    tools = FunctionToolset[RunDeps]()

    @tools.tool_plain
    def flaky(value: int) -> str:
        """A tool that raises."""
        raise error

    return tools


def tool_results(result):
    return [p for m in result.all_messages() if isinstance(m, ModelRequest) for p in m.parts if isinstance(p, ToolReturnPart) or p.part_kind == "retry-prompt"]


@pytest.mark.asyncio
async def test_a_tool_that_raises_gives_the_model_a_failed_result_and_the_answer_goes_on():
    for error in (RuntimeError("the database is gone"), KeyError("missing"), ConnectionError("lost")):
        agent = Agent(TestModel(), toolsets=[_failing_tool(error)], capabilities=[ToolFailures()], retries={"tools": 1})
        result = await agent.run("go")  # without ToolFailures this raises
        text = " ".join(str(p.content) for p in tool_results(result))
        assert "The tool `flaky` failed:" in text and type(error).__name__ in text, text
        assert result.output


@pytest.mark.asyncio
async def test_a_tool_that_the_model_cannot_call_right_does_not_end_the_answer_either():
    # ModelRetry asks the model to correct its call; once the allowed retries are used pydantic-ai raises UnexpectedModelBehavior. That used to end
    # the whole answer ("Tool ... exceeded max retries count"); now it is the tool's failed result, like any other failure.
    agent = Agent(TestModel(), toolsets=[_failing_tool(ModelRetry("give a better value"))], capabilities=[ToolFailures()], retries={"tools": 1})
    result = await agent.run("go")
    results = tool_results(result)
    assert [p.part_kind for p in results] == ["retry-prompt", "tool-return"]
    assert results[1].outcome == "failed" and "exceeded max retries" in results[1].content and result.output


def test_the_options_of_a_server_config_reach_the_toolset():
    toolset = toolset_from_config(
        {"url": "http://mcp/mcp", "headers": {"X": "1"}, "timeout": 3, "read_timeout": 9, "log_level": "info", "id": "calc",
         "cache_tools": False, "cache_resources": False}
    )
    assert toolset.id == "calc" and toolset.log_level == "info" and toolset.cache_tools is False and toolset.cache_resources is False
    assert toolset.client.transport.headers["X"] == "1"


@pytest.mark.asyncio
async def test_a_server_that_fails_when_asked_for_its_tools_is_left_out_not_fatal(health):
    class Broken(Fake):
        async def get_tools(self, ctx):
            raise ExceptionGroup("tools", [httpx.ReadTimeout("slow")])

    server = guard(Broken(), health)
    assert await server.get_tools(None) == {}
    assert "ReadTimeout" in server.status.down_because
    assert await health.why_down(server.status.key)  # and it is left alone from now on
    await server.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_a_server_that_was_entered_is_left_again(health):
    class Counted(Fake):
        left = 0

        async def __aexit__(self, *args):
            Counted.left += 1

    fake = Counted()
    server = guard(fake, health)
    await server.__aenter__()
    await server.__aexit__(None, None, None)
    assert Counted.left == 1
