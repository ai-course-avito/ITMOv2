from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    model_validator,
)

from app.schemas.types import MoneyStr

TWO_PLACES = Decimal("0.01")


class BillingCycle(StrEnum):
    monthly = "monthly"
    yearly = "yearly"
    weekly = "weekly"
    custom_days = "custom_days"


Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
Amount = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
MIN_DATE = date(2000, 1, 1)
MAX_DATE = date(2100, 12, 31)
MAX_INTERVAL_DAYS = 3650
BoundedDate = Annotated[date, Field(ge=MIN_DATE, le=MAX_DATE)]


class SubscriptionCreate(BaseModel):
    """Also used to validate the merged state of a PATCH."""

    name: Name
    amount: Amount
    billing_cycle: BillingCycle
    custom_interval_days: int | None = Field(default=None, gt=0, le=MAX_INTERVAL_DAYS)
    start_date: BoundedDate
    next_billing_date: BoundedDate | None = None
    note: str | None = Field(default=None, max_length=500)
    is_active: bool = True

    @model_validator(mode="after")
    def check_cross_field_rules(self) -> Self:
        if self.billing_cycle == BillingCycle.custom_days:
            if self.custom_interval_days is None:
                raise ValueError("custom_interval_days is required for custom_days")
        elif self.custom_interval_days is not None:
            raise ValueError("custom_interval_days is only allowed for custom_days")
        if (
            self.next_billing_date is not None
            and self.next_billing_date < self.start_date
        ):
            raise ValueError("next_billing_date must not be earlier than start_date")
        return self


class SubscriptionUpdate(BaseModel):
    """Partial update: only fields present in the request are applied."""

    name: str | None = None
    amount: Decimal | None = None
    billing_cycle: str | None = None
    custom_interval_days: int | None = None
    start_date: date | None = None
    next_billing_date: date | None = None
    note: str | None = None
    is_active: bool | None = None


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    amount: Decimal
    billing_cycle: str
    custom_interval_days: int | None
    is_active: bool
    start_date: date
    next_billing_date: date
    note: str | None

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return format(value.quantize(TWO_PLACES), "f")


class UpcomingCharge(BaseModel):
    id: int
    name: str
    amount: Decimal
    billing_cycle: str
    charge_date: date
    days_until: int

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return format(value.quantize(TWO_PLACES), "f")


class SortField(StrEnum):
    id = "id"
    name = "name"
    amount = "amount"
    monthly_cost = "monthly_cost"
    charge_date = "charge_date"


class SortOrder(StrEnum):
    asc = "asc"
    desc = "desc"


class SubscriptionListItem(SubscriptionRead):
    """A subscription as shown in the list, with read-only computed fields."""

    monthly_cost: MoneyStr
    charge_date: date | None
    days_until: int | None
