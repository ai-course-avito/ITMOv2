"""unit interrupt bus tests: a stream that runs in one replica is stopped from another (Redis, here fakeredis)"""

import asyncio

import fakeredis
import pytest

from ai import interrupt
from ai.interrupt_bus import InterruptBus, stream_key


@pytest.fixture
def replicas(monkeypatch):
    """Two replicas on one Redis: (bus of the one that runs the stream, bus of the one that is asked to stop it)."""
    server = fakeredis.FakeServer()
    a = InterruptBus(fakeredis.FakeAsyncRedis(server=server, decode_responses=True))
    b = InterruptBus(fakeredis.FakeAsyncRedis(server=server, decode_responses=True))
    monkeypatch.setattr(interrupt, "STOP_TIMEOUT_SECONDS", 1)
    yield a, b
    interrupt.bus = None
    interrupt._active.clear()


async def running_stream(bus, key, said="word0 word1 "):
    """A stream of replica `bus`, as request.py runs it: it says something, and when told to stop saves and finishes."""
    interrupt.bus = bus
    stream = interrupt.start(key)
    stream.partial.append(said)

    async def consumer():
        await stream.wanted.wait()
        await asyncio.sleep(0.05)  # saving the history
        interrupt.end(stream)

    return stream, asyncio.ensure_future(consumer())


@pytest.mark.asyncio
async def test_a_stream_of_another_replica_is_stopped_and_what_it_said_comes_back(replicas):
    a, b = replicas
    key = (3, 7)
    stream, consumer = await running_stream(a, key)
    server = asyncio.ensure_future(a.serve(interrupt.stop_for_replica))
    await asyncio.sleep(0.2)  # subscribed, and the claim is made
    assert await b.owner_of(key) == a.instance

    interrupt.bus = b  # the replica that gets the Stop knows nothing of the stream: it is not in its registry
    stopped = await interrupt._stop_elsewhere(key)

    assert stopped is not None and stopped.text == "word0 word1 " and stream.interrupted
    assert stream.finished.is_set()  # saved before the answer came back
    await consumer
    await asyncio.sleep(0.1)
    assert await b.owner_of(key) is None  # the claim is gone with the stream
    server.cancel()
    await asyncio.gather(server, return_exceptions=True)


@pytest.mark.asyncio
async def test_nobody_runs_the_stream_nothing_is_waited_for(replicas):
    a, b = replicas
    interrupt.bus = b
    started = asyncio.get_running_loop().time()
    assert await interrupt.stop(3, 7) is None
    assert asyncio.get_running_loop().time() - started < 0.5  # no claim: no request


@pytest.mark.asyncio
async def test_a_claim_nobody_answers_for_gives_up_after_the_timeout(replicas):
    a, b = replicas
    await a.client.set(stream_key((3, 7)), "a-replica-that-died", ex=30)
    interrupt.bus = b
    assert await interrupt.stop(3, 7) is None  # waited STOP_TIMEOUT_SECONDS + 2, then gave up


@pytest.mark.asyncio
async def test_without_redis_a_stop_only_reaches_the_streams_of_the_process():
    interrupt.bus = None
    stream = interrupt.start((1, 1))
    assert interrupt.bus is None and stream.holding is None
    stopping = asyncio.ensure_future(interrupt.stop(1, 1))
    await asyncio.sleep(0.05)
    assert stream.wanted.is_set()
    interrupt.end(stream)
    assert (await stopping) is stream
    assert await interrupt.stop(2, 2) is None
    interrupt._active.clear()
