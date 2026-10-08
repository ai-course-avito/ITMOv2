from datetime import date
from typing import Any, Dict, List, Optional

from ..context import PostgresConnectionWithContext


def _plain(row: Dict[str, Any]) -> Dict[str, Any]:
    """JSON-friendly: money and sums come out of Postgres as Decimal, dates as date."""
    out = {}
    for key, value in row.items():
        if hasattr(value, "is_finite"):  # Decimal
            value = float(value)
        elif isinstance(value, date):
            value = value.isoformat()
        out[key] = value
    return out


class UsageMethods(PostgresConnectionWithContext):
    async def record_usage(
        self,
        *,
        kind: str,
        model: str,
        status: str,
        duration_ms: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: Optional[float] = None,
    ) -> None:
        """One call to the model, written on the token that made the request (also when an admin acts as
        another agent). No texts: only that it happened, how long it took and what it cost."""
        token = self.context.token
        agent = self.context.agent
        await self.execute(
            """
            INSERT INTO usage_logs (token_id, token_name, agent_id, model, kind, status,
                                    duration_ms, input_tokens, output_tokens, cost)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            (
                token.id,
                token.name,
                agent.id if agent else None,
                model,
                kind,
                status,
                duration_ms,
                input_tokens,
                output_tokens,
                cost,
            ),
        )

    async def usage_daily(
        self,
        since: date,
        until: date,
        token_id: Optional[int] = None,
        agent_id: Optional[int] = None,
        own_agent_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """The recent rows (not folded yet), summed by day, token and model. `own_agent_id` limits it to the
        tokens of one agent (what a user token may see)."""
        rows = await self.fetch_all(
            """
            SELECT l.timestamp::date AS day, l.token_id, l.token_name, l.model,
                   count(*) AS requests,
                   count(*) FILTER (WHERE l.status NOT IN ('ok', 'interrupted')) AS errors,
                   COALESCE(sum(l.input_tokens), 0) AS input_tokens,
                   COALESCE(sum(l.output_tokens), 0) AS output_tokens,
                   COALESCE(sum(l.cost), 0) AS cost,
                   COALESCE(sum(l.duration_ms), 0) AS duration_ms_sum
            FROM usage_logs l
            LEFT JOIN tokens t ON t.id = l.token_id
            WHERE l.timestamp >= $1 AND l.timestamp < $2::date + 1
              AND ($3::bigint IS NULL OR l.token_id = $3)
              AND ($4::bigint IS NULL OR t.agent_id = $4)
              AND ($5::bigint IS NULL OR t.agent_id = $5)
            GROUP BY 1, 2, 3, 4
            ORDER BY 1, 3, 4
            """,
            (since, until, token_id, agent_id, own_agent_id),
        )
        return [_plain(dict(r)) for r in rows or []]

    async def usage_monthly(
        self,
        token_id: Optional[int] = None,
        agent_id: Optional[int] = None,
        own_agent_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        rows = await self.fetch_all(
            """
            SELECT m.month, m.token_id, m.token_name, m.model, m.requests, m.errors,
                   m.input_tokens, m.output_tokens, m.cost, m.duration_ms_sum
            FROM usage_monthly m
            LEFT JOIN tokens t ON t.id = m.token_id
            WHERE ($1::bigint IS NULL OR m.token_id = $1)
              AND ($2::bigint IS NULL OR t.agent_id = $2)
              AND ($3::bigint IS NULL OR t.agent_id = $3)
            ORDER BY m.month, m.token_name, m.model
            """,
            (token_id, agent_id, own_agent_id),
        )
        return [_plain(dict(r)) for r in rows or []]
