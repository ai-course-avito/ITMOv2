import pytest

from app.calculator import CalculatorError, calculate


def test_calculate_adds_two_ints_and_returns_int():
    result = calculate("2 + 2")

    assert result == 4
    assert type(result) is int


def test_calculate_adds_two_floats_and_returns_float():
    result = calculate("1.5 + 2.25")

    assert result == 3.75
    assert type(result) is float


def test_calculate_adds_int_and_float_and_returns_float():
    result = calculate("2 + 0.5")

    assert result == 2.5
    assert type(result) is float


def test_calculate_ignores_spaces_around_operands():
    assert calculate("  7+8  ") == 15


def test_calculate_adds_negative_numbers():
    assert calculate("-3 + 5") == 2


def test_calculate_subtracts():
    assert calculate("10 - 4") == 6


def test_calculate_multiplies():
    assert calculate("6 * 7") == 42


def test_calculate_divides_exact_ints_and_returns_int():
    result = calculate("8 / 2")

    assert result == 4
    assert type(result) is int


def test_calculate_divides_ints_with_remainder_and_returns_float():
    assert calculate("7 / 2") == 3.5


def test_calculate_respects_operator_precedence():
    assert calculate("2 + 3 * 4") == 14


def test_calculate_respects_parentheses():
    assert calculate("(2 + 3) * 4") == 20


@pytest.mark.parametrize("expression", ["", "   ", "abc", "2 +", "(2 + 3", "2 $ 3"])
def test_calculate_rejects_malformed_input(expression):
    with pytest.raises(CalculatorError):
        calculate(expression)


@pytest.mark.parametrize("expression", ["2 ** 3", "__import__('os')", "'a' + 'b'", "2 + True", "1 if 1 else 2"])
def test_calculate_rejects_unsupported_syntax(expression):
    with pytest.raises(CalculatorError):
        calculate(expression)


@pytest.mark.parametrize("expression", ["1 / 0", "1 / 0.0", "5 / (2 - 2)"])
def test_calculate_rejects_division_by_zero(expression):
    with pytest.raises(CalculatorError):
        calculate(expression)
