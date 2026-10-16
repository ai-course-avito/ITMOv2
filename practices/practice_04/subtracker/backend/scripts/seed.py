"""Idempotent demo data: one user with a subscription per billing cycle.

Run from backend/:  uv run python -m scripts.seed
"""

import asyncio
from decimal import Decimal

from app.db import SessionLocal
from app.models import Subscription
from app.services import auth as auth_service

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo-password"

DEMO_SUBSCRIPTIONS = [
    ("Netflix", Decimal("15.49"), "monthly", None),
    ("Spotify", Decimal("10.99"), "monthly", None),
    ("iCloud+ (annual)", Decimal("35.88"), "yearly", None),
    ("Gym pass", Decimal("6.00"), "weekly", None),
    ("VPN (every 90 days)", Decimal("19.90"), "custom_days", 90),
]


async def seed() -> bool:
    """Create the demo user and subscriptions. Returns False if already seeded."""
    async with SessionLocal() as session:
        if await auth_service.get_user_by_email(session, DEMO_EMAIL) is not None:
            return False
        user = await auth_service.register_user(session, DEMO_EMAIL, DEMO_PASSWORD)
        for name, amount, cycle, days in DEMO_SUBSCRIPTIONS:
            session.add(
                Subscription(
                    owner_id=user.id,
                    name=name,
                    amount=amount,
                    billing_cycle=cycle,
                    custom_interval_days=days,
                )
            )
        await session.commit()
        return True


if __name__ == "__main__":
    created = asyncio.run(seed())
    if created:
        print(f"Seeded demo user {DEMO_EMAIL} / {DEMO_PASSWORD}")
    else:
        print("Demo data already present, nothing to do")
