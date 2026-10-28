from pathlib import Path


def test_pages_have_canonical_metadata():
    root = Path(__file__).resolve().parents[2]
    for route in ["index.html", "fourier/index.html", "chebyshev/index.html", "approximation/index.html", "demos/index.html", "about/index.html"]:
        html = (root / route).read_text()
        assert 'rel="canonical"' in html
        assert '<meta name="description"' in html
