"""unit chats tests: the threads of a user, the default chat, the titles, and migration 13 on old data"""

import json

import pytest
from database import Chat
from database.foundation import (
    MIGRATIONS_DIR,
    apply_migrations,
    list_migrations,
)

from shared import (
    scratch_database,
)


def test_a_chat_without_a_title_has_a_name_all_the_same():
    from datetime import datetime

    now = datetime(2026, 1, 1)
    plain = Chat(id=7, user_id=1, title=None, timestamp=now, updated_at=now)
    assert plain.title == "Chat 7"
    assert Chat(id=8, user_id=1, is_default=True, timestamp=now, updated_at=now).title == "Default chat"
    assert Chat(id=9, user_id=1, title="  Prices  ", timestamp=now, updated_at=now).title == "  Prices  "  # a given title wins


@pytest.mark.asyncio
async def test_the_default_chat_is_made_once_and_is_the_same_for_ever():
    async with scratch_database("chat_default_test") as (pool, db):
        first = await db.ensure_default_chat()
        again = await db.ensure_default_chat()
        assert first.id == again.id and first.is_default and first.title == "Default chat"
        assert [c.id for c in await db.get_chats()] == [first.id]
        # another user has a default chat of their own
        other = await db.create_user("someone_else")
        mine, db.context.user = db.context.user, other
        theirs = await db.ensure_default_chat()
        assert theirs.id != first.id
        db.context.user = mine
        assert await db.get_chat(theirs.id) is None  # and a chat of another user is not here
        # the database itself allows one default chat per user
        with pytest.raises(Exception):
            await pool.pool.execute("INSERT INTO chats (user_id, is_default) VALUES ($1, TRUE)", mine.id)


@pytest.mark.asyncio
async def test_chats_are_listed_latest_first_renamed_and_deleted_with_their_messages():
    async with scratch_database("chat_crud_test") as (pool, db):
        a = await db.create_chat("First")
        b = await db.create_chat()
        assert (a.title, b.title) == ("First", f"Chat {b.id}") and not a.is_default
        default = db.context.chat  # the scratch user has one already, with nothing in it
        assert [c.id for c in await db.get_chats()] == [b.id, a.id, default.id]

        db.context.chat = a
        await db.create_messages([{"type": "user", "content": "hi"}, {"type": "assistant", "content": "hello"}])
        assert [c.id for c in await db.get_chats()] == [a.id, b.id, default.id]  # a wrote last
        assert (await db.get_chat(a.id)).messages == 2 and (await db.get_chat(b.id)).messages == 0

        assert (await db.rename_chat(a.id, "Renamed")).title == "Renamed"
        assert await db.rename_chat(999999, "x") is None
        deleted = await db.delete_chat(a.id)
        assert deleted.id == a.id and await db.get_chat(a.id) is None
        assert await pool.pool.fetchval("SELECT count(*) FROM messages") == 0  # the messages went with it
        assert await db.delete_chat(a.id) is None


@pytest.mark.asyncio
async def test_a_chat_is_named_after_its_first_message_unless_it_has_a_name_or_is_the_default():
    async with scratch_database("chat_title_test") as (pool, db):
        fresh = await db.create_chat()
        db.context.chat = fresh
        await db.create_messages([{"type": "user", "content": "\n  How much is the team plan?  \nsecond line"}, {"type": "assistant", "content": "$20"}])
        assert (await db.get_chat(fresh.id)).title == "How much is the team plan?"
        await db.create_messages([{"type": "user", "content": "And yearly?"}, {"type": "assistant", "content": "$200"}])
        assert (await db.get_chat(fresh.id)).title == "How much is the team plan?"  # named once

        named = await db.create_chat("Mine")
        db.context.chat = named
        await db.create_messages([{"type": "user", "content": "something else"}])
        assert (await db.get_chat(named.id)).title == "Mine"

        db.context.chat = await db.ensure_default_chat()
        await db.create_messages([{"type": "user", "content": "from a bot"}])
        assert (await db.get_chat(db.context.chat.id)).title == "Default chat"

        long = await db.create_chat()
        db.context.chat = long
        await db.create_messages([{"type": "user", "content": "x" * 300}])
        assert len((await db.get_chat(long.id)).title) <= 60


