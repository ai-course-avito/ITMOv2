import pytest
from sqlalchemy.exc import IntegrityError

from app.models import User


async def test_user_plan_defaults_to_free(session):
    user = User(email="a@example.com", hashed_password="x")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    assert user.plan == "free"


async def test_user_plan_rejects_unknown_value(session):
    session.add(User(email="b@example.com", hashed_password="x", plan="gold"))
    with pytest.raises(IntegrityError):
        await session.commit()
