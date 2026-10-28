import math


def fourier_partial_sum_square_wave_coeff(n):
    # a_n = 0, b_n = 4/(pi*(2k-1)) for odd n; simple helper
    if n % 2 == 0:
        return 0.0
    k = (n + 1) // 2
    return 4.0 / (math.pi * (2 * k - 1))


def test_fourier_coefficients_basic():
    # spot-check few odd terms
    assert math.isclose(fourier_partial_sum_square_wave_coeff(1), 4 / math.pi, rel_tol=1e-9)
    assert math.isclose(
        fourier_partial_sum_square_wave_coeff(3), 4 / (3 * math.pi), rel_tol=1e-9
    )
    # even terms zero
    assert fourier_partial_sum_square_wave_coeff(2) == 0.0


def chebyshev_T(n, x):
    # T_n(cos(theta)) = cos(n*theta)
    return math.cos(n * math.acos(max(-1.0, min(1.0, x))))


def test_chebyshev_properties():
    # T_0(x)=1, T_1(x)=x, T_n(1)=1, T_n(-1)=(-1)^n
    assert chebyshev_T(0, 0.3) == 1.0
    assert math.isclose(chebyshev_T(1, 0.5), 0.5, rel_tol=1e-12)
    assert math.isclose(chebyshev_T(5, 1.0), 1.0, rel_tol=1e-12)
    assert math.isclose(chebyshev_T(4, -1.0), 1.0, rel_tol=1e-12)
