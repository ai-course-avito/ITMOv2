"""Folding usage rows for a test: the job's work, without waiting for its interval."""

from infrastructure.jobs import UsageCompactionJob


async def fold_usage(db, ttl_days):
    return await UsageCompactionJob(db.pool, ttl_days, 1).fold()
