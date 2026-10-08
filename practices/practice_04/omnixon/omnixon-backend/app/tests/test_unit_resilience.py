"""unit resilience tests"""

import asyncio
from types import SimpleNamespace
import pytest
from database.foundation import list_migrations
from ai import resilience
from ai.resilience import Attempts, run_with_attempts


def test_which_failures_are_worth_retrying():
    import httpx
    from pydantic_ai.exceptions import (
        ModelAPIError,
        ModelHTTPError,
        UnexpectedModelBehavior,
    )

    for status in (408, 429, 500, 502, 503, 504):
        assert resilience.is_retryable(ModelHTTPError(status, "a/b", "x")), status
    for status in (400, 401, 402, 403, 404, 422):
        assert not resilience.is_retryable(ModelHTTPError(status, "a/b", "x")), status

    assert resilience.is_retryable(httpx.ReadTimeout("slow"))
    assert resilience.is_retryable(httpx.ConnectError("refused"))
    assert resilience.is_retryable(ModelAPIError("a/b", "connection dropped"))
    assert resilience.is_retryable(UnexpectedModelBehavior("empty answer"))
    assert resilience.is_retryable(
        ExceptionGroup("g", [ModelHTTPError(503, "a/b", "x")])
    )
    assert not resilience.is_retryable(RuntimeError("a bug"))
    assert not resilience.is_retryable(ExceptionGroup("g", [KeyError("k")]))


def test_mcp_failures_are_told_from_provider_failures():
    import httpx
    from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError

    assert resilience.is_mcp_failure(httpx.ConnectError("refused"))
    assert resilience.is_mcp_failure(
        ExceptionGroup("g", [httpx.ConnectTimeout("slow")])
    )
    assert not resilience.is_mcp_failure(ModelHTTPError(502, "a/b", "x"))
    assert not resilience.is_mcp_failure(ModelAPIError("a/b", "connection dropped"))
    assert not resilience.is_mcp_failure(RuntimeError("a bug"))


class Flaky:
    """An agent whose calls fail in the given order, then work."""

    def __init__(self, *failures):
        self.failures = list(failures)
        self.calls = 0

    async def call(self, agent):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return "answer"


async def plain_build(attempts):
    return "agent", []


@pytest.mark.asyncio
async def test_a_failing_provider_is_retried_twice_more():
    from pydantic_ai.exceptions import ModelHTTPError

    flaky = Flaky(ModelHTTPError(502, "a/b", "x"), ModelHTTPError(504, "a/b", "x"))
    result = await run_with_attempts(
        plain_build, flaky.call, Attempts(retries=2, delay=0)
    )
    assert result == "answer" and flaky.calls == 3

    flaky = Flaky(*[ModelHTTPError(502, "a/b", "x")] * 5)
    with pytest.raises(ModelHTTPError):
        await run_with_attempts(plain_build, flaky.call, Attempts(retries=2, delay=0))
    assert flaky.calls == 3  # the first try and two retries, then the failure is final


@pytest.mark.asyncio
async def test_failures_that_will_not_pass_are_not_retried():
    from pydantic_ai.exceptions import ModelHTTPError

    for failure in (ModelHTTPError(400, "a/b", "bad model"), RuntimeError("a bug")):
        flaky = Flaky(failure, failure)
        with pytest.raises(type(failure)):
            await run_with_attempts(
                plain_build, flaky.call, Attempts(retries=2, delay=0)
            )
        assert flaky.calls == 1


@pytest.mark.asyncio
async def test_retries_wait_longer_each_time(monkeypatch):
    from pydantic_ai.exceptions import ModelHTTPError

    waits = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(resilience.asyncio, "sleep", fake_sleep)
    flaky = Flaky(ModelHTTPError(502, "a/b", "x"), ModelHTTPError(502, "a/b", "x"))
    await run_with_attempts(plain_build, flaky.call, Attempts(retries=2, delay=1.5))
    assert waits == [1.5, 3.0]


class FakeServer:
    def __init__(self, alive):
        self.alive = alive

    async def __aenter__(self):
        if not self.alive:
            import httpx

            raise ExceptionGroup(
                "connect", [httpx.ConnectError("All connection attempts failed")]
            )
        return self

    async def __aexit__(self, *exc):
        return None


