from __future__ import annotations

import math
from typing import Any


def normalize_interval(value: tuple[float, float] | list[float]) -> list[float]:
    left, right = (float(value[0]), float(value[1]))
    if not math.isfinite(left) or not math.isfinite(right) or left >= right:
        raise ValueError("interval must contain finite, strictly increasing endpoints")
    return [left, right]


def normalize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: normalize_json(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [normalize_json(item) for item in value]
    if isinstance(value, list):
        return [normalize_json(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("numeric values must be finite")
        return float(value)
    return value


def within_tolerance(actual: float, expected: float, *, rtol: float = 1e-10, atol: float = 1e-12) -> bool:
    return abs(actual - expected) <= atol + rtol * abs(expected)
