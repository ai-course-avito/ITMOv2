"""unit user and chat service tests"""

import asyncio

import pytest

from domain.errors import Conflict, NotFound
from repositories.people import MessageRepository
from services.users import ChatService, UserService
from world import world


@pytest.mark.asyncio
async def test_users_are_created_found_renamed_and_deleted_with_the_texts_of_the_api():
    async with world() as w:
        users = w.get(UserService)
        p = await w.principal("regular")
        user = await users.create(p, "alice")
        with pytest.raises(Conflict, match="^User already exists$"):
            await users.create(p, "alice")
        assert (await users.get(p, "alice")).id == user.id and [u.external_id for u in await users.search(p, "ali", 10)] == ["alice"]
        await users.create(p, "bob")
        with pytest.raises(Conflict, match="^Failed to update user: duplicate external_id$"):
            await users.rename(p, "alice", "bob")
        assert (await users.rename(p, "alice", "carol")).external_id == "carol"
        assert (await users.rename(p, "carol", None)).external_id == "carol"  # nothing to change
        assert (await users.delete(p, "carol")).id == user.id
        with pytest.raises(NotFound, match="^User not found$"):
            await users.get(p, "carol")


@pytest.mark.asyncio
async def test_two_requests_that_ensure_the_same_user_at_once_get_the_same_one():
    async with world() as w:
        users = w.get(UserService)
        agent = await w.agent()
        made = await asyncio.gather(*[users.ensure(agent.id, "agent_1:alice") for _ in range(6)])
        assert len({u.id for u in made}) == 1


@pytest.mark.asyncio
async def test_the_default_chat_is_made_once_and_history_of_it_is_empty_until_needed():
    async with world() as w:
        users, chats = w.get(UserService), w.get(ChatService)
        p = await w.principal("regular")
        user = await users.create(p, "u")
        assert await chats.history(p, "u") == [] and await chats.list(p, "u") == []  # not needed yet
        first, second = await chats.resolve(user, None), await chats.resolve(user, None)
        assert first.id == second.id and first.is_default and first.title == "Default chat"
        await chats.clear(p, "u")  # nothing to clear, still fine
        with pytest.raises(NotFound, match="^User not found$"):
            await chats.history(p, "nobody")


@pytest.mark.asyncio
async def test_each_chat_is_its_own_thread_and_belongs_to_its_user():
    async with world() as w:
        users, chats, messages = w.get(UserService), w.get(ChatService), w.get(MessageRepository)
        p = await w.principal("regular")
        alice, bob = await users.create(p, "alice"), await users.create(p, "bob")
        one, two = await chats.create(p, "alice", "one"), await chats.create(p, "alice", None)
        await messages.append(alice.id, one.id, p.agent.id, {"type": "user", "content": "in one"})
        assert [m.content["content"] for m in await chats.history(p, "alice", one.id)] == ["in one"]
        assert await chats.history(p, "alice", two.id) == []
        with pytest.raises(NotFound, match="^Chat not found$"):
            await chats.get(p, "bob", one.id)  # not bob's
        with pytest.raises(NotFound, match="^Chat not found$"):
            await chats.resolve(bob, one.id)
        assert (await chats.rename(p, "alice", one.id, "renamed")).title == "renamed"
        await chats.clear(p, "alice", one.id)
        assert await chats.history(p, "alice", one.id) == []
        assert (await chats.delete(p, "alice", one.id)).id == one.id
        assert [c.id for c in await chats.list(p, "alice")] == [two.id]


@pytest.mark.asyncio
async def test_the_window_of_a_history_is_the_message_limit_of_the_agent():
    async with world(default_message_limit=2) as w:
        users, chats, messages = w.get(UserService), w.get(ChatService), w.get(MessageRepository)
        p = await w.principal("regular")
        user = await users.create(p, "u")
        chat = await chats.resolve(user, None)
        for i in range(4):
            await messages.append(user.id, chat.id, p.agent.id, {"type": "user", "content": f"m{i}"})
        assert [m.content["content"] for m in await chats.history(p, "u")] == ["m2", "m3"]
