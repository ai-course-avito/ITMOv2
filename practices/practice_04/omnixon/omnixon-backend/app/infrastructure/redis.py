"""Interrupting a stream that runs in another replica.

Every replica of the api keeps the streams it runs in its `InterruptRegistry`. With REDIS_URL set, a running stream also holds a key
`omnixon:stream:<agent>:<user>` (the replica that owns it, with a short life that the replica keeps renewing: a replica that dies leaves
nothing behind for long). To stop a stream that is not here, a replica asks all of them on the channel `omnixon:stop`; the one that owns the
stream stops it (the same way a local stop does: told to stop, waits until it has saved) and answers on `omnixon:stopped:<request id>` with
what was said. Without REDIS_URL the `LocalStopBus` does nothing and an interrupt only reaches the streams of its own process.
"""

import asyncio
import json
import uuid
from typing import Awaitable, Callable, Optional, Protocol, Tuple

import logfire
import redis.asyncio as redis

Key = Tuple[int, int]  # (agent id, user id)

STOP_CHANNEL = "omnixon:stop"
KEY_LIFE_SECONDS = 30
KEY_RENEW_SECONDS = 10


def stream_key(key: Key) -> str:
    return f"omnixon:stream:{key[0]}:{key[1]}"


class StopBus(Protocol):
    """How replicas reach each other's streams."""

    shared: bool  # whether there are other replicas to reach

    async def hold(self, key: Key) -> None: ...
    async def owner_of(self, key: Key) -> Optional[str]: ...
    async def ask_stop(self, key: Key, timeout: float) -> Optional[str]: ...
    async def serve(self, stop_here: Callable[[Key], Awaitable[Optional[str]]]) -> None: ...
    async def close(self) -> None: ...


class LocalStopBus:
    """One process: a stop only reaches the streams of this process."""

    shared = False

    async def hold(self, key: Key) -> None:
        await asyncio.Event().wait()

    async def owner_of(self, key: Key) -> Optional[str]:
        return None

    async def ask_stop(self, key: Key, timeout: float) -> Optional[str]:
        return None

    async def serve(self, stop_here) -> None:
        await asyncio.Event().wait()

    async def close(self) -> None:
        return None


class RedisStopBus:
    shared = True

    def __init__(self, client: redis.Redis):
        self.client = client
        self.instance = uuid.uuid4().hex

    @classmethod
    def from_url(cls, url: str) -> "RedisStopBus":
        return cls(redis.from_url(url, decode_responses=True))

    async def close(self) -> None:
        await self.client.aclose()

    async def hold(self, key: Key) -> None:
        """Say this replica runs the stream `key`, until cancelled (then the claim is taken back)."""
        name = stream_key(key)
        try:
            while True:
                try:
                    await self.client.set(name, self.instance, ex=KEY_LIFE_SECONDS)
                except redis.RedisError as error:  # the stream goes on; it just cannot be stopped from elsewhere for now
                    logfire.warning("Redis: cannot claim a stream: {error}", error=str(error))
                await asyncio.sleep(KEY_RENEW_SECONDS)
        finally:
            try:
                if await self.client.get(name) == self.instance:
                    await self.client.delete(name)
            except redis.RedisError:
                pass

    async def owner_of(self, key: Key) -> Optional[str]:
        try:
            return await self.client.get(stream_key(key))
        except redis.RedisError:
            return None

    async def ask_stop(self, key: Key, timeout: float) -> Optional[str]:
        """Ask the replica that runs the stream `key` to stop it and wait for it: what was said (maybe ""), or None if nobody answered."""
        request = uuid.uuid4().hex
        reply = f"omnixon:stopped:{request}"
        pubsub = self.client.pubsub()
        try:
            await pubsub.subscribe(reply)
            await self.client.publish(STOP_CHANNEL, json.dumps({"key": list(key), "reply": reply}))
            async with asyncio.timeout(timeout):
                while True:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message is not None:
                        return json.loads(message["data"])["text"]
        except TimeoutError:
            return None
        except redis.RedisError as error:
            logfire.warning("Redis: cannot ask for a stop: {error}", error=str(error))
            return None
        finally:
            await pubsub.aclose()

    async def serve(self, stop_here: Callable[[Key], Awaitable[Optional[str]]]) -> None:
        """Answer the stop requests of other replicas until cancelled. `stop_here(key)` stops the stream of this process and returns what
        was said, or None if this process has no such stream."""
        pubsub = self.client.pubsub()
        await pubsub.subscribe(STOP_CHANNEL)
        try:
            while True:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                except redis.RedisError as error:
                    logfire.warning("Redis: the stop channel failed: {error}", error=str(error))
                    await asyncio.sleep(1)
                    continue
                if message is None:
                    continue
                request = json.loads(message["data"])
                text = await stop_here((request["key"][0], request["key"][1]))
                if text is not None:
                    await self.client.publish(request["reply"], json.dumps({"text": text}))
        finally:
            await pubsub.aclose()
