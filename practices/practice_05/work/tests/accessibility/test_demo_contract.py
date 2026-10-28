from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_demos_have_fallback_and_shared_runtime_bindings():
    fourier = (ROOT / "fourier/index.html").read_text()
    chebyshev = (ROOT / "chebyshev/index.html").read_text()
    assert "demo-state.js" in fourier
    assert "demos/fourier.js" in fourier
    assert "demo-state.js" in chebyshev
    assert "demos/chebyshev.js" in chebyshev
    assert "Текстовая альтернатива" in fourier
    assert "Текстовая альтернатива" in chebyshev
