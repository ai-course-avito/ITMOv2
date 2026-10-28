from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator, model_validator

from app.contract.vocabulary import (
    CONTRACT_VERSION,
    CalculationMode,
    CalculationStatus,
    DemoId,
    DemoStatus,
    Route,
    Topic,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Breadcrumb(StrictModel):
    label: str = Field(min_length=1)
    href: str = Field(min_length=1)


class NavigationLink(StrictModel):
    label: str = Field(min_length=1)
    href: Route


class Page(StrictModel):
    contract_version: str = CONTRACT_VERSION
    route: Route
    topic: Topic
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    heading: str = Field(min_length=1)
    sections: list[str] = Field(min_length=1)
    canonical: Route
    breadcrumb: list[Breadcrumb] = Field(default_factory=list)
    navigation: list[NavigationLink] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identity(self) -> "Page":
        if self.route != self.canonical:
            raise ValueError("canonical must match route")
        if self.route == "/" and self.breadcrumb:
            raise ValueError("home page must not have breadcrumbs")
        if self.route != "/" and not self.breadcrumb:
            raise ValueError("non-home pages require breadcrumbs")
        return self


class ContractError(StrictModel):
    code: str = Field(min_length=1)
    field: str = Field(min_length=1)
    message: str = Field(min_length=1)
    constraint: str = Field(min_length=1)
    retryable: bool = False


class CalculationInfo(StrictModel):
    mode: CalculationMode
    status: CalculationStatus
    operation: str = Field(min_length=1)
    request_id: str | None = None


class DemoState(StrictModel):
    contract_version: str = CONTRACT_VERSION
    demo_id: DemoId
    status: DemoStatus
    parameters: dict[str, Any]
    time: FiniteFloat = Field(ge=0.0, le=1.0)
    frame: int = Field(ge=0, strict=True)
    formula_highlight: int | None = Field(default=None, ge=0, strict=True)
    calculation: CalculationInfo
    error: ContractError | None = None

    @field_validator("frame")
    @classmethod
    def reject_bool_frame(cls, value: int) -> int:
        if isinstance(value, bool):
            raise ValueError("frame must be an integer")
        return value

    @model_validator(mode="after")
    def validate_error_state(self) -> "DemoState":
        if self.status == "error" and self.error is None:
            raise ValueError("error status requires error details")
        if self.status != "error" and self.error is not None:
            raise ValueError("error details require error status")
        return self
