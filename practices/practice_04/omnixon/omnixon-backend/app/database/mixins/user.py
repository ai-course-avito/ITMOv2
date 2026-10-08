from typing import Optional, Sequence
from ..context import PostgresConnectionWithContext
from core import MESSAGE_TTL_DAYS
from ..models import RecentUser, User


class UserMethods(PostgresConnectionWithContext):
    async def get_user(self, external_id: str) -> Optional[User]:
        query = "SELECT * FROM users WHERE external_id=$1 AND agent_id=$2"
        return await self.fetch_one(query, (external_id, self.context.agent.id), User)

    async def search_users(self, prefix: str, limit: int = 10) -> Sequence[User]:
        """The users of this agent whose external id starts with `prefix`, by external id.
        Uses the prefix index, so it is cheap however many users there are; `%` and `_`
        in the prefix are taken literally."""
        pattern = (
            prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        )
        query = """
            SELECT * FROM users
            WHERE agent_id = $1 AND external_id LIKE $2
            ORDER BY external_id
            LIMIT $3
        """
        rows = await self.fetch_all(
            query, (self.context.agent.id, pattern, limit), User
        )
        return rows or []

    async def recent_users(self, limit: int = 20) -> Sequence[RecentUser]:
        """The users of this agent that have messages that are still kept (MESSAGE_TTL_DAYS), the latest first.
        There is no list of all users, but whoever wrote lately is worth suggesting."""
        query = """
            SELECT u.*, max(m.timestamp) AS last_active, count(*)::int AS messages
            FROM users u JOIN messages m ON m.user_id = u.id
            WHERE u.agent_id = $1
            AND ($3::float8 <= 0 OR m.timestamp > now() - make_interval(secs => $3))
            GROUP BY u.id
            ORDER BY last_active DESC, u.id DESC
            LIMIT $2
        """
        rows = await self.fetch_all(
            query, (self.context.agent.id, limit, MESSAGE_TTL_DAYS * 86400), RecentUser
        )
        return rows or []

    async def create_user(self, external_id: str) -> Optional[User]:
        query = """
            INSERT INTO users (agent_id, external_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            RETURNING *
        """
        return await self.fetch_one(
            query,
            (self.context.agent.id, external_id),
            User,
        )

    async def update_user(self) -> Optional[User]:
        query = """
            UPDATE users
            SET external_id = COALESCE($1, external_id)
            WHERE id = $2
            AND NOT EXISTS (
                SELECT 1 FROM users WHERE external_id = $1 AND agent_id = $3 AND id != $2
            )
            RETURNING *;
        """
        return await self.fetch_one(
            query,
            (
                self.context.user.external_id,
                self.context.user.id,
                self.context.agent.id,
            ),
            User,
        )

    async def delete_user(self) -> Optional[User]:
        query = "DELETE FROM users WHERE id=$1 RETURNING *"
        return await self.fetch_one(query, (self.context.user.id,), User)
