import asyncio
from decimal import Decimal

import pytest

from app.mcp_demo import demonstrate
from app.price_math import price_change


def test_real_mcp_stdio_calls():
    result = asyncio.run(demonstrate())
    assert result["database_unchanged"]


@pytest.mark.parametrize("previous,current,expected", [
    ("4000", "3500", (-500.0, -12.5)),
    ("100", "125", (25.0, 25.0)),
    ("100", "100", (0.0, 0.0)),
    ("0", "100", (100.0, None)),
])
def test_shared_price_calculation(previous, current, expected):
    assert price_change(Decimal(previous), Decimal(current)) == expected
