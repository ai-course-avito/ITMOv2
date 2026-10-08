"""unit interrupt tests"""

import asyncio
import json
from datetime import datetime
import pytest
from ai import utils as ai_utils

from shared import (
    scratch_database,
)


async def stream_of(texts, delay=0.0):
    for text in texts:
        await asyncio.sleep(delay)
        yield text


async def collect(items):
    return [item async for item in items]


@pytest.mark.asyncio
async def test_a_stream_that_is_not_stopped_passes_everything_through():
    from ai import interrupt

    stream = interrupt.start((1, 2))
    try:
        assert await collect(
            interrupt.until_stopped(stream_of(["a", "b", "c"]), stream)
        ) == ["a", "b", "c"]
        assert stream.interrupted is False
    finally:
        interrupt.end(stream)


@pytest.mark.asyncio
async def test_stopping_cancels_the_wait_for_the_next_piece_at_once():
    from ai import interrupt

    async def thinking():
        yield "first"
        await asyncio.sleep(60)  # a model that is thinking
        yield "never"

    stream = interrupt.start((1, 3))
    seen = []

    async def run():
        async for piece in interrupt.until_stopped(thinking(), stream):
            seen.append(piece)
            stream.partial.append(piece)
        stream.finished.set()

    task = asyncio.create_task(run())
    try:
        while not seen:
            await asyncio.sleep(0.01)
        started = asyncio.get_event_loop().time()
        stopped = await interrupt.stop(1, 3)
        assert stopped is stream and stream.interrupted and stream.text == "first"
        assert asyncio.get_event_loop().time() - started < 2  # not a minute
        await asyncio.wait_for(task, 2)
        assert seen == ["first"]
    finally:
        interrupt.end(stream)


@pytest.mark.asyncio
async def test_there_is_nothing_to_stop_for_an_idle_or_other_user_or_agent(monkeypatch):
    from ai import interrupt

    assert await interrupt.stop(9, 9) is None
    stream = interrupt.start((5, 6))
    try:
        assert (
            await interrupt.stop(5, 7) is None and await interrupt.stop(4, 6) is None
        )  # other user, other agent
        assert not stream.wanted.is_set()
    finally:
        interrupt.end(stream)
    assert await interrupt.stop(5, 6) is None  # it has ended
    assert (5, 6) not in interrupt._active


@pytest.mark.asyncio
async def test_stop_waits_until_the_stream_has_been_saved(monkeypatch):
    from ai import interrupt

    stream = interrupt.start((7, 8))
    order = []

    async def saver():
        await stream.wanted.wait()
        await asyncio.sleep(0.2)  # saving takes a while
        order.append("saved")
        stream.finished.set()

    task = asyncio.create_task(saver())
    stopped = await interrupt.stop(7, 8)
    order.append("returned")
    assert stopped is stream and order == ["saved", "returned"]
    await task
    interrupt.end(stream)

    # a stream that never finishes does not hold the new request for ever
    monkeypatch.setattr(interrupt, "STOP_TIMEOUT_SECONDS", 0.1)
    stuck = interrupt.start((7, 9))
    assert await interrupt.stop(7, 9) is stuck
    interrupt.end(stuck)


@pytest.mark.asyncio
async def test_a_new_stream_of_the_same_pair_replaces_the_old_one_in_the_registry():
    from ai import interrupt

    first = interrupt.start((2, 2))
    second = interrupt.start((2, 2))
    interrupt.end(first)  # the old one ending must not unregister the new one
    assert interrupt._active[(2, 2)] is second
    interrupt.end(second)
    assert (2, 2) not in interrupt._active


