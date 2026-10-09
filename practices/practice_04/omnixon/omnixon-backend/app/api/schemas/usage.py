from datetime import date
from typing import Optional

from pydantic import BaseModel


class UsageRow(BaseModel):
    token_id: Optional[int] = None  # None: the token has been deleted
    token_name: str
    model: str
    requests: int
    errors: int
    input_tokens: int
    output_tokens: int
    cost: float  # the sum of what the provider reported; calls without a price add nothing
    duration_ms_sum: int


class DailyUsage(UsageRow):
    day: date


class MonthlyUsage(UsageRow):
    month: date