@pytest.mark.asyncio
async def test_a_dead_mcp_server_is_left_out_and_the_request_goes_on():
    import httpx

    resilience.forget_down_servers()
    servers = {"alive": FakeServer(True), "dead": FakeServer(False)}
    built = []

    async def build(attempts):
        usable = [(k, s) for k, s in servers.items() if attempts.usable(k)]
        built.append([k for k, _ in usable])
        return "agent", usable

    async def call(agent):
        # the agent fails to start when a dead server is among its servers
        if "dead" in built[-1]:
            raise ExceptionGroup(
                "unhandled errors in a TaskGroup", [httpx.ConnectError("refused")]
            )
        return "answer"

    try:
        assert await run_with_attempts(build, call, Attempts(retries=0)) == "answer"
        assert built == [["alive", "dead"], ["alive"]]  # no retry was needed
        assert resilience.is_down("dead") and not resilience.is_down("alive")
        # and remembers why, for the model: the run is told which server is missing
        assert "ConnectError: All connection attempts failed" in resilience.down_reason(
            "dead"
        )

        # the next request does not even try the server that was found dead
        built.clear()
        assert await run_with_attempts(build, call, Attempts(retries=0)) == "answer"
        assert built == [["alive"]]
    finally:
        resilience.forget_down_servers()


@pytest.mark.asyncio
async def test_a_down_server_comes_back_after_a_while(monkeypatch):
    resilience.forget_down_servers()
    monkeypatch.setattr(resilience, "MCP_DOWN_SECONDS", 0.05)
    resilience.mark_down("x")
    assert resilience.is_down("x")
    await asyncio.sleep(0.1)
    assert not resilience.is_down("x")


@pytest.mark.asyncio
async def test_a_failure_that_is_not_the_servers_fault_is_not_blamed_on_them():
    resilience.forget_down_servers()
    alive = [("alive", FakeServer(True))]
    calls = []

    async def build(attempts):
        return "agent", alive

    async def call(agent):
        calls.append(1)
        if len(calls) == 1:
            import httpx

            raise httpx.ReadTimeout("slow")  # no MCP server is dead: retried as it is
        return "answer"

    assert (
        await run_with_attempts(build, call, Attempts(retries=1, delay=0)) == "answer"
    )
    assert len(calls) == 2 and not resilience.is_down("alive")


class FakeApp:
    def __init__(self, pool):
        self.state = SimpleNamespace(db_pool=pool)


class FakeRequest:
    def __init__(self, pool):
        self.app = FakeApp(pool)


@pytest.mark.asyncio
async def test_readiness_is_503_without_a_pool_or_a_database():
    import json as _json
    from routers.health import readyz

    res = await readyz(FakeRequest(None))
    assert res.status_code == 503 and _json.loads(res.body)["status"] == "starting"

    class BrokenPool:
        class pool:  # noqa: N801
            @staticmethod
            def acquire():
                raise ConnectionRefusedError("database is down")

    res = await readyz(FakeRequest(BrokenPool()))
    body = _json.loads(res.body)
    assert res.status_code == 503 and body["status"] == "database unavailable"
    assert body["detail"] == "ConnectionRefusedError"


@pytest.mark.asyncio
async def test_readiness_reports_a_database_that_is_behind(monkeypatch):
    import json as _json
    from routers import health

    class Connection:
        async def fetchval(self, query):
            return 2  # applied

    class Acquire:
        async def __aenter__(self):
            return Connection()

        async def __aexit__(self, *exc):
            return None

    class Pool:
        class pool:  # noqa: N801
            @staticmethod
            def acquire():
                return Acquire()

    res = await health.readyz(FakeRequest(Pool()))
    body = _json.loads(res.body)
    assert res.status_code == 503 and body["status"] == "migrating"
    assert body["migration"] == 2 and body["expected"] == list_migrations()[-1][0]


def test_metrics_page_renders_the_families():
    from core import metrics

    body, content_type = metrics.render()
    assert content_type.startswith("text/plain")
    assert b"omnixon_http_requests_total" in body and b"omnixon_active_streams" in body
