"""Stopping an answer that is being streamed.

A stream is registered under (agent, user) while it runs. `stop` ends it: the client gets `event: interrupted`, what was said so far goes into the
history (marked `interrupted`) and into the memory like any exchange, and only then does `stop` return, so whatever comes next (a new request of the
same user to the same agent) starts from a history that has it. A new request does exactly that before it reads the history, so a user who writes
again while the answer is still coming simply cuts it off.

The registry belongs to a process; with several replicas (Swarm) its `StopBus` makes an interrupt reach a stream that runs in another one.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, List, Optional, TypeVar

import logfire

from core import metrics
from infrastructure.redis import Key, StopBus

T = TypeVar("T")

_current: ContextVar[Optional["ActiveStream"]] = ContextVar("current_stream", default=None)


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


class InterruptRegistry:
    def __init__(self, bus: StopBus, stop_timeout: float = 15):
        self.bus = bus
        self.stop_timeout = stop_timeout
        self._active: Dict[Key, ActiveStream] = {}

    @staticmethod
    def current() -> Optional[ActiveStream]:
        """The stream the running request is (the context of the task that runs it)."""
        return _current.get()

    def start(self, key: Key) -> ActiveStream:
        stream = ActiveStream(key)
        self._active[key] = stream
        _current.set(stream)
        if self.bus.shared:
            stream.holding = asyncio.ensure_future(self.bus.hold(key))
        return stream

    def end(self, stream: ActiveStream) -> None:
        if self._active.get(stream.key) is stream:
            del self._active[stream.key]
        stream.finished.set()
        if stream.holding is not None:
            stream.holding.cancel()

    async def stop(self, agent_id: int, user_id: int) -> Optional[ActiveStream]:
        """Stop the stream of this user with this agent, if there is one (in this process, or in another replica), and wait until it has
        been saved. None: there was none."""
        stream = self._active.get((agent_id, user_id))
        if stream is None or stream.finished.is_set():
            return await self._stop_elsewhere((agent_id, user_id))
        return await self._stop_here(stream)

    async def _stop_elsewhere(self, key: Key) -> Optional[ActiveStream]:
        if await self.bus.owner_of(key) is None:
            return None
        text = await self.bus.ask_stop(key, self.stop_timeout + 2)
        if text is None:
            return None
        stopped = ActiveStream(key, interrupted=True)  # counted by the replica that stopped it
        stopped.partial.append(text)
        return stopped

    async def stop_for_replica(self, key: Key) -> Optional[str]:
        """A stop asked for by another replica: stop the stream here if it is here; what it had said, or None."""
        stream = self._active.get(key)
        if stream is None or stream.finished.is_set():
            return None
        return (await self._stop_here(stream)).text

    async def _stop_here(self, stream: ActiveStream) -> ActiveStream:
        stream.interrupted = True
        stream.wanted.set()
        try:
            await asyncio.wait_for(stream.finished.wait(), self.stop_timeout)
        except asyncio.TimeoutError:
            logfire.warning("A stream did not finish {seconds}s after it was told to stop", seconds=self.stop_timeout)
        metrics.STREAMS_INTERRUPTED.inc()
        return stream

    async def serve(self) -> None:
        """Answer the stop requests of other replicas until cancelled."""
        await self.bus.serve(self.stop_for_replica)

    async def aclose(self) -> None:
        for stream in list(self._active.values()):
            self.end(stream)
        await self.bus.close()


_DONE = object()


class StreamGuard:
    """Hands over the items of a source until the stream is told to stop; then the wait for the next one is cancelled at once (a model that
    is thinking is not waited for).

    The source runs in ONE task of its own, start to end, and hands its items over through a queue: the async generators of pydantic-ai keep
    anyio cancel scopes, which must be entered and left by the same task (a task per item breaks them)."""

    @staticmethod
    async def items(source: AsyncIterator[T], stream: ActiveStream) -> AsyncIterator[T]:
        queue: asyncio.Queue = asyncio.Queue()

        async def produce() -> None:
            try:
                async for item in source:
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
