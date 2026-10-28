import numpy as np

from app.math.chebyshev import nodes


TARGETS = {
    "runge": lambda x: 1.0 / (1.0 + 25.0 * x * x),
    "cosine": np.cos,
}


def _weights(x: np.ndarray) -> np.ndarray:
    weights = np.ones(len(x), dtype=np.float64)
    for index in range(len(x)):
        differences = x[index] - np.delete(x, index)
        weights[index] = 1.0 / np.prod(differences)
    weights /= np.max(np.abs(weights))
    return weights


def barycentric(node_x: np.ndarray, node_y: np.ndarray, evaluation_x: np.ndarray) -> np.ndarray:
    weights = _weights(node_x)
    result = np.empty_like(evaluation_x, dtype=np.float64)
    for index, point in enumerate(evaluation_x):
        match = np.flatnonzero(np.isclose(point, node_x, rtol=0.0, atol=8 * np.finfo(float).eps * max(1.0, abs(point))))
        if len(match):
            result[index] = node_y[match[0]]
            continue
        terms = weights / (point - node_x)
        denominator = np.sum(terms)
        if denominator == 0.0 or not np.isfinite(denominator):
            raise FloatingPointError("interpolation denominator is non-finite")
        result[index] = np.sum(terms * node_y) / denominator
    if not np.all(np.isfinite(result)):
        raise FloatingPointError("interpolation produced non-finite output")
    return result


def compare(target: str, interval: tuple[float, float], node_count: int, grid: list[float]) -> dict:
    function = TARGETS[target]
    evaluation_x = np.asarray(grid, dtype=np.float64)
    left, right = interval
    unit = np.linspace(-1.0, 1.0, node_count)
    uniform_x = (left + right) / 2.0 + (right - left) / 2.0 * unit
    chebyshev_x = nodes("roots", node_count, interval)
    target_uniform = function(uniform_x)
    target_chebyshev = function(chebyshev_x)
    target_grid = function(evaluation_x)
    results = {}
    for name, node_x, node_y in (
        ("chebyshev", chebyshev_x, target_chebyshev),
        ("uniform", uniform_x, target_uniform),
    ):
        approximation = barycentric(node_x, node_y, evaluation_x)
        error = approximation - target_grid
        results[name] = {
            "nodes": node_x.tolist(),
            "approximation": approximation.tolist(),
            "pointwise_error": error.tolist(),
            "max_absolute_error": float(np.max(np.abs(error))),
        }
    return {"x": evaluation_x.tolist(), "target": target_grid.tolist(), "results": results}
