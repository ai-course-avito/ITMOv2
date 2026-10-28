const { chromium } = require('playwright');

(async () => {
  const baseUrl = process.env.BASE_URL || 'http://localhost:1254';
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  try {
    const res = await page.goto(`${baseUrl}/fourier/`, { waitUntil: 'domcontentloaded' });
    if (!res || res.status() >= 400) {
      throw new Error(`Page did not load correctly, status=${res ? res.status() : 'n/a'}`);
    }

    // MathJax script present
    const scriptCount = await page.locator('script[src*="mathjax"]').count();
    if (scriptCount < 1) {
      throw new Error('Expected MathJax script tag on the page');
    }

    // Wait a bit for MathJax to typeset
    await page.waitForTimeout(800);
    const mjxCount = await page.locator('mjx-container').count();
    if (mjxCount < 2) {
      throw new Error(`Expected at least two MathJax-rendered containers, got ${mjxCount}`);
    }

    const bodyText = await page.innerText('body');
    if (bodyText.includes('$$') || /(^|\s)\$(?!\d)/.test(bodyText)) {
      throw new Error('Raw TeX delimiters should not be visible');
    }

    console.log('PASS: Feature A checks passed on /fourier');
    await browser.close();
    process.exit(0);
  } catch (err) {
    console.error('FAIL:', err.message);
    await page.screenshot({ path: '/tmp/feature_a_fail.png', fullPage: true }).catch(() => {});
    await browser.close();
    process.exit(1);
  }
})();
