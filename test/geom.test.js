// 투영·깊이 디코드·자산 무결성 검사 (node --test)
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { makeProjection, decodeDepth, cumLengths, pointAt } from '../src/geom.js';
import { sampleTour, TOUR, PLACES } from '../src/tour.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const A = path.resolve(here, '../assets/web-poc');
const scene = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(A, 'scene.json.gz'))));
const proj = makeProjection(scene.camera);

test('자산 sha256 이 매니페스트와 같다(해시가 고정된 것만)', () => {
  const m = JSON.parse(fs.readFileSync(path.join(here, '../assets.manifest.json'), 'utf8'));
  for (const [name, sha] of Object.entries(m.files)) {
    if (!sha) continue;
    const got = crypto.createHash('sha256').update(fs.readFileSync(path.join(A, '..', name))).digest('hex');
    assert.equal(got, sha, name);
  }
});

test('투영: 화면축과 시선이 직교하고, 화면 중심점이 캔버스 중앙에 온다', () => {
  const { ex, ey, vd } = proj;
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  assert.ok(Math.abs(dot(ex, ey)) < 1e-6 && Math.abs(dot(ex, vd)) < 1e-6 && Math.abs(dot(ey, vd)) < 1e-6);
  // P·ex = cx, P·ey = cy 인 점
  const P = [ex[0] * proj.cx + ey[0] * proj.cy, ex[1] * proj.cx + ey[1] * proj.cy, ex[2] * proj.cx + ey[2] * proj.cy];
  const o = proj.project(P[0], P[1], P[2], [0, 0, 0]);
  // 축 벡터가 float32 정밀도라 1e-3 px 까지 허용
  assert.ok(Math.abs(o[0] - proj.W / 2) < 1e-3 && Math.abs(o[1] - proj.H / 2) < 1e-3, `${o}`);
});

test('투영: 1 m 는 화면에서 2 px(0.5 m/px), 위로 올라가면 화면 위쪽·카메라 쪽', () => {
  const a = proj.project(0, 0, 0, [0, 0, 0]).slice(), b = proj.project(proj.ex[0], proj.ex[1], 0, [0, 0, 0]).slice();
  assert.ok(Math.abs(b[0] - a[0] - 2) < 1e-5);
  const up = proj.project(0, 0, 10, [0, 0, 0]);
  assert.ok(up[1] < a[1] && up[2] < a[2]);
});

test('차선 점은 모두 캔버스 근처로 투영되고 지면 깊이는 문서의 렌더 범위 안이다', () => {
  const o = [0, 0, 0];
  let inside = 0, total = 0;
  for (const ln of scene.lanes) for (const p of ln.pts) {
    proj.project(p[0], p[1], p[2], o); total++;
    if (o[0] >= 0 && o[0] < proj.W && o[1] >= 0 && o[1] < proj.H) { inside++; assert.ok(o[2] > 2000 && o[2] < 3500, `depth ${o[2]}`); }
  }
  assert.ok(inside / total > 0.5);
});

test('깊이 디코드: v=R*256+G, 65535 는 지오메트리 없음', () => {
  assert.equal(decodeDepth(0, 0), 2060);
  assert.equal(decodeDepth(1, 0), 2060 + 256 * 0.02);
  assert.equal(decodeDepth(255, 255), Infinity);
  assert.ok(Math.abs(decodeDepth(255, 254) - (2060 + 65534 * 0.02)) < 1e-9);
});

test('폴리라인 보간: 끝점과 중간점', () => {
  const pts = [[0, 0, 0], [10, 0, 0], [10, 10, 2]];
  const cum = cumLengths(pts);
  assert.equal(cum[2], 20);
  assert.deepEqual(pointAt(pts, cum, 5, [0, 0, 0]), [5, 0, 0]);
  assert.deepEqual(pointAt(pts, cum, 15, [0, 0, 0]), [10, 5, 1]);
  assert.deepEqual(pointAt(pts, cum, 99, [0, 0, 0]), [10, 10, 2]);
});

test('투어·장소 좌표는 캔버스 안이고, 투어는 끝나면 null 을 준다', () => {
  for (const p of PLACES) assert.ok(p.x >= 0 && p.x <= proj.W && p.y >= 0 && p.y <= proj.H, p.name);
  for (let t = 0; t < TOUR.total; t += 0.37) {
    const s = sampleTour(t);
    assert.ok(s.x >= 0 && s.x <= proj.W && s.y >= 0 && s.y <= proj.H && s.vh > 50 && s.tod >= 0 && s.tod <= 24);
  }
  assert.equal(sampleTour(TOUR.total + 0.01), null);
});
