from typing import Optional, Sequence

from core import MESSAGE_TTL_DAYS
from ..context import PostgresConnectionWithContext
from ..models import Chat, prompt_title

# a chat with the number of its messages that are still kept (the same window as when the messages are read)
_SELECT = """
    SELECT c.*,
           (SELECT count(*) FROM messages m
             WHERE m.chat_id = c.id
               AND ($2::float8 <= 0 OR m.timestamp > now() - make_interval(secs => $2)))::int AS messages
    FROM chats c
"""


class ChatMethods(PostgresConnectionWithContext):
    """The conversations of the current user (`context.user`). A request is in one of them (`context.chat`)."""

    @property
    def _window(self) -> float:
        return MESSAGE_TTL_DAYS * 86400

    async def get_chats(self) -> Sequence[Chat]:
        """The latest first."""
        rows = await self.fetch_all(
            _SELECT + " WHERE c.user_id = $1 ORDER BY c.updated_at DESC, c.id DESC",
            (self.context.user.id, self._window),
            Chat,
        )
        return rows or []

    async def get_chat(self, chat_id: int) -> Optional[Chat]:
        return await self.fetch_one(
            _SELECT + " WHERE c.id = $1 AND c.user_id = $3",
            (chat_id, self._window, self.context.user.id),
            Chat,
        )

    async def get_default_chat(self) -> Optional[Chat]:
        return await self.fetch_one(
            _SELECT + " WHERE c.user_id = $1 AND c.is_default",
            (self.context.user.id, self._window),
            Chat,
        )

    async def ensure_default_chat(self) -> Chat:
        """The chat that a request without `chat_id` goes to; made when it is first needed."""
        await self.execute(
            "INSERT INTO chats (user_id, is_default) VALUES ($1, TRUE) ON CONFLICT DO NOTHING",
            (self.context.user.id,),
        )
        return await self.get_default_chat()

    async def create_chat(self, title: Optional[str] = None) -> Chat:
        created = await self.fetch_one(
            "INSERT INTO chats (user_id, title) VALUES ($1, $2) RETURNING id",
            (self.context.user.id, title),
            dict,
        )
        return await self.get_chat(created["id"])

    async def rename_chat(self, chat_id: int, title: str) -> Optional[Chat]:
        updated = await self.fetch_one(
            "UPDATE chats SET title = $1 WHERE id = $2 AND user_id = $3 RETURNING id",
            (title, chat_id, self.context.user.id),
            dict,
        )
        return await self.get_chat(chat_id) if updated else None

    async def delete_chat(self, chat_id: int) -> Optional[Chat]:
        """Its messages go with it."""
        chat = await self.get_chat(chat_id)
        if chat is None:
            return None
        await self.execute("DELETE FROM chats WHERE id = $1", (chat_id,))
        return chat

    async def touch_chat(self, first_text: Optional[str] = None) -> None:
        """The chat has a new message: it is the latest now, and a chat with no title is named after what was said first
        (the default chat keeps its name)."""
        title = prompt_title(first_text or "") or None
        await self.execute(
            """
            UPDATE chats SET updated_at = now(),
                title = CASE WHEN title IS NULL AND NOT is_default THEN $2 ELSE title END
            WHERE id = $1
            """,
            (self.context.chat.id, title),
        )
