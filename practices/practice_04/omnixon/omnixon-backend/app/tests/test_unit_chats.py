"""unit chats tests: the threads of a user, the default chat, the titles, and migration 13 on old data"""

import json

import pytest
from domain.entities import Chat
from infrastructure.postgres import (
    MIGRATIONS_DIR,
    apply_migrations,
    list_migrations,
)

from world import world
from repositories.people import ChatRepository, MessageRepository, UserRepository


def test_a_chat_without_a_title_has_a_name_all_the_same():
    from datetime import datetime

    now = datetime(2026, 1, 1)
    plain = Chat(id=7, user_id=1, title=None, timestamp=now, updated_at=now)
    assert plain.title == "Chat 7"
    assert Chat(id=8, user_id=1, is_default=True, timestamp=now, updated_at=now).title == "Default chat"
    assert Chat(id=9, user_id=1, title="  Prices  ", timestamp=now, updated_at=now).title == "  Prices  "  # a given title wins


@pytest.mark.asyncio
async def test_the_default_chat_is_made_once_and_is_the_same_for_ever():
    async with world() as w:
        agent = await w.agent("a")
        user = await w.get(UserRepository).insert(agent.id, "u")
        chats = w.get(ChatRepository)
        assert await chats.default(user.id) is None  # not until it is needed
        first, again = await chats.ensure_default(user.id), await chats.ensure_default(user.id)
        assert first.id == again.id and first.is_default and first.title == "Default chat" and first.messages == 0
        other = await chats.insert(user.id, "other")
        assert not other.is_default and (await chats.default(user.id)).id == first.id


@pytest.mark.asyncio
async def test_chats_are_listed_latest_first_renamed_and_deleted_with_their_messages():
    async with world() as w:
        agent = await w.agent("a")
        user = await w.get(UserRepository).insert(agent.id, "u")
        chats, messages = w.get(ChatRepository), w.get(MessageRepository)
        a, b = await chats.insert(user.id, "a"), await chats.insert(user.id, "b")
        await messages.append(user.id, a.id, agent.id, {"type": "user", "content": "x"})
        await chats.touch(a.id, None)
        assert [c.title for c in await chats.list(user.id)] == ["a", "b"]  # the one with the latest message first
        assert (await chats.rename(user.id, b.id, "bee")).title == "bee" and await chats.rename(user.id, 99999, "x") is None
        await chats.delete(user.id, a.id)
        assert await chats.get(user.id, a.id) is None and await messages.window_of(a.id, 5) == []  # its messages go with it
        assert (await chats.get(user.id, b.id)).id == b.id


@pytest.mark.asyncio
async def test_a_chat_is_named_after_its_first_message_unless_it_has_a_name_or_is_the_default():
    async with world() as w:
        agent = await w.agent("a")
        user = await w.get(UserRepository).insert(agent.id, "u")
        chats = w.get(ChatRepository)
        untitled, named, default = await chats.insert(user.id), await chats.insert(user.id, "Prices"), await chats.ensure_default(user.id)
        for chat in (untitled, named, default):
            await chats.touch(chat.id, "How much is the red one?")
            await chats.touch(chat.id, "and the blue one?")  # only the first counts
        assert (await chats.get(user.id, untitled.id)).title == "How much is the red one?"
        assert (await chats.get(user.id, named.id)).title == "Prices" and (await chats.get(user.id, default.id)).title == "Default chat"


@pytest.mark.asyncio
async def test_messages_that_expired_are_not_counted_in_a_chat():
    for ttl, counted in ((7, 1), (0, 2)):
        async with world() as w:
            agent = await w.agent("a")
            user = await w.get(UserRepository).insert(agent.id, "u")
            chats = ChatRepository(w.get(ChatRepository).db, ttl)
            chat = await chats.ensure_default(user.id)
            for days in (10, 1):
                await chats.db.execute(
                    "INSERT INTO messages (user_id, chat_id, content, timestamp) VALUES ($1, $2, $3, now() - make_interval(days => $4))",
                    (user.id, chat.id, {"type": "user", "content": f"{days}"}, days),
                )
            assert (await chats.get(user.id, chat.id)).messages == counted


@pytest.mark.asyncio
async def test_deleting_a_user_deletes_their_chats():
    async with world() as w:
        agent = await w.agent("a")
        users, chats = w.get(UserRepository), w.get(ChatRepository)
        user = await users.insert(agent.id, "u")
        await chats.insert(user.id, "one")
        await users.delete(user.id)
        assert (await chats.db.fetch_one("SELECT count(*) AS n FROM chats WHERE user_id = $1", (user.id,)))["n"] == 0


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
