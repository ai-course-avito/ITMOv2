"""unit interrupt tests: the registry, the guard of a stream, and a stop that reaches another replica (fakeredis)"""

import asyncio

import fakeredis
import pytest

from ai.interrupts import InterruptRegistry, StreamGuard
from infrastructure.redis import LocalStopBus, RedisStopBus, stream_key


def local(timeout=15):
    return InterruptRegistry(LocalStopBus(), stop_timeout=timeout)


async def stream_of(texts, delay=0.0):
    for text in texts:
        await asyncio.sleep(delay)
        yield text


async def collect(items):
    return [item async for item in items]


@pytest.mark.asyncio
async def test_a_stream_that_is_not_stopped_passes_everything_through():
    registry = local()
    stream = registry.start((1, 2))
    try:
        assert await collect(StreamGuard.items(stream_of(["a", "b", "c"]), stream)) == ["a", "b", "c"]
        assert stream.interrupted is False
    finally:
        registry.end(stream)


@pytest.mark.asyncio
async def test_stopping_cancels_the_wait_for_the_next_piece_at_once():
    registry = local()

    async def thinking():
        yield "first"
        await asyncio.sleep(60)  # a model that is thinking
        yield "never"

    stream = registry.start((1, 3))
    seen = []

    async def run():
        async for piece in StreamGuard.items(thinking(), stream):
            seen.append(piece)
            stream.partial.append(piece)
        stream.finished.set()

    task = asyncio.create_task(run())
    try:
        while not seen:
            await asyncio.sleep(0.01)
        started = asyncio.get_event_loop().time()
        stopped = await registry.stop(1, 3)
        assert stopped is stream and stream.interrupted and stream.text == "first"
        assert asyncio.get_event_loop().time() - started < 2  # not a minute
        await asyncio.wait_for(task, 2)
        assert seen == ["first"]
    finally:
        registry.end(stream)


@pytest.mark.asyncio
async def test_there_is_nothing_to_stop_for_an_idle_or_other_user_or_agent():
    registry = local()
    assert await registry.stop(9, 9) is None
    stream = registry.start((5, 6))
    try:
        assert await registry.stop(5, 7) is None and await registry.stop(4, 6) is None  # other user, other agent
        assert not stream.wanted.is_set()
    finally:
        registry.end(stream)
    assert await registry.stop(5, 6) is None  # it has ended
    assert (5, 6) not in registry._active


@pytest.mark.asyncio
async def test_stop_waits_until_the_stream_has_been_saved_but_not_for_ever():
    registry = local(timeout=0.5)
    stream = registry.start((7, 8))
    order = []

    async def saver():
        await stream.wanted.wait()
        await asyncio.sleep(0.2)  # saving takes a while
        order.append("saved")
        stream.finished.set()

    task = asyncio.create_task(saver())
    stopped = await registry.stop(7, 8)
    order.append("returned")
    assert stopped is stream and order == ["saved", "returned"]
    await task
    registry.end(stream)

    registry.stop_timeout = 0.1  # a stream that never finishes does not hold the new request for ever
    stuck = registry.start((7, 9))
    assert await registry.stop(7, 9) is stuck
    registry.end(stuck)


@pytest.mark.asyncio
async def test_a_new_stream_of_the_same_pair_replaces_the_old_one_in_the_registry():
    registry = local()
    first, second = registry.start((2, 2)), registry.start((2, 2))
    registry.end(first)  # the old one ending must not unregister the new one
    assert registry._active[(2, 2)] is second
    registry.end(second)
    assert (2, 2) not in registry._active


@pytest.mark.asyncio
async def test_the_registry_of_a_request_knows_its_stream_and_two_registries_do_not_share_streams():
    a, b = local(), local()
    stream = a.start((1, 1))
    assert InterruptRegistry.current() is stream and await b.stop(1, 1) is None  # b has nothing of a's
    a.end(stream)


# -- two replicas on one Redis ------------------------------------------------------------------------------------------------


