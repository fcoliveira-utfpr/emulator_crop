// Figure of the web application (monitoring tab, Londrina, light theme) for the paper.
// Needs puppeteer-core, Google Chrome and the built site served by `npm run preview -- --port 4173` (web/).
// node analises/fig_app.mjs analises/figures/fig_app.png
import puppeteer from 'puppeteer-core';
const out = process.argv[2];
const browser = await puppeteer.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: 'new', args: ['--no-sandbox'] });
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 2 });
await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }]);
await page.goto('http://localhost:4173/?lang=en', { waitUntil: 'networkidle0' });
await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'light'));
await page.select('#preset', '-23.19,-51.18');
await page.waitForFunction(() => /ok|error/.test(document.getElementById('status').className), { timeout: 180000 });
await page.evaluate(() => [...document.querySelectorAll('.tab')][1].click());
await new Promise((r) => setTimeout(r, 400));
await page.waitForFunction(() => !document.getElementById('panel').classList.contains('busy'), { timeout: 120000 });
await new Promise((r) => setTimeout(r, 800));
const panel = await page.$('#panel');
const box = await panel.boundingBox();
// header, tiles, the yield chart and the two rows of figures below it
const cards = await page.$$eval('#panel > *', (els) => els.map((e) => { const r = e.getBoundingClientRect(); return [e.tagName, e.className, r.top + window.scrollY, r.height]; }));
console.log(JSON.stringify(cards));
const end = cards.filter((c) => /grid/.test(c[1]))[1]; // second grid (weather figures)
const bottom = end ? end[2] + end[3] : box.y + 1800;
await page.screenshot({ path: out, clip: { x: box.x, y: box.y, width: box.width, height: bottom - box.y }, captureBeyondViewport: true });
await browser.close();
