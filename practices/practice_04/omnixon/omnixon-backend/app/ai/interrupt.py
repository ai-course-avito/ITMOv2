"""Stopping an answer that is being streamed.

A stream is registered under (agent, user) while it runs. `stop` ends it: the client gets `event: interrupted`, what was said so far goes into the
history (marked `interrupted`) and into the memory like any exchange, and only then does `stop` return, so whatever comes next (a new request of the
same user to the same agent) starts from a history that has it. A new request does exactly that before it reads the history, so a user who writes
again while the answer is still coming simply cuts it off.

The registry lives in the process. With several replicas (Swarm) REDIS_URL makes an interrupt reach a stream that runs in another one:
see `interrupt_bus`. Without it an interrupt only reaches the streams of the process that gets it.
"""

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, List, Optional, Tuple, TypeVar

import logfire

from core import metrics

from .interrupt_bus import InterruptBus

T = TypeVar("T")
Key = Tuple[int, int]  # (agent id, user id)

STOP_TIMEOUT_SECONDS = 15


@dataclass
class ActiveStream:
    key: Key
    wanted: asyncio.Event = field(default_factory=asyncio.Event)  # someone asked it to stop
    finished: asyncio.Event = field(default_factory=asyncio.Event)  # and it has: saved and closed
    partial: List[str] = field(default_factory=list)  # the text sent so far
    interrupted: bool = False
    holding: Optional[asyncio.Task] = None  # keeps the claim on this stream in Redis

    @property
    def text(self) -> str:
        return "".join(self.partial)


_active: Dict[Key, ActiveStream] = {}
bus: Optional[InterruptBus] = None  # set at start when REDIS_URL is
current: ContextVar[Optional[ActiveStream]] = ContextVar("current_stream", default=None)


def start(key: Key) -> ActiveStream:
    stream = ActiveStream(key)
    _active[key] = stream
    if bus is not None:
        stream.holding = asyncio.ensure_future(bus.hold(key))
    return stream


def end(stream: ActiveStream) -> None:
    if _active.get(stream.key) is stream:
        del _active[stream.key]
    stream.finished.set()
    if stream.holding is not None:
        stream.holding.cancel()


async def stop(agent_id: int, user_id: int) -> Optional[ActiveStream]:
    """Stop the stream of this user with this agent, if there is one (in this process, or in another replica), and wait until it has been
    saved. None: there was none."""
    stream = _active.get((agent_id, user_id))
    if stream is None or stream.finished.is_set():
        return await _stop_elsewhere((agent_id, user_id))
    return await _stop_here(stream)


async def _stop_elsewhere(key: Key) -> Optional[ActiveStream]:
    if bus is None or await bus.owner_of(key) is None:
        return None
    text = await bus.ask_stop(key, STOP_TIMEOUT_SECONDS + 2)
    if text is None:
        return None
    stopped = ActiveStream(key, interrupted=True)  # counted by the replica that stopped it
    stopped.partial.append(text)
    return stopped


async def stop_for_replica(key: Key) -> Optional[str]:
    """A stop asked for by another replica: stop the stream here if it is here; what it had said, or None."""
    stream = _active.get(key)
    if stream is None or stream.finished.is_set():
        return None
    return (await _stop_here(stream)).text


async def _stop_here(stream: ActiveStream) -> ActiveStream:
    stream.interrupted = True
    stream.wanted.set()
    try:
        await asyncio.wait_for(stream.finished.wait(), STOP_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logfire.warning("A stream did not finish {seconds}s after it was told to stop", seconds=STOP_TIMEOUT_SECONDS)
    metrics.STREAMS_INTERRUPTED.inc()
    return stream


_DONE = object()


async def until_stopped(items: AsyncIterator[T], stream: ActiveStream) -> AsyncIterator[T]:
    """The items of `items`, until the stream is told to stop: then the wait for the next one is cancelled at once (a model that is
    thinking is not waited for).

    `items` runs in ONE task of its own, start to end, and hands its items over through a queue: the async generators of pydantic-ai
    keep anyio cancel scopes, which must be entered and left by the same task (a task per item breaks them)."""
    queue: asyncio.Queue = asyncio.Queue()

    async def produce() -> None:
        try:
            async for item in items:
                await queue.put((item, None))
            await queue.put((_DONE, None))
        except asyncio.CancelledError:
            raise
        except BaseException as error:  # handed to the consumer, who raises it where the stream is read
            await queue.put((_DONE, error))

    producer = asyncio.ensure_future(produce())
    waiter = asyncio.ensure_future(stream.wanted.wait())
    try:
        while True:
            following = asyncio.ensure_future(queue.get())
            try:
                done, _ = await asyncio.wait({following, waiter}, return_when=asyncio.FIRST_COMPLETED)
            finally:
                if not following.done():
                    following.cancel()
            if following not in done or following.cancelled():
                return
            item, error = following.result()
            if item is _DONE:
                if error is not None:
                    raise error
                return
            yield item
    finally:
        waiter.cancel()
        producer.cancel()
        await asyncio.gather(producer, waiter, return_exceptions=True)