@pytest.mark.asyncio
async def test_each_chat_is_its_own_thread_of_messages():
    async with scratch_database("chat_threads_test") as (pool, db):
        a, b = await db.create_chat("A"), await db.create_chat("B")
        for chat, word in ((a, "apples"), (b, "bananas"), (a, "avocados")):
            db.context.chat = chat
            await db.create_messages([{"type": "user", "content": word}])

        db.context.chat = a
        assert [m.content["content"] for m in await db.get_all_messages()] == ["apples", "avocados"]
        db.context.chat = b
        assert [m.content["content"] for m in await db.get_all_messages()] == ["bananas"]
        assert all(m.chat_id == b.id for m in await db.get_all_messages())

        # clearing one chat leaves the other alone (and the chat itself stays)
        await db.clear_messages()
        assert await db.get_all_messages() == []
        db.context.chat = a
        assert len(await db.get_all_messages()) == 2
        assert await db.get_chat(b.id) is not None


@pytest.mark.asyncio
async def test_messages_that_expired_are_not_counted_in_a_chat(monkeypatch):
    from database.mixins import chat as chat_mixin

    async with scratch_database("chat_count_test") as (pool, db):
        chat = db.context.chat
        for days in (10, 1):
            await pool.pool.execute(
                "INSERT INTO messages (user_id, chat_id, content, timestamp) VALUES ($1, $2, $3, now() - make_interval(days => $4))",
                db.context.user.id, chat.id, json.dumps({"type": "user", "content": f"{days}"}), days,
            )
        assert (await db.get_chat(chat.id)).messages == 1
        monkeypatch.setattr(chat_mixin, "MESSAGE_TTL_DAYS", 0)
        assert (await db.get_chat(chat.id)).messages == 2


@pytest.mark.asyncio
async def test_deleting_a_user_deletes_their_chats(scratch_db=None):
    async with scratch_database("chat_cascade_test") as (pool, db):
        await db.create_chat("one")
        await db.delete_user()
        assert await pool.pool.fetchval("SELECT count(*) FROM chats") == 0


@pytest.mark.asyncio
async def test_migration_13_puts_the_old_messages_into_the_default_chat_of_their_user(scratch_db, tmp_path):
    for number, path in list_migrations(MIGRATIONS_DIR):
        if number <= 12:
            (tmp_path / path.name).write_text(path.read_text())
    await scratch_db.execute("CREATE EXTENSION IF NOT EXISTS vector")
    assert await apply_migrations(scratch_db, tmp_path) == 12

    await scratch_db.execute("INSERT INTO models (id, request_json) VALUES (0, '{\"model\": \"a/b\"}')")
    agent = await scratch_db.fetchval("INSERT INTO agents (prompt, model_id) VALUES ('', 0) RETURNING id")
    ann = await scratch_db.fetchval("INSERT INTO users (agent_id, external_id) VALUES ($1, 'ann') RETURNING id", agent)
    bob = await scratch_db.fetchval("INSERT INTO users (agent_id, external_id) VALUES ($1, 'bob') RETURNING id", agent)
    await scratch_db.fetchval("INSERT INTO users (agent_id, external_id) VALUES ($1, 'quiet') RETURNING id", agent)
    for user, text, ago in ((ann, "one", 3), (ann, "two", 1), (bob, "hello", 2)):
        await scratch_db.execute(
            "INSERT INTO messages (user_id, content, timestamp) VALUES ($1, $2, now() - make_interval(days => $3))", user, json.dumps({"type": "user", "content": text}), ago
        )
    await scratch_db.execute("INSERT INTO messages (user_id, content) VALUES (NULL, '{\"type\": \"user\", \"content\": \"nobody\"}')")

    (tmp_path / "13.sql").write_text((MIGRATIONS_DIR / "13.sql").read_text())
    assert await apply_migrations(scratch_db, tmp_path) == 13

    chats = await scratch_db.fetch("SELECT * FROM chats ORDER BY user_id")
    assert [(c["user_id"], c["is_default"]) for c in chats] == [(ann, True), (bob, True)]  # a user with no messages has no chat yet
    assert chats[0]["title"] is None
    assert chats[0]["updated_at"] > chats[0]["timestamp"]  # first message to last
    rows = await scratch_db.fetch("SELECT user_id, chat_id, content FROM messages ORDER BY id")
    assert [json.loads(r["content"])["content"] for r in rows] == ["one", "two", "hello"]  # the orphan is gone
    by_user = {c["user_id"]: c["id"] for c in chats}
    assert [r["chat_id"] for r in rows] == [by_user[ann], by_user[ann], by_user[bob]]
    # from now on a message needs a chat
    with pytest.raises(Exception):
        await scratch_db.execute("INSERT INTO messages (user_id, content) VALUES ($1, '{}')", ann)
