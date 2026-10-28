import numpy as np


def partial_sum(order: int, x_values: list[float]) -> np.ndarray:
    x = np.asarray(x_values, dtype=np.float64)
    harmonics = 2 * np.arange(order, dtype=np.float64) + 1.0
    result = (4.0 / np.pi) * np.sum(np.sin(harmonics[:, None] * x[None, :]) / harmonics[:, None], axis=0)
    if not np.all(np.isfinite(result)):
        raise FloatingPointError("Fourier calculation produced non-finite output")
    return result
