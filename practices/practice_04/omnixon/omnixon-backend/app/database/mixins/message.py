from typing import Optional, Sequence
from core import MESSAGE_TTL_DAYS
from ..context import PostgresConnectionWithContext
from ..models import Message


class MessageMethods(PostgresConnectionWithContext):
    async def create_message(self, content: dict) -> Message:
        query = """
            INSERT INTO messages (user_id, chat_id, content, agent_version)
            VALUES (
                $1, $4, $2,
                (SELECT max(number) FROM agent_versions WHERE agent_id=$3)
            )
            RETURNING *
        """
        return await self.fetch_one(
            query,
            (self.context.user.id, content, self.context.agent.id, self.context.chat.id),
            Message,
        )

    async def create_messages(self, contents: Sequence[dict]) -> Sequence[Message]:
        """Write several messages of the current user as one unit: all or none, and next
        to each other even when the user has other requests running (their messages
        go before or after, never in between)."""
        created = []
        async with self.transaction():
            await self.lock(f"messages:{self.context.chat.id}")
            for content in contents:
                created.append(await self.create_message(content))
            first = next((c.get("content") for c in contents if c.get("type") == "user"), None)
            await self.touch_chat(first if isinstance(first, str) else None)
        return created

    async def get_all_messages(self) -> Optional[Sequence[Message]]:
        # (a message older than the TTL is gone even before the cleanup deletes it)
        query = """
            SELECT * FROM messages
            WHERE chat_id=$1
            AND ($3::float8 <= 0 OR timestamp > now() - make_interval(secs => $3))
            ORDER BY id DESC
            LIMIT $2
        """
        return (
            (
                await self.fetch_all(
                    query,
                    (
                        self.context.chat.id,
                        self.context.agent.message_limit,
                        MESSAGE_TTL_DAYS * 86400,
                    ),
                    Message,
                )
            )
            or []
        )[::-1]

    async def clear_messages(self) -> None:
        """The messages of the current chat."""
        await self.execute("DELETE FROM messages WHERE chat_id = $1", (self.context.chat.id,))
