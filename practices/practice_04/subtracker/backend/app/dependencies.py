from datetime import UTC, date, datetime


def get_today() -> date:
    """Current date in UTC; a dependency so tests can pin the clock."""
    return datetime.now(UTC).date()
