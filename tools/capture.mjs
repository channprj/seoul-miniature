// 자동 투어를 결정론적으로 프레임 단위 캡처해 mp4 로 만든다(로컬 녹화용). 개발 서버가 떠 있어야 한다.
//   node tools/capture.mjs <out.mp4> [width=1280] [height=720] [fps=30] [seconds=투어 전체]
// 시스템 Chrome 과 ffmpeg 가 필요하다. 프레임마다 __iso.step(1/fps) 로 시뮬레이션을 진행하므로 실제 성능과 무관하다.
import puppeteer from 'puppeteer-core';
import { spawn } from 'node:child_process';
const [out, w = '1280', h = '720', fps = '30', secs = ''] = process.argv.slice(2);
if (!out) { console.error('usage: node tools/capture.mjs <out.mp4> [w] [h] [fps] [seconds]'); process.exit(64); }
const browser = await puppeteer.launch({
  executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: 'new', args: ['--use-angle=metal', '--enable-webgl', '--ignore-gpu-blocklist', '--hide-scrollbars'],
});
const page = await browser.newPage();
await page.setViewport({ width: Number(w), height: Number(h), deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.error('[pageerror]', e.message));
await page.goto(`http://127.0.0.1:${process.env.PORT || 5173}/?${process.env.QUERY || ''}`, { waitUntil: 'load' });
await page.waitForFunction('window.__iso', { timeout: 30000 });
const total = await page.evaluate(() => { __iso.manual(true); __iso.startTour(); return __iso.tourLength; });
const n = Math.round((Number(secs) || total) * Number(fps));
const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', fps, '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '16', '-preset', 'slow', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
for (let i = 0; i < n; i++) {
  await page.evaluate((dt) => __iso.step(dt), 1 / Number(fps));
  const buf = await page.screenshot({ type: 'png' });
  if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
  if (i % 60 === 0) console.log(`frame ${i}/${n}`);
}
ff.stdin.end();
await new Promise((r) => ff.on('close', r));
await browser.close();
console.log('wrote', out);