@pytest.fixture
def replicas():
    """Two replicas on one Redis: (registry of the one that runs the stream, registry of the one that is asked to stop it)."""
    server = fakeredis.FakeServer()
    a = InterruptRegistry(RedisStopBus(fakeredis.FakeAsyncRedis(server=server, decode_responses=True)), stop_timeout=1)
    b = InterruptRegistry(RedisStopBus(fakeredis.FakeAsyncRedis(server=server, decode_responses=True)), stop_timeout=1)
    return a, b


async def running_stream(registry, key, said="word0 word1 "):
    """A stream of replica `registry`, as the conversation runs it: it says something, and when told to stop saves and finishes."""
    stream = registry.start(key)
    stream.partial.append(said)

    async def consumer():
        await stream.wanted.wait()
        await asyncio.sleep(0.05)  # saving the history
        registry.end(stream)

    return stream, asyncio.ensure_future(consumer())


@pytest.mark.asyncio
async def test_a_stream_of_another_replica_is_stopped_and_what_it_said_comes_back(replicas):
    a, b = replicas
    key = (3, 7)
    stream, consumer = await running_stream(a, key)
    server = asyncio.ensure_future(a.serve())
    await asyncio.sleep(0.2)  # subscribed, and the claim is made
    assert await b.bus.owner_of(key) == a.bus.instance

    stopped = await b._stop_elsewhere(key)  # b knows nothing of the stream: it is not in its registry
    assert stopped is not None and stopped.text == "word0 word1 " and stream.interrupted
    assert stream.finished.is_set()  # saved before the answer came back
    await consumer
    await asyncio.sleep(0.1)
    assert await b.bus.owner_of(key) is None  # the claim is gone with the stream
    server.cancel()
    await asyncio.gather(server, return_exceptions=True)


@pytest.mark.asyncio
async def test_nobody_runs_the_stream_nothing_is_waited_for(replicas):
    a, b = replicas
    started = asyncio.get_running_loop().time()
    assert await b.stop(3, 7) is None
    assert asyncio.get_running_loop().time() - started < 0.5  # no claim: no request


@pytest.mark.asyncio
async def test_a_claim_nobody_answers_for_gives_up_after_the_timeout(replicas):
    a, b = replicas
    await a.bus.client.set(stream_key((3, 7)), "a-replica-that-died", ex=30)
    assert await b.stop(3, 7) is None  # waited the timeout + 2, then gave up


@pytest.mark.asyncio
async def test_closing_the_registry_ends_its_streams_and_closes_the_bus(replicas):
    a, _ = replicas
    stream = a.start((8, 8))
    await a.aclose()
    assert stream.finished.is_set() and a._active == {}


@pytest.mark.asyncio
async def test_the_source_of_a_stream_runs_in_one_task_from_start_to_end():
    """pydantic-ai's generators keep anyio cancel scopes, which break when the pieces are pulled by different tasks."""
    import anyio

    registry, tasks = local(), set()

    async def source():
        with anyio.CancelScope():  # entered by the first pull, left by the last: the same task or it raises
            for n in range(3):
                tasks.add(asyncio.current_task())
                await asyncio.sleep(0)
                yield n

    stream = registry.start((1, 11))
    try:
        assert await collect(StreamGuard.items(source(), stream)) == [0, 1, 2]
        assert len(tasks) == 1 and asyncio.current_task() not in tasks
    finally:
        registry.end(stream)


@pytest.mark.asyncio
async def test_a_failure_of_the_source_reaches_the_reader_and_a_closed_reader_stops_the_source():
    registry = local()

    async def failing():
        yield "a"
        raise ValueError("boom")

    stream = registry.start((1, 12))
    try:
        seen = []
        with pytest.raises(ValueError, match="boom"):
            async for piece in StreamGuard.items(failing(), stream):
                seen.append(piece)
        assert seen == ["a"]

        closed = asyncio.Event()

        async def endless():
            try:
                while True:
                    await asyncio.sleep(0.01)
                    yield "x"
            finally:
                closed.set()

        reader = StreamGuard.items(endless(), stream)
        assert await reader.__anext__() == "x"
        await reader.aclose()  # the client went away
        await asyncio.wait_for(closed.wait(), 2)  # the source was cancelled, not left running
    finally:
        registry.end(stream)
