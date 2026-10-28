from pathlib import Path


def test_mathjax_uses_shared_configuration_and_scoped_helper():
    root = Path(__file__).resolve().parents[2]
    mathjax = (root / "static/js/mathjax.js").read_text()
    fourier = (root / "fourier/index.html").read_text()
    assert "typesetPromise(nodes || undefined)" in mathjax
    assert "inlineMath" in mathjax
    assert "displayMath" in mathjax
    assert "data-testid=\"fourier-plot\"" in fourier
