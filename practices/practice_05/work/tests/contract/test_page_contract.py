from pathlib import Path

from app.contract.pages import PAGES


ROOT = Path(__file__).resolve().parents[2]
HTML_BY_ROUTE = {
    "/": "index.html",
    "/fourier/": "fourier/index.html",
    "/chebyshev/": "chebyshev/index.html",
    "/approximation/": "approximation/index.html",
    "/demos/": "demos/index.html",
    "/about/": "about/index.html",
}


def test_page_registry_covers_all_required_routes() -> None:
    assert set(PAGES) == set(HTML_BY_ROUTE)
    assert len({page.title for page in PAGES.values()}) == len(PAGES)


def test_html_routes_expose_contract_landmarks_and_navigation() -> None:
    required_hrefs = set(HTML_BY_ROUTE)
    for route, relative_path in HTML_BY_ROUTE.items():
        html = (ROOT / relative_path).read_text()
        assert html.count("<h1") == 1
        assert all(marker in html for marker in ("<header", "<nav", "<main", "<footer"))
        assert '<link rel="canonical"' in html
        assert all(f'href="{href}"' in html for href in required_hrefs)
