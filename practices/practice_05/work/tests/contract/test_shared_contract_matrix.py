from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_shared_contract_matrix_has_all_required_routes_and_contract_docs():
    routes = ["/", "/fourier/", "/chebyshev/", "/approximation/", "/demos/", "/about/"]
    html_files = ["index.html", "fourier/index.html", "chebyshev/index.html", "approximation/index.html", "demos/index.html", "about/index.html"]
    for route, filename in zip(routes, html_files):
        html = (ROOT / filename).read_text()
        assert f'href="{route}"' in html
        assert '<link rel="canonical"' in html
        assert html.count("<h1") == 1
    assert (ROOT / "specs/001-common-contract/contracts/math-api.md").exists()
    assert (ROOT / "specs/001-common-contract/contracts/page-and-demo.md").exists()
