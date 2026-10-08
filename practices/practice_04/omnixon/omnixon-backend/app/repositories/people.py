from __future__ import annotations

import secrets
from typing import List, Optional

from database.models import Chat, Message, NewToken, RecentUser, Token, User, prompt_title, token_hash
from .base import Repository
from .database import Database


def _chosen(alphabet: str, times: int) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(times))


def new_secret() -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return _chosen(alphabet, 3) + "_" + _chosen(alphabet, 60)


class TokenRepository(Repository):
    async def by_secret(self, secret: str) -> Optional[Token]:
        return await self.db.fetch_one("SELECT * FROM tokens WHERE token_sha256=$1", (token_hash(secret),), Token)

    async def get(self, token_id: int) -> Optional[Token]:
        return await self.db.fetch_one("SELECT * FROM tokens WHERE id=$1", (token_id,), Token)

    async def list(self, agent_id: Optional[int] = None) -> List[Token]:
        """The tokens of an agent, or of every agent."""
        if agent_id is None:
            return await self.db.fetch_all("SELECT * FROM tokens ORDER BY id", (), Token)
        return await self.db.fetch_all("SELECT * FROM tokens WHERE agent_id=$1 ORDER BY id", (agent_id,), Token)

    async def insert(self, name: str, agent_id: int, role: str, secret: Optional[str] = None) -> NewToken:
        """Make a token and return it with its secret: the only time the secret is known."""
        for _ in range(5):
            secret_value = secret or new_secret()
            row = await self.db.fetch_one(
                "INSERT INTO tokens (name, agent_id, role, token_sha256) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING RETURNING *",
                (name, agent_id, role, token_hash(secret_value)),
                Token,
            )
            if row:
                return NewToken(**row.model_dump(), token_sha256=row.token_sha256, token=secret_value)
            if secret:
                break
        raise RuntimeError("Failed to create a token: could not allocate a unique secret")

    async def update(self, token_id: int, name: Optional[str] = None, role: Optional[str] = None) -> Optional[Token]:
        """Rename and/or change the role (what is None stays)."""
        return await self.db.fetch_one(
            "UPDATE tokens SET name=COALESCE($1, name), role=COALESCE($2, role) WHERE id=$3 RETURNING *", (name, role, token_id), Token
        )

    async def delete(self, token_id: int) -> Optional[Token]:
        return await self.db.fetch_one("DELETE FROM tokens WHERE id=$1 RETURNING *", (token_id,), Token)


class UserRepository(Repository):
    async def get(self, agent_id: int, external_id: str) -> Optional[User]:
        return await self.db.fetch_one("SELECT * FROM users WHERE external_id=$1 AND agent_id=$2", (external_id, agent_id), User)

    async def search(self, agent_id: int, prefix: str, limit: int = 10) -> List[User]:
        """The users of the agent whose external id starts with `prefix`, by external id (`%` and `_` in the prefix are taken literally)."""
        pattern = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        return await self.db.fetch_all(
            "SELECT * FROM users WHERE agent_id = $1 AND external_id LIKE $2 ORDER BY external_id LIMIT $3", (agent_id, pattern, limit), User
        )

    async def recent(self, agent_id: int, limit: int, ttl_days: float) -> List[RecentUser]:
        """The users that have messages that are still kept, the latest first."""
        return await self.db.fetch_all(
            """
            SELECT u.*, max(m.timestamp) AS last_active, count(*)::int AS messages
            FROM users u JOIN messages m ON m.user_id = u.id
            WHERE u.agent_id = $1
            AND ($3::float8 <= 0 OR m.timestamp > now() - make_interval(secs => $3))
            GROUP BY u.id
            ORDER BY last_active DESC, u.id DESC
            LIMIT $2
            """,
            (agent_id, limit, ttl_days * 86400),
            RecentUser,
        )

    async def insert(self, agent_id: int, external_id: str) -> Optional[User]:
        """None: the user is there already."""
        return await self.db.fetch_one(
            "INSERT INTO users (agent_id, external_id) VALUES ($1, $2) ON CONFLICT DO NOTHING RETURNING *", (agent_id, external_id), User
        )

    async def rename(self, user_id: int, agent_id: int, external_id: str) -> Optional[User]:
        """None: no such user, or the new id is taken."""
        return await self.db.fetch_one(
            """
            UPDATE users SET external_id = COALESCE($1, external_id)
            WHERE id = $2
            AND NOT EXISTS (SELECT 1 FROM users WHERE external_id = $1 AND agent_id = $3 AND id != $2)
            RETURNING *
            """,
            (external_id, user_id, agent_id),
            User,
        )

    async def delete(self, user_id: int) -> Optional[User]:
        return await self.db.fetch_one("DELETE FROM users WHERE id=$1 RETURNING *", (user_id,), User)


