from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

TWO_PLACES = Decimal("0.01")


def _money_to_str(value: Decimal) -> str:
    return format(value.quantize(TWO_PLACES), "f")


# A Decimal that is serialized as a string with exactly two decimal places.
MoneyStr = Annotated[Decimal, PlainSerializer(_money_to_str, return_type=str)]
