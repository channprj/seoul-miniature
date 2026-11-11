// 밤 창문을 그림의 창틀에 맞추기(src/winfaces.js): 주기 추정(합성 단면), 면 나누기·면 종류(여의도 자산), 셰이더와 같은 식인지.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { BIN, AX, KIND, estimateAxis, buildFaces, classifyFaces, createWinEstimator, faceDc, zOf, rleFaceMap, unrleFaceMap, packWinFaces, unpackWinFaces, WINFACES_SCHEMA } from '../src/winfaces.js';
import zlib from 'node:zlib';
import { inflateRaw } from '../src/gunzip.js';
import { decodePng } from '../src/png.js';
import { makeProjection } from '../src/geom.js';
import { MAPS } from '../src/maps.js';

const here = path.dirname(fileURLToPath(import.meta.url));

// 합성 단면: 좌표 x(m)마다 밝기 f(x)를 BIN 칸으로
const profile = (len, f, origin = 0) => {
  const n = Math.round(len / BIN), s = new Float32Array(n), c = new Uint32Array(n);
  for (let i = 0; i < n; i++) { const x = origin + (i + 0.5) * BIN; s[i] = f(x) * 4; c[i] = 4; }
  return [s, c, origin];
};
const frac = (x) => x - Math.floor(x);

test('가는 창틀 선(커튼월): 주기·위상을 찾고 창 구간은 선 사이', () => {
  const P = 3.9, line = 1.37;   // 선이 x ≡ 1.37 (mod 3.9) 에 한 칸 폭
  const [s, c, o] = profile(240, (x) => 0.55 - (Math.abs(frac((x - line) / P) - 0.5) > 0.5 - BIN / P / 2 ? 0.08 : 0) + 0.04 * Math.sin(x / 37), 3);
  const e = estimateAxis(s, c, o, AX.v);
  assert.ok(e, '못 찾음');
  assert.ok(Math.abs(e.P - P) < 0.01, `주기 ${e.P}`);
  assert.ok(e.w > 0.85, `창 구간 ${e.w}`);
  // 창 구간 [phi, phi + w·P) 가 선을 피한다: 선 위치는 구간 밖
  const inWin = (x) => frac((x - e.phi) / e.P) < e.w;
  assert.ok(!inWin(line + 0.02) || !inWin(line + P * 3 + 0.02), '선이 창 구간 안');
  assert.ok(inWin(line + P / 2) && inWin(line + P * 7 + P / 2), '선 사이가 창 구간 밖');
});

test('굵은 선·가는 선이 번갈아 서면 창 칸은 그 사이(P/2), 9·10 px 번갈아 찍힌 선도 찾는다', () => {
  // 1.18 m 마다 세로 창틀, 한 칸 건너 짙기가 다르다(63빌딩 그림)
  const [s, c, o] = profile(60, (x) => { const k = Math.round(x / 1.18), d = Math.abs(x - k * 1.18); return 0.54 - (d < BIN / 2 ? (k % 2 ? 0.02 : 0.045) : 0); });
  const e = estimateAxis(s, c, o, AX.h);
  assert.ok(e && Math.abs(e.P - 1.18) < 0.01, `주기 ${e && e.P}`);
});

test('아파트(어두운 창 덩어리): 창 구간은 어두운 쪽, 민무늬는 못 찾음', () => {
  const P = 2.9;
  const [s, c, o] = profile(45, (x) => (frac((x - 0.6) / P) < 0.45 ? 0.3 : 0.8));
  const e = estimateAxis(s, c, o, AX.v, true);
  assert.ok(e && Math.abs(e.P - P) < 0.02, `주기 ${e && e.P}`);
  assert.ok(Math.abs(e.w - 0.45) < 0.08, `창 폭 ${e.w}`);
  assert.ok(Math.abs(frac((e.phi - 0.6) / P + 0.5) - 0.5) < 0.08, `위상 ${e.phi}`);
  const [s2, c2, o2] = profile(80, () => 0.5);
  assert.equal(estimateAxis(s2, c2, o2, AX.v), null);
  const [s3, c3, o3] = profile(5, (x) => (frac(x / P) < 0.45 ? 0.3 : 0.8));
  assert.equal(estimateAxis(s3, c3, o3, AX.v), null, '주기 2.5 개 미만');
});

test('셰이더(render.js)가 같은 식: 같은 면 네 칸 쌍선형 밑동 깊이(+1e-3), 벽 위 높이 = KZ·(dc − 지면 깊이)', () => {
  const src = fs.readFileSync(path.join(here, '../src/render.js'), 'utf8');
  assert.ok(src.includes('const float KZW = VD.z / (1.0 - VD.z * VD.z)'));
  assert.ok(/faceDcAt[\s\S]{0,600}\+ 1\.0e-3/.test(src), '가중치 +1e-3');
  assert.ok(src.includes('zc = KZW * (dcf - groundDepth(mc.y))'));
  const wl = fs.readFileSync(path.join(here, '../src/winlights.js'), 'utf8');
  assert.ok(wl.includes('vec4 gv, vec4 gh'), 'winCell 이 잰 격자를 받는다');
});

