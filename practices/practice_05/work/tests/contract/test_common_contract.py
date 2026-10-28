import pytest
from pydantic import ValidationError

from app.contract.models import ContractError, DemoState, Page


def page_payload(route: str = "/") -> dict:
    return {
        "route": route,
        "topic": "home" if route == "/" else "about",
        "title": "Test page",
        "description": "Test description",
        "heading": "Test heading",
        "sections": ["hero"],
        "canonical": route,
        "breadcrumb": [] if route == "/" else [{"label": "Главная", "href": "/"}],
        "navigation": [{"label": "Главная", "href": "/"}],
    }


def test_page_requires_breadcrumbs_outside_home() -> None:
    Page.model_validate(page_payload())
    with pytest.raises(ValidationError):
        Page.model_validate(page_payload("/about/") | {"breadcrumb": []})


def test_demo_state_requires_error_details_for_error_status() -> None:
    payload = {
        "demo_id": "fourier-square-wave",
        "status": "error",
        "parameters": {"order": 3},
        "time": 0,
        "frame": 0,
        "calculation": {"mode": "local", "status": "error", "operation": "fourier_partial_sum"},
    }
    with pytest.raises(ValidationError):
        DemoState.model_validate(payload)

    payload["error"] = {
        "code": "VALIDATION_ERROR",
        "field": "parameters.order",
        "message": "Некорректный порядок",
        "constraint": "1 <= order <= 10000",
    }
    assert DemoState.model_validate(payload).contract_version == "v1"


def test_contract_error_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ContractError(
            code="VALIDATION_ERROR",
            field="body",
            message="bad",
            constraint="fix it",
            unexpected=True,
        )
