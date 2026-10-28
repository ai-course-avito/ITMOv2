from typing import Final, Literal

CONTRACT_VERSION: Final = "v1"

Route = Literal["/", "/fourier/", "/chebyshev/", "/approximation/", "/demos/", "/about/"]
Topic = Literal[
    "home",
    "fourier-series",
    "chebyshev-polynomials",
    "approximation-theory",
    "demonstrations",
    "about",
]
DemoId = Literal["fourier-square-wave", "chebyshev-interpolation"]
DemoStatus = Literal["idle", "playing", "paused", "stepping", "completed", "error"]
CalculationMode = Literal["local", "service"]
CalculationStatus = Literal["pending", "ready", "error"]

REQUIRED_ROUTES: Final[tuple[Route, ...]] = (
    "/",
    "/fourier/",
    "/chebyshev/",
    "/approximation/",
    "/demos/",
    "/about/",
)
OPERATIONS: Final[tuple[str, ...]] = (
    "fourier_partial_sum",
    "chebyshev_values",
    "chebyshev_nodes",
    "interpolation_comparison",
)
ERROR_CODES: Final[tuple[str, ...]] = (
    "MALFORMED_JSON",
    "INVALID_CONTENT_TYPE",
    "VALIDATION_ERROR",
    "MISSING_FIELD",
    "INVALID_TYPE",
    "NON_FINITE_VALUE",
    "INVALID_INTERVAL",
    "OUT_OF_RANGE",
    "RESOURCE_LIMIT",
    "UNSUPPORTED_OPERATION",
    "UNSUPPORTED_VERSION",
    "NUMERICAL_ERROR",
    "INVALID_RESPONSE",
    "SERVICE_UNAVAILABLE",
    "TIMEOUT",
    "CANCELLED",
)
