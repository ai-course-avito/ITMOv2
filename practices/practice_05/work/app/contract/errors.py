from __future__ import annotations

from app.contract.models import ContractError


HTTP_STATUS_BY_CODE = {
    "MALFORMED_JSON": 400,
    "INVALID_CONTENT_TYPE": 400,
    "UNSUPPORTED_OPERATION": 400,
    "UNSUPPORTED_VERSION": 400,
    "SERVICE_UNAVAILABLE": 503,
    "TIMEOUT": 504,
}


def make_error(code: str, field: str, message: str, constraint: str, *, retryable: bool = False) -> ContractError:
    return ContractError(
        code=code,
        field=field,
        message=message,
        constraint=constraint,
        retryable=retryable,
    )


def status_for_error(code: str) -> int:
    return HTTP_STATUS_BY_CODE.get(code, 422)
