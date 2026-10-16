from sqlalchemy import select

from app.models import Subscription, User
from scripts import seed as seed_module


async def test_seed_is_idempotent(session, monkeypatch):
    class Maker:
        def __call__(self):
            return _Ctx(session)

    class _Ctx:
        def __init__(self, s):
            self.s = s

        async def __aenter__(self):
            return self.s

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(seed_module, "SessionLocal", Maker())

    assert await seed_module.seed() is True
    assert await seed_module.seed() is False

    users = (await session.execute(select(User))).scalars().all()
    subs = (await session.execute(select(Subscription))).scalars().all()
    assert len(users) == 1
    assert {s.billing_cycle for s in subs} == {
        "monthly",
        "yearly",
        "weekly",
        "custom_days",
    }
    assert len(subs) == len(seed_module.DEMO_SUBSCRIPTIONS)


async def test_demo_user_can_log_in_after_seed(session, monkeypatch):
    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(seed_module, "SessionLocal", lambda: _Ctx())
    await seed_module.seed()

    from app.services import auth as auth_service

    user = await auth_service.authenticate(
        session, seed_module.DEMO_EMAIL, seed_module.DEMO_PASSWORD
    )
    assert user.email == seed_module.DEMO_EMAIL
