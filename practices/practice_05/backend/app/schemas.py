from datetime import date
import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

IataCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
MarketCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]


class FareSearch(BaseModel):
    origin: IataCode
    destination: IataCode
    departure_date: date
    market: MarketCode = "RU"
    direct: bool = False
    max_price: int | None = Field(default=None, gt=0)

    @field_validator("departure_date", mode="before")
    @classmethod
    def full_departure_date(cls, value: object) -> object:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Укажите полную дату вылета в формате YYYY-MM-DD.")
        return value

    @field_validator("departure_date")
    @classmethod
    def future_departure(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("Дата вылета уже прошла.")
        return value

    @model_validator(mode="after")
    def different_airports(self) -> "FareSearch":
        if self.origin == self.destination:
            raise ValueError("Пункты отправления и назначения должны отличаться.")
        return self


class RoundTripSearch(FareSearch):
    return_date: date

    @field_validator("return_date", mode="before")
    @classmethod
    def full_return_date(cls, value: object) -> object:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Укажите полную дату возвращения в формате YYYY-MM-DD.")
        return value

    @model_validator(mode="after")
    def valid_return(self) -> "RoundTripSearch":
        if self.return_date < self.departure_date:
            raise ValueError("Дата возвращения должна быть не раньше даты вылета.")
        return self


class Price(BaseModel):
    amount: float = Field(ge=0)
    currency: str
    status: str | None = None


class Segment(BaseModel):
    marketing_carrier_code: str | None = None
    flight_number: str | None = None
    operating_carrier_name: str | None = None
    departure_airport: IataCode
    departure_time_local: str
    arrival_airport: IataCode
    arrival_time_local: str
    duration_minutes: int | None = None


class Leg(BaseModel):
    carrier: str | None = None
    duration_minutes: int | None = None
    segments: list[Segment] = Field(min_length=1)
    stops: int = Field(ge=0)


class Itinerary(BaseModel):
    ignav_id: str
    price: Price
    outbound: Leg
    inbound: Leg | None = None
    requires_self_transfer: bool = False


class PriceComparison(BaseModel):
    status: Literal["compared", "no_previous_price", "no_current_price", "currency_mismatch"]
    previous_price: float | None = None
    current_price: float | None = None
    previous_currency: str | None = None
    current_currency: str | None = None
    difference: float | None = None
    percent_difference: float | None = None
    previous_search_at: str | None = None
    current_search_at: str


class FareSearchResponse(BaseModel):
    itineraries: list[Itinerary]
    observed_at: str | None = None
    cache_hit: bool = False
    comparison: PriceComparison | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
