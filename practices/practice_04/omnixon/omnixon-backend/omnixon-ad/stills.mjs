// Dump stills at given times for review: node stills.mjs <outdir> 1.0 2.5 ...
import { chromium } from '../omnixon/omnixon-frontend/node_modules/playwright/index.mjs';
import { writeFileSync, mkdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const [out, ...times] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
page.on('pageerror', e => console.error('PAGE ERROR', e.message));
page.on('console', m => m.type() === 'error' && console.error('console', m.text()));
await page.goto(pathToFileURL(new URL('./index.html', import.meta.url).pathname).href + `?render&lang=${process.env.FILM_LANG || 'en'}`);
await page.evaluate(() => window.__film.ready);
for (const t of times) {
  const data = await page.evaluate(t => { window.__film.render(+t); return document.getElementById('c').toDataURL('image/jpeg', 0.85); }, t);
  writeFileSync(`${out}/t${(+t).toFixed(2).padStart(5, '0')}.jpg`, Buffer.from(data.split(',')[1], 'base64'));
}
await browser.close();
