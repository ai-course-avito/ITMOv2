from playwright.sync_api import sync_playwright


def test_mathjax_on_fourier_page():
    base_url = "http://localhost:8000"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{base_url}/fourier", wait_until="networkidle")

        # Smoke: page should be reachable
        assert page.status == 200 or page.url.endswith("/fourier"), "Page did not load correctly"

        # MathJax script present
        scripts = page.locator('script[src*="mathjax"]').all()
        assert len(scripts) >= 1, "Expected MathJax script tag on the page"

        # At least two rendered math containers: one inline and one block
        page.wait_for_timeout(500)  # give MathJax time if present
        mjx = page.locator('mjx-container').all()
        assert len(mjx) >= 2, "Expected at least two MathJax-rendered containers"

        # No raw TeX delimiters visible
        body_text = page.inner_text('body')
        assert "$$" not in body_text and "$" not in body_text, "Raw TeX delimiters should not be visible"

        browser.close()
