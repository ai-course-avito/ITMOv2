from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("plan IN ('free', 'pro')", name="ck_users_plan"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    default_currency: Mapped[str] = mapped_column(String(3), default="USD")
    plan: Mapped[str] = mapped_column(String(10), default="free", server_default="free")

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="owner")


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_subscriptions_amount_positive"),
        CheckConstraint(
            "billing_cycle IN ('monthly', 'yearly', 'weekly', 'custom_days')",
            name="ck_subscriptions_billing_cycle",
        ),
        CheckConstraint(
            "(billing_cycle = 'custom_days' AND custom_interval_days IS NOT NULL "
            "AND custom_interval_days BETWEEN 1 AND 3650) "
            "OR (billing_cycle <> 'custom_days' AND custom_interval_days IS NULL)",
            name="ck_subscriptions_custom_interval",
        ),
        CheckConstraint(
            "start_date BETWEEN '2000-01-01' AND '2100-12-31' "
            "AND next_billing_date BETWEEN '2000-01-01' AND '2100-12-31'",
            name="ck_subscriptions_dates_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    billing_cycle: Mapped[str] = mapped_column(String(20))
    custom_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    start_date: Mapped[date] = mapped_column(Date, default=date.today)
    next_billing_date: Mapped[date] = mapped_column(Date, default=date.today)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    owner: Mapped["User"] = relationship(back_populates="subscriptions")
