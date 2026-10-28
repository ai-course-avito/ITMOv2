from pathlib import Path


def test_demo_contract_selectors_exist():
    root = Path(__file__).resolve().parents[2]
    fourier = (root / "fourier/index.html").read_text()
    chebyshev = (root / "chebyshev/index.html").read_text()
    assert 'data-demo-id="fourier-square-wave"' in fourier
    assert 'data-testid="fourier-plot"' in fourier
    assert 'role="status"' in fourier
    assert 'data-demo-id="chebyshev-interpolation"' in chebyshev
    assert 'data-node-count' in chebyshev
