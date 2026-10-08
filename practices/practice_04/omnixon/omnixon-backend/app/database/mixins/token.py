import secrets
from typing import Optional, Sequence

from ..context import PostgresConnectionWithContext
from ..models import NewToken, Token, token_hash


def _chosen(alphabet: str, times: int) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(times))


def create_secret() -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return _chosen(alphabet, 3) + "_" + _chosen(alphabet, 60)


class TokenMethods(PostgresConnectionWithContext):
    async def get_token_by_secret(self, secret: str) -> Optional[Token]:
        return await self.fetch_one(
            "SELECT * FROM tokens WHERE token_sha256=$1", (token_hash(secret),), Token
        )

    async def get_token(self, token_id: int) -> Optional[Token]:
        return await self.fetch_one("SELECT * FROM tokens WHERE id=$1", (token_id,), Token)

    async def get_tokens(self, agent_id: Optional[int] = None) -> Sequence[Token]:
        """The tokens of an agent, or of every agent."""
        if agent_id is None:
            rows = await self.fetch_all("SELECT * FROM tokens ORDER BY id", (), Token)
        else:
            rows = await self.fetch_all(
                "SELECT * FROM tokens WHERE agent_id=$1 ORDER BY id", (agent_id,), Token
            )
        return rows or []

    async def create_token(
        self, name: str, agent_id: int, role: str, secret: Optional[str] = None
    ) -> NewToken:
        """Make a token and return it with its secret: the only time the secret is known."""
        for _ in range(5):
            secret_value = secret or create_secret()
            row = await self.fetch_one(
                """
                INSERT INTO tokens (name, agent_id, role, token_sha256)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
                RETURNING *
                """,
                (name, agent_id, role, token_hash(secret_value)),
                Token,
            )
            if row:
                return NewToken(**row.model_dump(), token_sha256=row.token_sha256, token=secret_value)
            if secret:
                break
        raise RuntimeError("Failed to create a token: could not allocate a unique secret")

    async def update_token(
        self, token_id: int, name: Optional[str] = None, role: Optional[str] = None
    ) -> Optional[Token]:
        """Rename and/or change the role (what is None stays)."""
        return await self.fetch_one(
            "UPDATE tokens SET name=COALESCE($1, name), role=COALESCE($2, role) WHERE id=$3 RETURNING *",
            (name, role, token_id),
            Token,
        )

    async def delete_token(self, token_id: int) -> Optional[Token]:
        return await self.fetch_one(
            "DELETE FROM tokens WHERE id=$1 RETURNING *", (token_id,), Token
        )

    async def ensure_initial_token(self, secret: str) -> Token:
        """The token of INITIAL_API_KEY is an owner, made at start if it is not there (with an
        agent of its own), and made an owner again if someone lowered it by hand."""
        existing = await self.get_token_by_secret(secret)
        if existing:
            if existing.role != "owner":
                existing = await self.fetch_one(
                    "UPDATE tokens SET role='owner' WHERE id=$1 RETURNING *", (existing.id,), Token
                )
            return existing
        async with self.transaction():
            # replicas start together: the first one makes the token, the others find it
            await self.lock("initial-token")
            existing = await self.get_token_by_secret(secret)
            if existing:
                return existing
            agent = await self.create_agent("", 0, name="Default agent")
            created = await self.create_token("initial", agent.id, "owner", secret)
        return await self.get_token(created.id)
