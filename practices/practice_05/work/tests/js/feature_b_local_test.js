const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  const filePath = path.resolve(__dirname, '../../fourier/index.html');
  if (!fs.existsSync(filePath)) {
    console.error('FAIL: fourier/index.html not found at', filePath);
    process.exit(1);
  }

  const url = 'file://' + filePath;
  const browser = await chromium.launch({ headless: true });
  const page = await browser.new_page?.() || await browser.newPage();
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded' });

    const slider = page.locator('input[data-testid="fourier-slider"]');
    const label = page.locator('span[data-testid="fourier-N-label"]');
    const plot = page.locator('path[data-testid="fourier-plot"]');

    if ((await slider.count()) !== 1) throw new Error('Slider not found');
    if ((await label.count()) !== 1) throw new Error('N label not found');
    if ((await plot.count()) !== 1) throw new Error('Plot path not found');

    // Give inline script time to render
    await page.waitForTimeout(50);

    const initVal = await slider.inputValue();
    const initLabel = await label.innerText();
    if (!initLabel.trim().endsWith(`= ${initVal}`)) {
      throw new Error(`Label not synced with slider: val=${initVal}, label='${initLabel}'`);
    }

    const d0 = await plot.getAttribute('d');
    if (!d0 || d0.length < 20) throw new Error('Initial path data too short');

    // Change slider
    const newVal = String(Math.min(15, Number(initVal) + 5));
    await slider.fill(newVal);
    await slider.dispatchEvent('input');
    await page.waitForTimeout(20);

    const updLabel = await label.innerText();
    const d1 = await plot.getAttribute('d');
    if (!updLabel.trim().endsWith(`= ${newVal}`)) throw new Error('Label did not update after change');
    if (d0 === d1) throw new Error('Path did not change after slider update');

    console.log('PASS: Local Feature B test passed for file://fourier/index.html');
    await browser.close();
    process.exit(0);
  } catch (err) {
    console.error('FAIL:', err.message);
    await page.screenshot({ path: '/tmp/feature_b_local_fail.png', fullPage: true }).catch(() => {});
    await browser.close();
    process.exit(1);
  }
})();
