from __future__ import annotations

import json
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from app.api.models import (
    CalculationResponse,
    ChebyshevNodeParameters,
    ChebyshevValueParameters,
    ErrorResponse,
    FourierParameters,
    InterpolationParameters,
    ServiceMetadata,
    Tolerance,
)
from app.math.chebyshev import nodes, values
from app.math.fourier import partial_sum
from app.math.interpolation import compare
from app.services.cache import LRUCache
from app.contract.errors import make_error


class CalculationError(Exception):
    def __init__(self, code: str, field: str, message: str, constraint: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code, self.field, self.message, self.constraint, self.status_code = code, field, message, constraint, status_code


cache = LRUCache()


def _error_from_validation(exc: ValidationError) -> CalculationError:
    first = exc.errors()[0]
    location = ".".join(str(item) for item in first.get("loc", ())) or "parameters"
    return CalculationError("VALIDATION_ERROR", location, first["msg"], "see the field constraint")


def calculate(operation: str, version: str, raw_parameters: dict[str, Any]) -> CalculationResponse:
    started = perf_counter()
    if version != "v1":
        raise CalculationError("UNSUPPORTED_VERSION", "contract_version", "unsupported contract version", "contract_version must be v1", 400)
    try:
        if operation == "fourier_partial_sum":
            parameters = FourierParameters.model_validate(raw_parameters)
            x_values = parameters.x_values or [
                value for value in __import__("numpy").linspace(*parameters.interval, parameters.sample_count)
            ]
            normalized = parameters.model_dump(mode="json")
            result = {"x": x_values, "y": partial_sum(parameters.order, x_values).tolist()}
            domain = {"kind": "periodic", "unit": "radian"}
        elif operation == "chebyshev_values":
            parameters = ChebyshevValueParameters.model_validate(raw_parameters)
            x_values = parameters.x_values
            normalized = parameters.model_dump(mode="json")
            result = {"x": x_values, "y": values(parameters.kind, parameters.order, x_values).tolist()}
            domain = {"kind": "polynomial", "interval": [-1.0, 1.0], "polynomial_kind": parameters.kind}
        elif operation == "chebyshev_nodes":
            parameters = ChebyshevNodeParameters.model_validate(raw_parameters)
            normalized = parameters.model_dump(mode="json")
            result = {"nodes": nodes(parameters.kind, parameters.count, parameters.interval).tolist()}
            domain = {"kind": "nodes", "node_convention": parameters.kind, "ordering": "ascending", "interval": list(parameters.interval)}
        elif operation == "interpolation_comparison":
            parameters = InterpolationParameters.model_validate(raw_parameters)
            normalized = parameters.model_dump(mode="json")
            result = compare(parameters.target, parameters.interval, parameters.node_count, parameters.evaluation_grid)
            domain = {"kind": "interpolation", "target": parameters.target, "interval": list(parameters.interval)}
        else:
            raise CalculationError("UNSUPPORTED_OPERATION", "operation", "unsupported operation", "use a documented v1 operation", 400)
    except ValidationError as exc:
        raise _error_from_validation(exc) from exc
    except (FloatingPointError, ValueError) as exc:
        raise CalculationError("NUMERICAL_ERROR", "operation", str(exc), "all calculated values must be finite") from exc

    key = json.dumps([operation, version, normalized], sort_keys=True, separators=(",", ":"))
    cached = cache.get(key)
    if cached is not None:
        result, domain = cached
        cache_status = "hit"
    else:
        cache.put(key, (result, domain))
        cache_status = "miss"
    metadata = ServiceMetadata(
        operation=operation,
        contract_version=version,
        normalized_parameters=normalized,
        domain=domain,
        tolerance=Tolerance(),
        duration_ms=(perf_counter() - started) * 1000.0,
        cache_status=cache_status,
    )
    return CalculationResponse(operation=operation, contract_version=version, data=result, metadata=metadata)


def error_response(error: CalculationError) -> ErrorResponse:
    return ErrorResponse.model_validate({
        "error": {
            "code": error.code,
            "field": error.field,
            "message": error.message,
            "constraint": error.constraint,
            "retryable": error.code in {"SERVICE_UNAVAILABLE", "TIMEOUT"},
        }
    })
