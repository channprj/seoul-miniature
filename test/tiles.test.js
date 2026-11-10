// 배경 타일 피라미드(단계 고르기·캐시)와 깊은 단계 스프라이트 아틀라스 검사 (node --test)
// WebGL 은 없으므로 gl 은 기록만 하는 가짜. 셰이더 출력은 스크린샷으로 확인한다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import zlib from 'node:zlib';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createBgTiles, TILE } from '../src/bgtiles.js';
import { buildHiSprites } from '../src/hisprites.js';
import { makeProjection } from '../src/geom.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const scene = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.resolve(here, '../assets/web-poc/scene.json.gz'))));
const proj = makeProjection(scene.camera);
const W = 2752, H = 1696;
globalThis.ImageData ||= class { constructor(w, h) { this.width = w; this.height = h; this.data = new Uint8ClampedArray(w * h * 4); } };

const fakeGl = () => {
  const up = [];
  const gl = new Proxy({ MAX_TEXTURE_SIZE: 1, getParameter: () => 8192, createTexture: () => ({}), texSubImage2D: (...a) => up.push(a), up }, {
    get: (t, k) => (k in t ? t[k] : typeof k === 'string' && /^[A-Z_0-9]+$/.test(k) ? 0 : () => {}),
  });
  return gl;
};
const manifest = (solid = []) => ({
  tile: TILE, map: [W, H], base: 'z1.png', colors: [[10, 20, 30]], zs: [2, 4, 8],
  levels: Object.fromEntries([2, 4, 8].map((z) => [z, { grid: [Math.ceil(W * z / TILE), Math.ceil(H * z / TILE)], format: 'png', solid: z === 8 ? solid : [] }])),
});
const flush = () => new Promise((r) => setTimeout(r, 0));
const bmp = () => ({ close() {} });

test('목표 단계의 보이는 타일이 다 올라오기 전에는 거친 단계로 그린다(섞지 않음)', async () => {
  const loads = [];
  const T = createBgTiles(fakeGl(), W, H, manifest(), { phone: true, load: (z, x, y) => { loads.push([z, x, y]); return Promise.resolve(bmp()); } });
  // 지도 px 1000..1050 × 900..1000 (z8 에서 400×800 텍셀 → 2~3 × 4 칸)
  const r = [1000, 900, 1050, 1000];
  assert.equal(T.plan(8, ...r), 1);
  // 첫 요청은 거친 단계(z2 → z4)의 보이는 칸부터
  const zl = loads.map((l) => l[0]);
  assert.equal(zl[0], 2);
  assert.ok(zl.includes(4) && (!zl.includes(8) || zl.indexOf(4) < zl.indexOf(8)));
  let F = 1;
  for (let i = 0; i < 60 && F !== 8; i++) { await flush(); F = T.plan(8, ...r); }
  assert.equal(F, 8);
  const st = T.stats();
  assert.ok(st.z4.up > 0 && st.z8.up > 0);
  // 둘레까지 다 받은 뒤 같은 자리에 머물면 더 받지 않는다(교체 반복 없음)
  for (let i = 0; i < 40; i++) { await flush(); T.plan(8, ...r); }
  const n = loads.length;
  for (let i = 0; i < 20; i++) { await flush(); T.plan(8, ...r); }
  assert.equal(loads.length, n);
});

test('단색 타일은 받지 않고 바로 있는 것으로 친다', async () => {
  const loads = [];
  // z8 에서 (0,0)..(3,3) 칸 전부 단색
  const solid = [];
  for (let y = 0; y < 4; y++) for (let x = 0; x < 4; x++) solid.push([x, y, 0]);
  const T = createBgTiles(fakeGl(), W, H, manifest(solid), { load: (z, x, y) => { loads.push([z, x, y]); return Promise.resolve(bmp()); } });
  // 지도 px 0..100 → z8 0..800 텍셀 → 칸 0..3
  for (let i = 0; i < 20; i++) { T.plan(8, 0, 0, 100, 100); await flush(); }
  assert.equal(T.plan(8, 0, 0, 100, 100), 8);
  assert.equal(loads.filter(([z, x, y]) => z === 8 && x <= 3 && y <= 3).length, 0);
});

