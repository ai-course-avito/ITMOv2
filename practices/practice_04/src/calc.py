def add(a, b):
    """Simple addition with type coercion to float where possible."""
    try:
        return float(a) + float(b)
    except (TypeError, ValueError):
        raise ValueError("add expects numbers or numeric strings")


def avg(values, ndigits=None):
    """Average of an iterable of numeric values.

    Empty iterable raises ValueError.
    Optional rounding to `ndigits` decimal places.
    """
    vals = list(values)
    if not vals:
        raise ValueError("avg expects a non-empty iterable")
    total = 0.0
    for v in vals:
        try:
            total += float(v)
        except (TypeError, ValueError):
            raise ValueError("avg expects numbers or numeric strings")
    result = total / len(vals)
    if ndigits is None:
        return result
    try:
        return round(result, int(ndigits))
    except Exception:
        raise ValueError("ndigits must be an integer or None")

def median(values):
    """Median of an iterable of numeric values.

    For even-length lists, returns the average of the two middle values.
    """
    vals = sorted([float(v) for v in values])
    n = len(vals)
    if n == 0:
        raise ValueError("median expects a non-empty iterable")
    mid = n // 2
    if n % 2 == 1:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2.0
