from decimal import Decimal


def price_change(previous: Decimal, current: Decimal) -> tuple[float, float | None]:
    """Signed change; a percentage relative to zero is undefined."""
    if not previous.is_finite() or not current.is_finite() or min(previous, current) < 0:
        raise ValueError("Цены должны быть конечными неотрицательными числами.")
    difference = current - previous
    return float(difference), float(difference / previous * 100) if previous else None