test('타일이 배포되지 않은 단계(404)는 꺼지고 바탕으로 그린다', async () => {
  const T = createBgTiles(fakeGl(), W, H, manifest(), { load: () => Promise.resolve(null) });
  for (let i = 0; i < 10; i++) { T.plan(4, 1000, 900, 1100, 1000); await flush(); }
  assert.equal(T.plan(4, 1000, 900, 1100, 1000), 1);
  assert.equal(T.has(4), false);
});

test('빠르게 지나가도 아틀라스 칸 수를 넘지 않고, 지금 쓰는 칸은 내보내지 않는다', async () => {
  const T = createBgTiles(fakeGl(), W, H, manifest(), { phone: true, load: () => Promise.resolve(bmp()) });
  // 휴대폰 화면 하나(z8, 지도 약 110×225 px)를 오른쪽으로 40 px 씩 옮긴다
  for (let x = 400; x < 2000; x += 40) {
    for (let k = 0; k < 3; k++) { T.plan(8, x, 800, x + 110, 1025); await flush(); }
    const st = T.stats();
    assert.ok(st.z4.up + st.z8.up <= T.slots, `칸 초과 ${st.z4.up + st.z8.up}`);
  }
  // 멈추면 결국 그 단계로 그린다
  let F = 1;
  for (let i = 0; i < 40 && F !== 8; i++) { await flush(); F = T.plan(8, 1960, 800, 2070, 1025); }
  assert.equal(F, 8);
});

test('깊은 단계 스프라이트 아틀라스: 칸이 아틀라스 안, 차·사람·새가 다 그려짐', () => {
  for (const SS of [4, 8]) {
    const a = buildHiSprites(scene, proj, SS);
    const { width: AW, height: AH, data } = a.img;
    assert.ok(AW <= 2048 && AH <= 4096, `${SS}: ${AW}×${AH}`);
    assert.ok(a.colors.length <= 32);
    const filled = (x, y, w, h) => { let n = 0; for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) if (data[((y + j) * AW + x + i) * 4 + 3]) n++; return n; };
    for (const kind of Object.keys(scene.vehicle_specs)) {
      for (const f of a.vehFrames[kind]) {
        const w = Math.round(f.w * SS), h = Math.round(f.h * SS);
        assert.ok(f.src[0] + w <= AW && f.src[1] + h <= AH);
        assert.ok(filled(f.src[0], f.src[1], w, h) > SS * SS * 4, `${kind} 비어 있음`);
      }
    }
    for (const cells of a.people) for (const [x, y] of cells) assert.ok(filled(x, y, 2 * SS, 4.5 * SS) > SS * SS * 2);
    for (const f of [...a.birds.pigeon, ...a.birds.egret, ...a.birds.magpie, ...a.birds.sit]) assert.ok(filled(f.src[0], f.src[1], f.w * SS, f.h * SS) > 0);
  }
});

test('타일 manifest(있으면): 단계 크기·격자·파일 수가 맞다', () => {
  const dir = path.resolve(here, '../assets/redraw/tiles');
  const mf = path.join(dir, 'manifest.json');
  if (!fs.existsSync(mf)) return;
  const m = JSON.parse(fs.readFileSync(mf, 'utf8'));
  const names = new Set(fs.readdirSync(dir));
  assert.ok(names.has(m.base));
  for (const [z, lv] of Object.entries(m.levels)) {
    assert.deepEqual(lv.size, [m.map[0] * z, m.map[1] * z]);
    assert.deepEqual(lv.grid, [Math.ceil(lv.size[0] / m.tile), Math.ceil(lv.size[1] / m.tile)]);
    const solid = new Set(lv.solid.map(([x, y]) => `${x},${y}`));
    let files = 0;
    for (let y = 0; y < lv.grid[1]; y++) for (let x = 0; x < lv.grid[0]; x++) {
      const has = names.has(`z${z}_${x}_${y}.${lv.format}`);
      assert.ok(has !== solid.has(`${x},${y}`), `z${z} ${x},${y}`);
      files += has;
    }
    assert.equal(files, lv.files);
  }
});
