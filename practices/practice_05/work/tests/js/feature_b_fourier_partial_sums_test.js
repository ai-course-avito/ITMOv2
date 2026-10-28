const { chromium } = require('playwright');

(async () => {
  const baseUrl = process.env.BASE_URL || 'http://localhost:1254';
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  try {
    const res = await page.goto(`${baseUrl}/fourier/`, { waitUntil: 'networkidle' });
    if (!res || res.status() >= 400) {
      throw new Error(`Page did not load correctly, status=${res ? res.status() : 'n/a'}`);
    }

    // Elements presence
    const slider = page.locator('input[data-testid="fourier-slider"]');
    const label = page.locator('span[data-testid="fourier-N-label"]');
    const plot = page.locator('path[data-testid="fourier-plot"]');

    if ((await slider.count()) !== 1) throw new Error('Slider not found');
    if ((await label.count()) !== 1) throw new Error('N label not found');
    if ((await plot.count()) !== 1) throw new Error('Plot path not found');

    // Initial sync between slider and label
    const initVal = await slider.inputValue();
    const initLabel = await label.innerText();
    if (!initLabel.trim().endsWith(`= ${initVal}`)) {
      throw new Error(`Label not synced with slider: val=${initVal}, label='${initLabel}'`);
    }

    // Capture initial path d
    const d0 = await plot.getAttribute('d');
    if (!d0 || d0.length < 20) {
      throw new Error('Initial path data is missing or too short');
    }

    // Interact: change slider value
    const newVal = String(Math.min(15, Number(initVal) + 5));
    await slider.fill(newVal);
    // trigger change/input events explicitly
    await slider.dispatchEvent('input');
    await page.waitForTimeout(50);

    // Verify label updated
    const updLabel = await label.innerText();
    if (!updLabel.trim().endsWith(`= ${newVal}`)) {
      throw new Error(`Label did not update to new value: expected ${newVal}, got '${updLabel}'`);
    }

    // Verify path updated
    const d1 = await plot.getAttribute('d');
    if (d0 === d1) {
      throw new Error('Plot path d attribute did not change after slider update');
    }

    console.log('PASS: Feature B checks passed on /fourier');
    await browser.close();
    process.exit(0);
  } catch (err) {
    console.error('FAIL:', err.message);
    await page.screenshot({ path: '/tmp/feature_b_fail.png', fullPage: true }).catch(() => {});
    await browser.close();
    process.exit(1);
  }
})();
