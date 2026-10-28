import os

import pytest
from playwright.sync_api import sync_playwright


def test_mathjax_on_fourier_page():
    base_url = os.environ.get("TEST_BASE_URL")
    if not base_url:
        pytest.skip("set TEST_BASE_URL to run the browser smoke test")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        response = page.goto(f"{base_url}/fourier/", wait_until="networkidle")

        # Smoke: page should be reachable
        assert response is not None and response.status == 200, "Page did not load correctly"

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
