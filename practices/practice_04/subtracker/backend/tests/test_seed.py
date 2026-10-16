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


async def test_demo_user_has_upcoming_charges_within_30_days(session, monkeypatch):
    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(seed_module, "SessionLocal", lambda: _Ctx())
    await seed_module.seed()

    from app.services import auth as auth_service
    from app.services import subscriptions as subscription_service

    user = await auth_service.get_user_by_email(session, seed_module.DEMO_EMAIL)
    charges = await subscription_service.upcoming_charges(
        session, user, 30, seed_module.get_today()
    )
    assert len(charges) >= 2


async def test_seed_refuses_in_production(session, monkeypatch):
    import pytest
    from sqlalchemy import select

    from app.models import User

    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(seed_module, "SessionLocal", lambda: _Ctx())
    monkeypatch.setattr(seed_module.settings, "app_env", "production")

    with pytest.raises(seed_module.SeedRefusedError):
        await seed_module.seed()
    assert (await session.execute(select(User))).scalars().all() == []


def test_seed_script_exits_nonzero_in_production():
    import os
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "scripts.seed"],
        check=False,
        cwd=seed_module.__file__.rsplit("/scripts/", 1)[0],
        env={
            **os.environ,
            "APP_ENV": "production",
            "SECRET_KEY": "test-secret-key-with-sufficient-length-32b",
            "DATABASE_URL": "postgresql+asyncpg://u:p@127.0.0.1:1/none",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Refusing to seed" in result.stderr
