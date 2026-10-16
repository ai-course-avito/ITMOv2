"""Idempotent demo data: one user with a subscription per billing cycle.

Run from backend/:  uv run python -m scripts.seed
"""

import asyncio
from datetime import timedelta
from decimal import Decimal

from app.config import settings
from app.db import SessionLocal
from app.dependencies import get_today
from app.models import Subscription
from app.services import auth as auth_service

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo-password"

# (name, amount, cycle, custom interval, days until the next charge)
DEMO_SUBSCRIPTIONS = [
    ("Netflix", Decimal("15.49"), "monthly", None, 2),
    ("Spotify", Decimal("10.99"), "monthly", None, 9),
    ("iCloud+ (annual)", Decimal("35.88"), "yearly", None, 120),
    ("Gym pass", Decimal("6.00"), "weekly", None, 1),
    ("VPN (every 90 days)", Decimal("19.90"), "custom_days", 90, 25),
]


class SeedRefusedError(Exception):
    pass


async def seed() -> bool:
    """Create the demo user and subscriptions. Returns False if already seeded."""
    if settings.app_env.lower() == "production":
        raise SeedRefusedError(
            "Refusing to seed: APP_ENV=production (the demo account has a public password)"
        )
    async with SessionLocal() as session:
        if await auth_service.get_user_by_email(session, DEMO_EMAIL) is not None:
            return False
        user = await auth_service.register_user(session, DEMO_EMAIL, DEMO_PASSWORD)
        today = get_today()
        for name, amount, cycle, interval, days_until in DEMO_SUBSCRIPTIONS:
            session.add(
                Subscription(
                    owner_id=user.id,
                    name=name,
                    amount=amount,
                    billing_cycle=cycle,
                    custom_interval_days=interval,
                    start_date=today - timedelta(days=200),
                    next_billing_date=today + timedelta(days=days_until),
                )
            )
        await session.commit()
        return True


if __name__ == "__main__":
    try:
        created = asyncio.run(seed())
    except SeedRefusedError as exc:
        raise SystemExit(str(exc)) from exc
    if created:
        print(f"Seeded demo user {DEMO_EMAIL} / {DEMO_PASSWORD}")
    else:
        print("Demo data already present, nothing to do")