# a chat with the number of its messages that are still kept (the same window as when the messages are read)
_CHAT = """
    SELECT c.*,
           (SELECT count(*) FROM messages m
             WHERE m.chat_id = c.id
               AND ($2::float8 <= 0 OR m.timestamp > now() - make_interval(secs => $2)))::int AS messages
    FROM chats c
"""


class ChatRepository(Repository):
    def __init__(self, database: Database, ttl_days: float):
        super().__init__(database)
        self.window = ttl_days * 86400

    async def list(self, user_id: int) -> List[Chat]:
        """The latest first."""
        return await self.db.fetch_all(_CHAT + " WHERE c.user_id = $1 ORDER BY c.updated_at DESC, c.id DESC", (user_id, self.window), Chat)

    async def get(self, user_id: int, chat_id: int) -> Optional[Chat]:
        return await self.db.fetch_one(_CHAT + " WHERE c.id = $1 AND c.user_id = $3", (chat_id, self.window, user_id), Chat)

    async def default(self, user_id: int) -> Optional[Chat]:
        return await self.db.fetch_one(_CHAT + " WHERE c.user_id = $1 AND c.is_default", (user_id, self.window), Chat)

    async def ensure_default(self, user_id: int) -> Chat:
        """The chat that a request without `chat_id` goes to; made when it is first needed."""
        await self.db.execute("INSERT INTO chats (user_id, is_default) VALUES ($1, TRUE) ON CONFLICT DO NOTHING", (user_id,))
        return await self.default(user_id)

    async def insert(self, user_id: int, title: Optional[str] = None) -> Chat:
        created = await self.db.fetch_one("INSERT INTO chats (user_id, title) VALUES ($1, $2) RETURNING id", (user_id, title))
        return await self.get(user_id, created["id"])

    async def rename(self, user_id: int, chat_id: int, title: str) -> Optional[Chat]:
        updated = await self.db.fetch_one(
            "UPDATE chats SET title = $1 WHERE id = $2 AND user_id = $3 RETURNING id", (title, chat_id, user_id)
        )
        return await self.get(user_id, chat_id) if updated else None

    async def delete(self, user_id: int, chat_id: int) -> Optional[Chat]:
        """Its messages go with it."""
        chat = await self.get(user_id, chat_id)
        if chat is None:
            return None
        await self.db.execute("DELETE FROM chats WHERE id = $1", (chat_id,))
        return chat

    async def touch(self, chat_id: int, first_text: Optional[str] = None) -> None:
        """The chat has a new message: it is the latest now, and a chat with no title is named after what was said first
        (the default chat keeps its name)."""
        title = prompt_title(first_text or "") or None
        await self.db.execute(
            """
            UPDATE chats SET updated_at = now(),
                title = CASE WHEN title IS NULL AND NOT is_default THEN $2 ELSE title END
            WHERE id = $1
            """,
            (chat_id, title),
        )


class MessageRepository(Repository):
    def __init__(self, database: Database, ttl_days: float):
        super().__init__(database)
        self.window = ttl_days * 86400

    async def window_of(self, chat_id: int, limit: int) -> List[Message]:
        """The latest `limit` messages that have not expired, oldest first (an expired one is gone even before the cleanup deletes it)."""
        rows = await self.db.fetch_all(
            """
            SELECT * FROM messages
            WHERE chat_id=$1
            AND ($3::float8 <= 0 OR timestamp > now() - make_interval(secs => $3))
            ORDER BY id DESC
            LIMIT $2
            """,
            (chat_id, limit, self.window),
            Message,
        )
        return rows[::-1]

    async def append(self, user_id: int, chat_id: int, agent_id: int, content: dict) -> Message:
        return await self.db.fetch_one(
            """
            INSERT INTO messages (user_id, chat_id, content, agent_version)
            VALUES ($1, $4, $2, (SELECT max(number) FROM agent_versions WHERE agent_id=$3))
            RETURNING *
            """,
            (user_id, content, agent_id, chat_id),
            Message,
        )

    async def clear(self, chat_id: int) -> None:
        await self.db.execute("DELETE FROM messages WHERE chat_id = $1", (chat_id,))