// ── 여의도 자산으로
const M = MAPS.yeouido, A = path.resolve(here, '../assets/');
const dir = [M.dir, M.devDir].map((d) => path.join(A, d)).find((d) => fs.existsSync(path.join(d, M.map)) && fs.existsSync(path.join(d, 'tiles/z1.png')));
const skip = dir ? false : '여의도 자산(타일 포함)이 없음';
let ctx = null;
async function load() {
  if (ctx) return ctx;
  const map = JSON.parse(fs.readFileSync(path.join(dir, 'map.json'), 'utf8'));
  const proj = makeProjection({ ...map.camera, m_per_px_screen: map.map_m_per_px, res: map.map_px }, { D0_m: map.depth.D0, step_m: map.depth.step });
  const png = async (p) => decodePng(new Uint8Array(fs.readFileSync(path.join(dir, p))));
  const G = buildFaces({ proj, depth: (await png('depth_rg8.png')).data, sem: (await png('classes.png')).data });
  classifyFaces(G, (await png('tiles/z1.png')).data);
  return (ctx = { map, proj, png, G });
}
const lm = (map, k) => map.landmarks[k].px.map(Math.round);

test('여의도 면 나누기: 63빌딩은 꼭대기부터 밑동까지 한 커튼월 면(아래 1/3 의 어두운 금빛 포함), 파크원·IFC 도 커튼월', { skip }, async () => {
  const { map, G } = await load();
  assert.ok(G.faces.length > 200 && G.faces.length < 65535, `면 ${G.faces.length}`);
  const [x, y] = lm(map, '63');
  // 63 앵커 근처 벽 칸 중 가장 큰 면
  const cnt = new Map();
  for (let yy = y - 120; yy < y + 120; yy++) for (let xx = x - 30; xx < x + 30; xx++) { const f = G.face[yy * G.W + xx]; if (f) cnt.set(f, (cnt.get(f) || 0) + 1); }
  const f63 = [...cnt].sort((a, b) => b[1] - a[1])[0][0], F = G.faces[f63];
  assert.equal(F.kind, KIND.office, '63빌딩 면이 커튼월이 아님');
  assert.ok(F.zhi - F.zlo > 200 && F.zlo < 5, `높이 ${F.zlo}..${F.zhi}`);
  for (const k of ['parc1', 'ifc']) {
    const [px, py] = lm(map, k);
    let off = 0, n = 0;
    for (let yy = py - 120; yy < py; yy++) for (let xx = px - 20; xx < px + 20; xx++) { const f = G.face[yy * G.W + xx]; if (f) { n++; if (G.faces[f].kind === KIND.office) off++; } }
    assert.ok(n > 300 && off / n > 0.65, `${k}: 커튼월 ${off}/${n}`);
  }
  // 아파트로 분류된 면도 있다(흰 벽)
  assert.ok(G.faces.filter((Fc) => Fc && Fc.kind === KIND.home).length > 100);
  // faceDc: 면 안에서 연속(1 px 옮겨도 높이가 1.3 m 넘게 뛰지 않는다)
  const yy = Math.round((F.y0 + F.y1) / 2);
  let xx = F.x0; while (G.face[yy * G.W + xx] !== f63) xx++;
  const z0 = zOf(G, faceDc(G, f63, xx + 2.3, yy + 0.5), yy + 0.5), z1 = zOf(G, faceDc(G, f63, xx + 2.3, yy - 0.5), yy - 0.5);
  assert.ok(z1 - z0 > 1.0 && z1 - z0 < 1.4, `1 px 위로 ${z1 - z0} m`);
});

test('여의도 63빌딩: z4 타일에서 층 주기 3.9 m(그림의 가로 창틀)를 찾는다', { skip }, async () => {
  const { map, png, G } = await load();
  const E = createWinEstimator(G, { levels: [4] });
  const [x, y] = lm(map, '63');
  for (let ty = Math.floor((y - 110) * 4 / 256); ty <= Math.floor((y + 110) * 4 / 256); ty++)
    for (let tx = Math.floor((x - 25) * 4 / 256); tx <= Math.floor((x + 40) * 4 / 256); tx++) {
      const p = `tiles/z4_${tx}_${ty}.png`;
      if (!fs.existsSync(path.join(dir, p)) || !E.covers(4, tx, ty)) continue;
      const im = await png(p); E.add(4, tx * 256, ty * 256, im.width, im.height, im.data, ty * 1000 + tx);
    }
  while (E.pending()) E.work(1e9);
  const f = G.face[(y - 10) * G.W + x], F = G.faces[f];
  assert.ok(F && F.ev, '층 주기를 못 찾음');
  assert.ok(F.ev.P > 3.5 && F.ev.P < 4.3, `층 ${F.ev.P}`);
  assert.equal(E.tab[f * 8], Math.fround(F.ev.P), '면 표에 들어감');
  assert.equal(E.tab[f * 8 + 3], KIND.office);
});

