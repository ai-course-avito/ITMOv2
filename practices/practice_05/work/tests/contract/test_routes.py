from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROUTES = ["index.html", "fourier/index.html", "chebyshev/index.html", "approximation/index.html", "demos/index.html", "about/index.html"]


def test_required_pages_exist_and_have_landmarks():
    for route in ROUTES:
        content = (ROOT / route).read_text()
        assert "<h1>" in content
        assert "<main>" in content
        assert "<nav" in content
        assert 'rel="canonical"' in content
