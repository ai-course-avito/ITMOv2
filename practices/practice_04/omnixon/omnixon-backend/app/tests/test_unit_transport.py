"""unit transport tests: a provider that drops a request or is busy is asked again, under the model client (ai/transport.py)"""

import asyncio

import httpx2
import pytest

from infrastructure import transport
from infrastructure.transport import RetryingTransport, retry_after


@pytest.fixture
def waits(monkeypatch):
    seen = []

    async def sleep(seconds):
        seen.append(seconds)

    monkeypatch.setattr(transport.asyncio, "sleep", sleep)
    return seen


def client_for(*outcomes, retries=2, delay=1.0):
    """A client whose server answers with the outcomes in turn (a response, or an exception to raise)."""
    calls = []

    def handler(request):
        calls.append(request)
        outcome = outcomes[min(len(calls), len(outcomes)) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    return httpx2.AsyncClient(transport=RetryingTransport(httpx2.MockTransport(handler), retries, delay)), calls


def status(code, **headers):
    return httpx2.Response(code, headers=headers, text=f"status {code}")


@pytest.mark.asyncio
async def test_a_busy_provider_is_asked_again_with_growing_pauses(waits):
    client, calls = client_for(status(503), status(429), status(200))
    response = await client.post("http://llm/chat", json={})
    assert response.status_code == 200 and len(calls) == 3
    assert waits == [1.0, 2.0]


@pytest.mark.asyncio
async def test_the_last_answer_is_handed_on_as_it_is(waits):
    client, calls = client_for(status(502))
    response = await client.post("http://llm/chat", json={})
    assert response.status_code == 502 and response.text == "status 502"  # the client sees the provider's own status
    assert len(calls) == 3  # the first try and two more


@pytest.mark.asyncio
async def test_what_will_not_pass_is_not_asked_again(waits):
    for code in (400, 401, 402, 403, 404, 422):
        client, calls = client_for(status(code))
        assert (await client.post("http://llm/chat", json={})).status_code == code
        assert len(calls) == 1
    assert waits == []


@pytest.mark.asyncio
async def test_a_connection_that_fails_is_retried_and_then_raised(waits):
    client, calls = client_for(httpx2.ConnectError("refused"), status(200))
    assert (await client.post("http://llm/chat", json={})).status_code == 200 and len(calls) == 2

    client, calls = client_for(httpx2.ReadTimeout("slow"))
    with pytest.raises(httpx2.ReadTimeout):
        await client.post("http://llm/chat", json={})
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_the_pause_the_provider_asks_for_wins_but_is_capped(waits):
    client, _ = client_for(status(429, **{"Retry-After": "7"}), status(429, **{"Retry-After": "3600"}), status(200))
    await client.post("http://llm/chat", json={})
    assert waits == [7.0, transport.MAX_WAIT_SECONDS]


def test_retry_after_reads_seconds_dates_and_nonsense():
    assert retry_after(status(429, **{"Retry-After": "2.5"})) == 2.5
    assert retry_after(status(429)) is None
    assert retry_after(status(429, **{"Retry-After": "soon"})) is None
    assert retry_after(status(429, **{"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"})) == 0.0  # in the past: no wait


@pytest.mark.asyncio
async def test_retries_can_be_switched_off(waits):
    client, calls = client_for(status(503), retries=0)
    assert (await client.post("http://llm/chat", json={})).status_code == 503 and len(calls) == 1
    assert asyncio.iscoroutinefunction(RetryingTransport.aclose)