// ── 미리 계산한 면(winfaces.json)
const codec = { deflateRaw: (u8) => new Uint8Array(zlib.deflateRawSync(u8)), toB64: (u8) => Buffer.from(u8).toString('base64'), inflateRaw, fromB64: (b) => Uint8Array.from(Buffer.from(b, 'base64')) };

test('winfaces.json 포장: 면 번호 길이 부호화·표가 그대로 돌아오고, 다른 굽기(벽이 아닌 칸)·크기가 다르면 쓰지 않는다', () => {
  const W = 64, H = 40, N = W * H, face = new Uint16Array(N), sem = new Uint8Array(N * 4);
  for (let i = 0; i < N; i++) { const x = i % W, y = (i / W) | 0; if (x > 5 && x < 30 && y > 3) face[i] = 1 + (x > 17 ? 1 : 0) + (y > 30 ? 300 : 0); if (face[i]) sem[i * 4] = 7; }
  assert.deepEqual(unrleFaceMap(rleFaceMap(face), N), face);
  const tab = new Float32Array(1024 * 2 * 4);
  tab.set([3.9001, 0.4875, 0.9375, 1, 1.1785, 1.1048, 0.9375, 326], 1 * 8);
  tab.set([0, 0, 0, 2, 0, 0, 0, 12], 302 * 8);
  const faces = [null]; for (let f = 1; f <= 302; f++) faces.push({});
  const J = JSON.parse(JSON.stringify(packWinFaces({ G: { W, H, face, faces }, tab }, { ...codec, meta: { map: 't' } })));
  assert.equal(J.schema, WINFACES_SCHEMA); assert.equal(J.faces.length, 302);
  const r = unpackWinFaces(J, { W, H, sem, ...codec });
  assert.ok(typeof r === 'object', r);
  assert.deepEqual(r.face, face);
  assert.deepEqual(Array.from(r.tab.subarray(8, 16)), Array.from(tab.subarray(8, 16)));
  assert.equal(r.tab[302 * 8 + 3], 2);
  assert.equal(r.faceBytes[(10 * W + 20) * 2 + 1], 2);
  // 다른 굽기: 면 칸의 클래스가 벽이 아니다 → 이유 문자열(앱은 실행 중 계산으로)
  const sem2 = new Uint8Array(sem); for (let i = 0; i < N; i += 7) sem2[i * 4] = 1;
  assert.equal(typeof unpackWinFaces(J, { W, H, sem: sem2, ...codec }), 'string');
  assert.equal(typeof unpackWinFaces(J, { W: W + 1, H, sem, ...codec }), 'string');
  assert.equal(typeof unpackWinFaces({ ...J, schema: 'x' }, { W, H, sem, ...codec }), 'string');
});

const wfFile = dir && path.join(dir, 'winfaces.json');
test('여의도 winfaces.json(설치돼 있으면): 지금 깊이·클래스 맵과 맞고, 63빌딩 앞면 층 3.9 m·칸 1.18 m(또는 2배)', { skip: !wfFile || !fs.existsSync(wfFile) ? 'winfaces.json 없음(node app/tools/build-winfaces.mjs)' : false }, async () => {
  const J = JSON.parse(fs.readFileSync(wfFile, 'utf8'));
  const map = JSON.parse(fs.readFileSync(path.join(dir, 'map.json'), 'utf8'));
  const sem = (await decodePng(new Uint8Array(fs.readFileSync(path.join(dir, 'classes.png'))))).data;
  const [W, H] = map.map_px;
  const r = unpackWinFaces(J, { W, H, sem, ...codec });
  assert.ok(typeof r === 'object', `쓸 수 없음: ${r} — 그림을 다시 구웠으면 build-winfaces.mjs 를 다시 돌리세요`);
  assert.ok(fs.statSync(wfFile).size < 400 * 1024, `크기 ${fs.statSync(wfFile).size}`);
  const [x, y] = map.landmarks['63'].px.map(Math.round);
  const f = r.face[(y - 10) * W + x + 15], row = J.faces[f - 1];
  assert.ok(f && row, '63빌딩 앞면에 면이 없음');
  assert.equal(row[3], KIND.office);
  assert.ok(Math.abs(row[0] - 3.9) < 0.1, `층 ${row[0]}`);
  // r7 부터 랜드마크 재질이 창 칸을 2배로 그려(LANDMARK-NOTES 5차) 그림의 칸이 2.36 m 다. 그림 주기의 1·2배만 받는다
  assert.ok([1.18, 2.36].some((c) => Math.abs(row[4] - c) < 0.04), `칸 ${row[4]}`);
});
