// Figure of the web application (monitoring tab, Londrina, light theme) for the paper.
// Needs puppeteer-core, Google Chrome (CHROME: path of the executable; default: macOS location) and the built
// site served by `npm run preview -- --port 4173` (web/).
// node analises/fig_app.mjs analises/figures/fig_app.png
// Shows the headline tiles, the expected yield with the projection until maturity, rain and temperature, and
// the yield and yield gap built along the cycle (% of the potential); the yield-gap and final-yield charts and
// the sections below are hidden so the figure fits a page. Prints the tiles, used in the text of the paper.
import puppeteer from 'puppeteer-core';
const out = process.argv[2];
const chrome = process.env.CHROME ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browser = await puppeteer.launch({ executablePath: chrome, headless: 'new', args: ['--no-sandbox'] });
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 2 });
await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }]);
await page.goto('http://localhost:4173/?lang=en', { waitUntil: 'networkidle0' });
await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'light'));
await page.select('#preset', '-23.19,-51.18');
await page.waitForFunction(() => /ok|error/.test(document.getElementById('status').className), { timeout: 240000 });
await page.evaluate(() => [...document.querySelectorAll('.tab')][1].click());
await new Promise((r) => setTimeout(r, 400));
await page.waitForFunction(() => !document.getElementById('panel').classList.contains('busy'), { timeout: 240000 });
// the projection until maturity is computed after the first drawing
await page.waitForFunction(() => { const p = document.querySelector('.proj-status'); return !p || p.textContent === '' || /unavailable/.test(p.textContent); }, { timeout: 240000 });
await new Promise((r) => setTimeout(r, 800));
console.log(await page.evaluate(() => [...document.querySelectorAll('#panel .tiles')][0].innerText.replace(/\n+/g, ' | ')));
console.log(await page.evaluate(() => document.querySelector('#panel .panel-head .lead')?.innerText ?? ''));
// keep: header, tiles, the expected-yield chart, the weather grid and the % grid
await page.evaluate(() => {
  const grids = [...document.querySelectorAll('#panel > .grid')];
  [...grids[0].children].slice(1).forEach((c) => { c.style.display = 'none'; });
  let after = grids[2]?.nextElementSibling;
  while (after) { after.style.display = 'none'; after = after.nextElementSibling; }
});
await new Promise((r) => setTimeout(r, 300));
const panel = await page.$('#panel');
const box = await panel.boundingBox();
const grids = await page.$$eval('#panel > .grid', (els) => els.map((e) => { const r = e.getBoundingClientRect(); return [r.top + window.scrollY, r.height]; }));
const last = grids[2] ?? grids.at(-1);
await page.screenshot({ path: out, clip: { x: box.x, y: box.y, width: box.width, height: last[0] + last[1] - box.y }, captureBeyondViewport: true });
await browser.close();
