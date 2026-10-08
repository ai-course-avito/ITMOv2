"""Messages expire: a conversation older than MESSAGE_TTL_DAYS is forgotten.

Reading ignores expired messages at once (see MessageMethods.get_all_messages); this
module deletes them, so the table does not grow forever."""

import asyncio

import logfire

from core import metrics
from core import MESSAGE_CLEANUP_INTERVAL_SECONDS, MESSAGE_TTL_DAYS

BATCH_SIZE = 10_000


async def expire_messages(
    pool, ttl_days: float = MESSAGE_TTL_DAYS, batch: int = BATCH_SIZE
) -> int:
    """Delete the messages older than `ttl_days` (in batches, so a large backlog does
    not hold locks for long). Returns how many were deleted; 0 days keeps everything."""
    if ttl_days <= 0:
        return 0

    query = """
        DELETE FROM messages
        WHERE id IN (
            SELECT id FROM messages
            WHERE timestamp < now() - make_interval(secs => $1)
            LIMIT $2
        )
    """
    total = 0
    while True:
        async with pool.acquire() as connection:
            status = await connection.execute(query, ttl_days * 86400, batch)
        deleted = int(status.split()[-1])  # "DELETE <n>"
        total += deleted
        if deleted < batch:
            break

    if total:
        metrics.MESSAGES_EXPIRED.inc(total)
        logfire.info(
            "Deleted {count} messages older than {days} days",
            count=total,
            days=ttl_days,
        )
    return total


async def run_retention(
    pool,
    ttl_days: float = MESSAGE_TTL_DAYS,
    interval: float = MESSAGE_CLEANUP_INTERVAL_SECONDS,
) -> None:
    """Delete expired messages now and then, until cancelled."""
    if ttl_days <= 0:
        return
    while True:
        try:
            await expire_messages(pool, ttl_days)
        except asyncio.CancelledError:
            raise
        except Exception:
            logfire.exception("Deleting expired messages failed")
        await asyncio.sleep(interval)
