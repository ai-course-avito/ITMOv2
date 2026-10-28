from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator


MAX_VALUES = 10_000
MAX_ORDER = 10_000
MAX_INTERPOLATION_NODES = 256
MAX_WORK = 10_000_000
MAX_BODY_BYTES = 250_000


def parse_interval(value: Any) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("interval must contain exactly two finite numbers")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        raise ValueError("interval must contain exactly two finite numbers")
    from math import isfinite

    if not all(isfinite(item) for item in value):
        raise ValueError("interval must contain exactly two finite numbers")
    return (float(value[0]), float(value[1]))


class RequestEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    operation: Literal[
        "fourier_partial_sum",
        "chebyshev_values",
        "chebyshev_nodes",
        "interpolation_comparison",
    ]
    contract_version: Literal["v1"]
    parameters: dict[str, Any]


class FourierParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    order: int = Field(ge=1, le=MAX_ORDER, strict=True)
    x_values: list[FiniteFloat] | None = Field(default=None, min_length=1, max_length=MAX_VALUES)
    interval: tuple[FiniteFloat, FiniteFloat] | None = None
    sample_count: int | None = Field(default=None, ge=1, le=MAX_VALUES, strict=True)

    @field_validator("interval", mode="before")
    @classmethod
    def interval_from_json(cls, value: Any) -> tuple[float, float] | None:
        return None if value is None else parse_interval(value)

    @field_validator("order", "sample_count")
    @classmethod
    def reject_bool(cls, value: int | None) -> int | None:
        if isinstance(value, bool):
            raise ValueError("must be an integer")
        return value

    def model_post_init(self, __context: Any) -> None:
        explicit = self.x_values is not None
        sampled = self.interval is not None or self.sample_count is not None
        if explicit == sampled or (sampled and (self.interval is None or self.sample_count is None)):
            raise ValueError("provide either x_values or interval with sample_count")
        if self.interval is not None and self.interval[0] >= self.interval[1]:
            raise ValueError("interval must be strictly increasing")
        if self.order * (len(self.x_values) if self.x_values else self.sample_count or 0) > MAX_WORK:
            raise ValueError("requested computation exceeds the work limit")


class ChebyshevValueParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["first", "second"]
    order: int = Field(ge=0, le=MAX_ORDER, strict=True)
    x_values: list[FiniteFloat] = Field(min_length=1, max_length=MAX_VALUES)

    @field_validator("order")
    @classmethod
    def reject_bool(cls, value: int) -> int:
        if isinstance(value, bool):
            raise ValueError("must be an integer")
        return value

    @field_validator("x_values")
    @classmethod
    def validate_domain(cls, values: list[float]) -> list[float]:
        if any(value < -1.0 - 1e-15 or value > 1.0 + 1e-15 for value in values):
            raise ValueError("x_values must be within [-1, 1]")
        return [min(1.0, max(-1.0, value)) for value in values]


class ChebyshevNodeParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: Literal["roots", "extrema"]
    count: int = Field(ge=1, le=MAX_VALUES, strict=True)
    interval: tuple[FiniteFloat, FiniteFloat] = (-1.0, 1.0)

    @field_validator("interval", mode="before")
    @classmethod
    def interval_from_json(cls, value: Any) -> tuple[float, float]:
        return parse_interval(value)

    @field_validator("count")
    @classmethod
    def validate_count(cls, value: int, info: Any) -> int:
        if isinstance(value, bool):
            raise ValueError("must be an integer")
        if info.data.get("kind") == "extrema" and value < 2:
            raise ValueError("extrema count must be at least 2")
        return value

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, value: tuple[float, float]) -> tuple[float, float]:
        if value[0] >= value[1]:
            raise ValueError("interval must be strictly increasing")
        return value


class InterpolationParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    target: Literal["runge", "cosine"]
    interval: tuple[FiniteFloat, FiniteFloat] = (-1.0, 1.0)
    node_count: int = Field(ge=2, le=MAX_INTERPOLATION_NODES, strict=True)
    evaluation_grid: list[FiniteFloat] = Field(min_length=1, max_length=MAX_VALUES)

    @field_validator("interval", mode="before")
    @classmethod
    def interval_from_json(cls, value: Any) -> tuple[float, float]:
        return parse_interval(value)

    @field_validator("node_count")
    @classmethod
    def reject_bool(cls, value: int) -> int:
        if isinstance(value, bool):
            raise ValueError("must be an integer")
        return value

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, value: tuple[float, float]) -> tuple[float, float]:
        if value[0] >= value[1]:
            raise ValueError("interval must be strictly increasing")
        return value

    @field_validator("evaluation_grid")
    @classmethod
    def validate_grid(cls, values: list[float], info: Any) -> list[float]:
        interval = info.data.get("interval", (-1.0, 1.0))
        if any(value < interval[0] or value > interval[1] for value in values):
            raise ValueError("evaluation_grid must lie inside interval")
        return values


class Tolerance(BaseModel):
    dtype: str = "float64"
    rtol: float = 1e-10
    atol: float = 1e-12


class NumericalSeries(BaseModel):
    x: list[FiniteFloat]
    y: list[FiniteFloat]
    domain: dict[str, Any]


class ErrorSummary(BaseModel):
    strategy: str
    pointwise_error: list[FiniteFloat]
    max_absolute_error: FiniteFloat


class ServiceMetadata(BaseModel):
    operation: str
    contract_version: str
    normalized_parameters: dict[str, Any]
    domain: dict[str, Any]
    tolerance: Tolerance
    duration_ms: float
    cache_status: Literal["hit", "miss"]
    result: dict[str, Any] = {"ordering": "request_order", "finite": True}


class CalculationResponse(BaseModel):
    operation: str
    contract_version: str
    data: dict[str, Any]
    metadata: ServiceMetadata


class ErrorDetail(BaseModel):
    code: str
    field: str
    message: str
    constraint: str
    retryable: bool = False


class ErrorResponse(BaseModel):
    error: ErrorDetail
    contract_version: str = "v1"
