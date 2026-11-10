// 시스템 Chrome(헤드리스)으로 앱 화면을 찍는다. 개발 서버가 떠 있어야 한다.
//   node tools/shot.mjs <out.png> [query] [js-to-eval] [width] [height] [settleSeconds]
import puppeteer from 'puppeteer-core';
const [out, query = '', js = '', w = '1440', h = '900', settle = '2'] = process.argv.slice(2);
const browser = await puppeteer.launch({
  executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: 'new', args: ['--use-angle=metal', '--enable-webgl', '--ignore-gpu-blocklist', '--hide-scrollbars'],
});
const page = await browser.newPage();
await page.setViewport({ width: Number(w), height: Number(h), deviceScaleFactor: 1 });
const logs = [];
page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`));
await page.goto(`http://127.0.0.1:${process.env.PORT || 5173}/?${query}`, { waitUntil: 'load' });
await page.waitForFunction('window.__iso || document.querySelector("#loading p").textContent.includes("못")', { timeout: 30000 });
if (js) { const r = await page.evaluate(js); if (r !== undefined) console.log('eval →', JSON.stringify(r)); }
await new Promise((r) => setTimeout(r, Number(settle) * 1000));
await page.screenshot({ path: out });
if (logs.length) console.log(logs.join('\n'));
await browser.close();