@pytest.mark.asyncio
async def test_an_interrupted_exchange_is_saved_with_what_was_said_and_remembered(
    monkeypatch,
):
    from ai import runner

    async with scratch_database("interrupt_save_test") as (pool, db):
        learned = []

        async def learn(db_, user_input, answer):
            learned.append((user_input, answer))

        monkeypatch.setattr(runner, "_learn", learn)
        await runner.save_interrupted(db, "count to ten", "one two three")
        rows = [
            json.loads(r["content"])
            for r in await pool.pool.fetch("SELECT content FROM messages ORDER BY id")
        ]
        assert [(r["type"], r["content"]) for r in rows] == [
            ("user", "count to ten"),
            ("assistant", "one two three"),
        ]
        assert rows[1]["interrupted"] is True and "interrupted" not in rows[0]
        assert learned == [("count to ten", "one two three")]

        # nothing said yet: only the question is kept, and there is nothing to learn from
        await runner.save_interrupted(db, "second question", "  \n")
        rows = [
            json.loads(r["content"])
            for r in await pool.pool.fetch("SELECT content FROM messages ORDER BY id")
        ]
        assert [r["type"] for r in rows] == ["user", "assistant", "user"] and rows[-1][
            "content"
        ] == "second question"
        assert len(learned) == 1


@pytest.mark.asyncio
async def test_a_cut_answer_is_given_to_the_model_as_an_answer_of_its_own(monkeypatch):
    from ai import runner

    async with scratch_database("interrupt_history_test") as (pool, db):

        async def learn(*args):
            pass

        monkeypatch.setattr(runner, "_learn", learn)
        await runner.save_interrupted(db, "count to ten", "one two three")
        history = await ai_utils.get_conversation_history(db)
        assert [type(m).__name__ for m in history][-2:] == [
            "ModelRequest",
            "ModelResponse",
        ]
        assert "one two three" in str(history[-1])


@pytest.mark.asyncio
async def test_an_interrupted_call_is_logged_as_interrupted_and_not_as_an_error():
    from ai import interrupt
    from ai.usage import track_usage

    async with scratch_database("usage_interrupt_test") as (pool, db):
        stream = interrupt.start((db.context.agent.id, 1))
        token = interrupt.current.set(stream)
        try:
            stream.interrupted = True
            with pytest.raises(GeneratorExit):
                async with track_usage(db, "stream", "a/model"):
                    raise GeneratorExit()
        finally:
            interrupt.current.reset(token)
            interrupt.end(stream)
        # a cancellation that nobody asked for stays "cancelled"
        with pytest.raises(asyncio.CancelledError):
            async with track_usage(db, "stream", "a/model"):
                raise asyncio.CancelledError()
        assert [
            r["status"]
            for r in await pool.pool.fetch("SELECT status FROM usage_logs ORDER BY id")
        ] == ["interrupted", "cancelled"]
        today = datetime.now().date()
        rows = await db.usage_daily(today, today)
        assert (
            sum(r["requests"] for r in rows) == 2
            and sum(r["errors"] for r in rows) == 1
        )  # only the cancelled one is an error


@pytest.mark.asyncio
async def test_the_source_of_a_stream_runs_in_one_task_from_start_to_end():
    """pydantic-ai's generators keep anyio cancel scopes, which break when the pieces are pulled by different tasks."""
    import anyio
    from ai import interrupt

    tasks = set()

    async def source():
        with (
            anyio.CancelScope()
        ):  # entered by the first pull, left by the last: the same task or it raises
            for n in range(3):
                tasks.add(asyncio.current_task())
                await asyncio.sleep(0)
                yield n

    stream = interrupt.start((1, 11))
    try:
        assert await collect(interrupt.until_stopped(source(), stream)) == [0, 1, 2]
        assert len(tasks) == 1 and asyncio.current_task() not in tasks
    finally:
        interrupt.end(stream)


@pytest.mark.asyncio
async def test_a_failure_of_the_source_reaches_the_reader_and_a_closed_reader_stops_the_source():
    from ai import interrupt

    async def failing():
        yield "a"
        raise ValueError("boom")

    stream = interrupt.start((1, 12))
    try:
        seen = []
        with pytest.raises(ValueError, match="boom"):
            async for piece in interrupt.until_stopped(failing(), stream):
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

        reader = interrupt.until_stopped(endless(), stream)
        assert await reader.__anext__() == "x"
        await reader.aclose()  # the client went away
        await asyncio.wait_for(
            closed.wait(), 2
        )  # the source was cancelled, not left running
    finally:
        interrupt.end(stream)
