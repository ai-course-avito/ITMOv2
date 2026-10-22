from typing import Sequence

from fastapi import Depends, Query

from api.controller import Controller, current_principal, endpoint
from api.schemas.users import ChatCreate, ChatUpdate, UserCreate, UserUpdate
from domain.entities import Chat, Message, RecentUser, User
from domain.access import Principal
from services.users import ChatService, UserService


class UserController(Controller):
    prefix = "/api/v1"
    tags = ["Main API"]

    def __init__(self, users: UserService):
        self.users = users
        super().__init__()

    @endpoint.get("/users", summary="Find users by the start of their external ID")
    async def search_users(
        self,
        query: str = Query(
            ..., min_length=3, max_length=64, description="The start of the external ID (at least 3 characters: there is no list of all users)"
        ),
        limit: int = Query(10, ge=1, le=50, description="Maximum number of results"),
        principal: Principal = Depends(current_principal),
    ) -> Sequence[User]:
        return await self.users.search(principal, query, limit)

    @endpoint.get("/users/recent", summary="The users of the agent who wrote lately (their messages are still kept)")
    async def recent_users(
        self,
        limit: int = Query(20, ge=1, le=100, description="Maximum number of users"),
        principal: Principal = Depends(current_principal),
    ) -> Sequence[RecentUser]:
        """Latest first, by the latest message that has not expired (`MESSAGE_TTL_DAYS`, 7 by default). Not a list of all users: a user
        with no kept messages is not in it, but can still be found by `GET /users?query=`."""
        return await self.users.recent(principal, limit)

    @endpoint.post("/users", summary="Create a new user", status_code=201)
    async def create_user(self, data: UserCreate, principal: Principal = Depends(current_principal)) -> User:
        return await self.users.create(principal, data.external_id)

    @endpoint.get("/users/{user_id}", summary="Get a user by external ID")
    async def get_user(self, user_id: str, principal: Principal = Depends(current_principal)) -> User:
        return await self.users.get(principal, user_id)

    @endpoint.patch("/users/{user_id}", summary="Update a user")
    async def update_user(self, user_id: str, data: UserUpdate, principal: Principal = Depends(current_principal)) -> User:
        return await self.users.rename(principal, user_id, data.external_id)

    @endpoint.delete("/users/{user_id}", summary="Delete a user")
    async def delete_user(self, user_id: str, principal: Principal = Depends(current_principal)) -> User:
        return await self.users.delete(principal, user_id)


class ChatController(Controller):
    """The conversations of a user with the agent (each is its own thread of messages), and the history of the default chat."""

    prefix = "/api/v1"
    tags = ["Main API"]

    def __init__(self, chats: ChatService):
        self.chats = chats
        super().__init__()

    @endpoint.get("/users/{user_id}/history", summary="Get the message history of the default chat of a user")
    async def get_history(self, user_id: str, principal: Principal = Depends(current_principal)) -> Sequence[Message]:
        return await self.chats.history(principal, user_id)

    @endpoint.delete("/users/{user_id}/history", summary="Clear the message history of the default chat of a user", status_code=204)
    async def delete_history(self, user_id: str, principal: Principal = Depends(current_principal)) -> None:
        await self.chats.clear(principal, user_id)

    @endpoint.get("/users/{user_id}/chats", summary="The chats of a user, the latest first")
    async def get_chats(self, user_id: str, principal: Principal = Depends(current_principal)) -> Sequence[Chat]:
        return await self.chats.list(principal, user_id)

    @endpoint.post("/users/{user_id}/chats", summary="Start a chat", status_code=201)
    async def create_chat(self, user_id: str, data: ChatCreate | None = None, principal: Principal = Depends(current_principal)) -> Chat:
        return await self.chats.create(principal, user_id, data.title if data else None)

    @endpoint.get("/users/{user_id}/chats/{chat_id}", summary="One chat of a user")
    async def get_chat(self, user_id: str, chat_id: int, principal: Principal = Depends(current_principal)) -> Chat:
        return await self.chats.get(principal, user_id, chat_id)

    @endpoint.patch("/users/{user_id}/chats/{chat_id}", summary="Rename a chat")
    async def rename_chat(self, user_id: str, chat_id: int, data: ChatUpdate, principal: Principal = Depends(current_principal)) -> Chat:
        return await self.chats.rename(principal, user_id, chat_id, data.title)

    @endpoint.delete("/users/{user_id}/chats/{chat_id}", summary="Delete a chat with its messages")
    async def delete_chat(self, user_id: str, chat_id: int, principal: Principal = Depends(current_principal)) -> Chat:
        """The default chat can be deleted too: it is made again when a request without `chat_id` needs it."""
        return await self.chats.delete(principal, user_id, chat_id)

    @endpoint.get("/users/{user_id}/chats/{chat_id}/history", summary="The messages of a chat")
    async def get_chat_history(self, user_id: str, chat_id: int, principal: Principal = Depends(current_principal)) -> Sequence[Message]:
        return await self.chats.history(principal, user_id, chat_id)

    @endpoint.delete("/users/{user_id}/chats/{chat_id}/history", summary="Clear a chat (it stays, its messages go)", status_code=204)
    async def clear_chat_history(self, user_id: str, chat_id: int, principal: Principal = Depends(current_principal)) -> None:
        await self.chats.clear(principal, user_id, chat_id)
