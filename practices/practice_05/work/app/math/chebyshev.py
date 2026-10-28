import numpy as np


def values(kind: str, order: int, x_values: list[float]) -> np.ndarray:
    x = np.asarray(x_values, dtype=np.float64)
    if order == 0:
        return np.ones_like(x)
    previous = np.ones_like(x)
    current = x.copy() if kind == "first" else 2.0 * x
    if order == 1:
        return current
    for _ in range(1, order):
        previous, current = current, 2.0 * x * current - previous
    if not np.all(np.isfinite(current)):
        raise FloatingPointError("Chebyshev calculation produced non-finite output")
    return current


def nodes(kind: str, count: int, interval: tuple[float, float]) -> np.ndarray:
    if kind == "roots":
        unit = np.cos((2.0 * np.arange(count) + 1.0) * np.pi / (2.0 * count))[::-1]
    else:
        unit = np.cos(np.arange(count - 1, -1, -1) * np.pi / (count - 1))
    left, right = interval
    result = (left + right) / 2.0 + (right - left) / 2.0 * unit
    result = np.clip(result, left, right)
    if not np.all(np.isfinite(result)):
        raise FloatingPointError("Chebyshev node calculation produced non-finite output")
    return result
