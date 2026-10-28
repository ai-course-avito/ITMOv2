from pathlib import Path


def test_pages_have_descriptions_and_footer():
    root = Path(__file__).resolve().parents[2]
    for route in ["index.html", "fourier/index.html", "chebyshev/index.html", "approximation/index.html", "demos/index.html", "about/index.html"]:
        html = (root / route).read_text()
        assert '<meta name="description"' in html
        assert "<footer" in html
        assert 'aria-label="Основная навигация"' in html
