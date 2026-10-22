from __future__ import annotations

from typing import List, Optional

from config import AgentDefaults
from domain.entities import Chat, Message, RecentUser, User
from domain.access import Principal
from domain.errors import Conflict, NotFound
from repositories.people import ChatRepository, MessageRepository, UserRepository


class UserService:
    def __init__(self, users: UserRepository, ttl_days: float):
        self.users, self.ttl_days = users, ttl_days

    async def search(self, principal: Principal, query: str, limit: int) -> List[User]:
        return await self.users.search(principal.agent.id, query, limit)

    async def recent(self, principal: Principal, limit: int) -> List[RecentUser]:
        return await self.users.recent(principal.agent.id, limit, self.ttl_days)

    async def create(self, principal: Principal, external_id: str) -> User:
        user = await self.users.insert(principal.agent.id, external_id)
        if not user:
            raise Conflict("User already exists")
        return user

    async def get(self, principal: Principal, external_id: str) -> User:
        user = await self.users.get(principal.agent.id, external_id)
        if not user:
            raise NotFound("User not found")
        return user

    async def rename(self, principal: Principal, external_id: str, new_id: Optional[str]) -> User:
        user = await self.get(principal, external_id)
        renamed = await self.users.rename(user.id, principal.agent.id, new_id or user.external_id)
        if not renamed:
            raise Conflict("Failed to update user: duplicate external_id")
        return renamed

    async def delete(self, principal: Principal, external_id: str) -> User:
        user = await self.get(principal, external_id)
        return await self.users.delete(user.id)

    async def ensure(self, agent_id: int, external_id: str) -> User:
        """The user of the agent with this id, made if there is none. Two requests that make it at once get the same one."""
        user = await self.users.get(agent_id, external_id)
        if user is None:
            user = await self.users.insert(agent_id, external_id)
            if user is None:  # another task made it first (two tools of one turn asking the same agent)
                user = await self.users.get(agent_id, external_id)
        if user is None:
            raise Conflict("Could not create a new user")
        return user


class ChatService:
    """The conversations of a user with the agent, and their messages."""

    def __init__(self, users: UserService, chats: ChatRepository, messages: MessageRepository, defaults: AgentDefaults):
        self.users, self.chats, self.messages, self.defaults = users, chats, messages, defaults

    def _limit(self, principal: Principal) -> int:
        return principal.agent.settings(self.defaults).message_limit

    async def list(self, principal: Principal, external_id: str) -> List[Chat]:
        user = await self.users.get(principal, external_id)
        return await self.chats.list(user.id)

    async def create(self, principal: Principal, external_id: str, title: Optional[str]) -> Chat:
        user = await self.users.get(principal, external_id)
        return await self.chats.insert(user.id, title)

    async def get(self, principal: Principal, external_id: str, chat_id: int) -> Chat:
        user = await self.users.get(principal, external_id)
        chat = await self.chats.get(user.id, chat_id)
        if not chat:
            raise NotFound("Chat not found")
        return chat

    async def rename(self, principal: Principal, external_id: str, chat_id: int, title: str) -> Chat:
        chat = await self.get(principal, external_id, chat_id)
        return await self.chats.rename(chat.user_id, chat_id, title)

    async def delete(self, principal: Principal, external_id: str, chat_id: int) -> Chat:
        """The default chat can be deleted too: it is made again when a request without `chat_id` needs it."""
        chat = await self.get(principal, external_id, chat_id)
        return await self.chats.delete(chat.user_id, chat_id)

    async def history(self, principal: Principal, external_id: str, chat_id: Optional[int] = None) -> List[Message]:
        """The messages of a chat, or of the default chat of the user (none if it has not been needed yet)."""
        if chat_id is not None:
            chat = await self.get(principal, external_id, chat_id)
        else:
            user = await self.users.get(principal, external_id)
            chat = await self.chats.default(user.id)
            if chat is None:
                return []
        return await self.messages.window_of(chat.id, self._limit(principal))

    async def clear(self, principal: Principal, external_id: str, chat_id: Optional[int] = None) -> None:
        if chat_id is not None:
            chat = await self.get(principal, external_id, chat_id)
        else:
            user = await self.users.get(principal, external_id)
            chat = await self.chats.default(user.id)
            if chat is None:
                return
        await self.messages.clear(chat.id)

    async def resolve(self, user: User, chat_id: Optional[int]) -> Chat:
        """The chat a request goes to: the one asked for (it must be the user's), else the user's default chat."""
        if chat_id is None:
            return await self.chats.ensure_default(user.id)
        chat = await self.chats.get(user.id, chat_id)
        if not chat:
            raise NotFound("Chat not found")
        return chat
