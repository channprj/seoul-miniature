// 새 배치·상태 검사 (node --test). 실제 classes.png 를 읽어 그림이 바뀌어도 규칙이 지켜지는지 본다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import zlib from 'node:zlib';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createBirds, planBirds, isGround, CLS } from '../src/birds.js';

const here = path.dirname(fileURLToPath(import.meta.url));

// 8bit 회색조·비인터레이스 PNG 만 푼다(classes.png 형식). 필터 0–4.
function readGrayPng(file) {
  const d = fs.readFileSync(file);
  let i = 8, w = 0, h = 0; const idat = [];
  while (i < d.length) {
    const len = d.readUInt32BE(i), type = d.toString('latin1', i + 4, i + 8), body = d.subarray(i + 8, i + 8 + len);
    if (type === 'IHDR') { w = body.readUInt32BE(0); h = body.readUInt32BE(4); assert.equal(body[8], 8); assert.equal(body[9], 0); assert.equal(body[12], 0); }
    if (type === 'IDAT') idat.push(body);
    i += 12 + len;
  }
  const raw = zlib.inflateSync(Buffer.concat(idat));
  const out = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (w + 1)], src = raw.subarray(y * (w + 1) + 1, (y + 1) * (w + 1));
    for (let x = 0; x < w; x++) {
      const a = x > 0 ? out[y * w + x - 1] : 0, b = y > 0 ? out[(y - 1) * w + x] : 0, c = x > 0 && y > 0 ? out[(y - 1) * w + x - 1] : 0;
      let v = src[x];
      if (f === 1) v += a; else if (f === 2) v += b; else if (f === 3) v += (a + b) >> 1;
      else if (f === 4) { const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c); v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c; }
      out[y * w + x] = v & 255;
    }
  }
  return { w, h, cls: out };
}

const grid = readGrayPng(path.resolve(here, '../assets/redraw/classes.png'));
const at = (x, y) => grid.cls[Math.floor(y) * grid.w + Math.floor(x)];

test('새 배치: 같은 시드면 같은 결과, 다른 시드면 다른 결과', () => {
  const a = planBirds(grid, { seed: 11 }), b = planBirds(grid, { seed: 11 }), c = planBirds(grid, { seed: 12 });
  assert.deepEqual(a, b);
  assert.notDeepEqual(a, c);
  assert.ok(a.flocks.length >= 6, `무리 ${a.flocks.length}`);
  assert.ok(a.loners.length >= 1, `외톨이 ${a.loners.length}`);
});

test('비둘기는 마당·광장에만 앉는다(물·지붕·도로·나무 위 금지, 종종걸음 범위 포함)', () => {
  const { flocks } = planBirds(grid, { seed: 11 });
  let n = 0;
  for (const f of flocks) for (const b of f.birds) {
    for (const dx of [-0.5, 0, 0.5]) for (const dy of [-0.5, 0]) {
      const c = at(b.hx + dx, b.hy + dy);
      assert.ok(isGround(c), `(${b.hx + dx}, ${b.hy + dy}) 클래스 ${c}`);
      assert.ok(![CLS.WATER, 2, 6, 7, 8, 9].includes(c));
    }
    n++;
  }
  assert.ok(n >= 30, `비둘기 ${n}`);
});

test('흐름 재현: 같은 dt 열이면 상태가 같다(__iso.step 영상 캡처용)', () => {
  const run = () => {
    const s = createBirds(grid, { seed: 11 });
    const f0 = s.flocks[0];
    for (let i = 0; i < 900; i++) {
      if (i === 30) s.scare(f0.x, f0.y, 5);
      s.step(1 / 30);
    }
    return s.snapshot();
  };
  assert.deepEqual(run(), run());
});

test('무리는 날아올랐다가 제자리로 돌아와 앉는다', () => {
  const s = createBirds(grid, { seed: 11 });
  const f = s.flocks[0];
  const P = {};
  assert.equal(s.scare(f.x, f.y, 5), 1);
  assert.equal(f.state, 'flying');
  let maxAlt = 0;
  for (let i = 0; i < 30 * 30 && f.state === 'flying'; i++) {
    s.step(1 / 30);
    for (const b of f.birds) { s.pose(f, b, P); maxAlt = Math.max(maxAlt, P.alt); }
  }
  assert.equal(f.state, 'ground');
  assert.ok(maxAlt > 8, `최고 고도 ${maxAlt}`);
  for (const b of f.birds) {
    s.pose(f, b, P);
    assert.equal(P.alt, 0); assert.equal(P.flying, false);
    assert.ok(Math.abs(P.x - b.hx) <= 0.5 && P.y === b.hy);
    assert.ok(isGround(at(P.x, P.y - 0.5)));
  }
  // 내려앉은 직후에는 다시 놀라지 않는다
  assert.equal(s.scare(f.x, f.y, 5), 0);
});

test('가만두어도 가끔 저절로 날아오른다', () => {
  const s = createBirds(grid, { seed: 11 });
  let launched = 0;
  const was = s.flocks.map((f) => f.state);
  for (let i = 0; i < 30 * 200; i++) {
    s.step(1 / 30);
    s.flocks.forEach((f, k) => { if (was[k] === 'ground' && f.state === 'flying') launched++; was[k] = f.state; });
  }
  assert.ok(launched >= s.flocks.length, `저절로 난 횟수 ${launched}`);
});

test('땅이 없는 격자에서는 새를 만들지 않는다', () => {
  const w = 64, h = 64, cls = new Uint8Array(w * h).fill(CLS.WATER);
  const s = createBirds({ w, h, cls }, { seed: 3 });
  assert.equal(s.flocks.length, 0);
});
