from decimal import Decimal

from pydantic import BaseModel, field_serializer

from app.schemas.types import MoneyStr


class StatsSummaryResponse(BaseModel):
    monthly_total: Decimal
    yearly_total: Decimal
    currency: str

    @field_serializer("monthly_total", "yearly_total")
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)


class SubscriptionShare(BaseModel):
    id: int
    name: str
    billing_cycle: str
    monthly_cost: MoneyStr
    share_percent: MoneyStr


class CycleShare(BaseModel):
    billing_cycle: str
    subscription_count: int
    monthly_cost: MoneyStr
    share_percent: MoneyStr


class StatsBreakdownResponse(BaseModel):
    currency: str
    monthly_total: MoneyStr
    by_subscription: list[SubscriptionShare]
    by_cycle: list[CycleShare]
