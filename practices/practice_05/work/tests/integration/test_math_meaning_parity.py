from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_fourier_and_chebyshev_pages_use_contract_parameter_vocabulary():
    fourier = (ROOT / "fourier/index.html").read_text()
    chebyshev = (ROOT / "chebyshev/index.html").read_text()
    assert "Порядок частичной суммы" in fourier
    assert "data-node-count" in chebyshev
    assert "Текстовая альтернатива" in fourier
    assert "Текстовая альтернатива" in chebyshev
