// 여의도 지도 검사(node --test). 자산은 assets/yeouido/(정식), 없으면 개발용 임시 세트 assets/_yd_interim/. 둘 다 없으면 건너뛴다(공개 배치에는 정식만 있다).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import zlib from 'node:zlib';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { MAPS, isPublic, publicMaps, mapIdFrom, mapUrl, DEFAULT_MAP, resolveView, resolveBox, resolveShots } from '../src/maps.js';
import { sceneFromMap } from '../src/mapscene.js';
import { makeProjection, cumLengths, pointAt } from '../src/geom.js';
import { makeTour } from '../src/tour.js';
import { createSimpleTraffic } from '../src/sim/simple-traffic.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const A = path.resolve(here, '../assets/');
const M = MAPS.yeouido;
const dir = [M.dir, M.devDir].map((d) => path.join(A, d)).find((d) => fs.existsSync(path.join(d, M.map)));
const skip = dir ? false : '여의도 자산이 없음';

// 8bit 비인터레이스 PNG(회색조·RGB·RGBA). people.test.js 의 것과 같다.
function readPng(file) {
  const d = fs.readFileSync(file);
  let i = 8, w = 0, h = 0, ch = 1; const idat = [];
  while (i < d.length) {
    const len = d.readUInt32BE(i), type = d.toString('latin1', i + 4, i + 8), body = d.subarray(i + 8, i + 8 + len);
    if (type === 'IHDR') { w = body.readUInt32BE(0); h = body.readUInt32BE(4); ch = { 0: 1, 2: 3, 6: 4 }[body[9]]; assert.equal(body[8], 8); }
    if (type === 'IDAT') idat.push(body);
    i += 12 + len;
  }
  const raw = zlib.inflateSync(Buffer.concat(idat)), row = w * ch;
  const out = new Uint8Array(row * h);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (row + 1)], src = raw.subarray(y * (row + 1) + 1, (y + 1) * (row + 1)), o = y * row;
    for (let x = 0; x < row; x++) {
      const a = x >= ch ? out[o + x - ch] : 0, b = y > 0 ? out[o - row + x] : 0, c = x >= ch && y > 0 ? out[o - row + x - ch] : 0;
      let v = src[x];
      if (f === 1) v += a; else if (f === 2) v += b; else if (f === 3) v += (a + b) >> 1;
      else if (f === 4) { const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c); v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c; }
      out[o + x] = v & 255;
    }
  }
  return { w, h, ch, data: out };
}
const size = (file) => { const d = fs.readFileSync(file); return [d.readUInt32BE(16), d.readUInt32BE(20)]; };

let L = null;
const load = () => {
  if (L) return L;
  const scene = sceneFromMap(JSON.parse(fs.readFileSync(path.join(dir, M.map), 'utf8')));
  const proj = makeProjection(scene.camera, scene.occlusion);
  const cls = readPng(path.join(dir, 'classes.png')), dep = readPng(path.join(dir, 'depth_rg8.png'));
  const groundAt = (y) => -((proj.H / 2 - y) * proj.m + proj.cy) * proj.ey[2] / proj.vd[2] - proj.camDotVd;
  const heightAt = (x, y) => { const o = (y * dep.w + x) * dep.ch; return (groundAt(y + 0.5) - proj.decodeDepth(dep.data[o], dep.data[o + 1])) * -proj.vd[2]; };
  const clsAt = (x, y) => cls.data[y * cls.w + x];
  return (L = { scene, proj, cls, dep, heightAt, clsAt });
};

test('지도 고르기: ?map= 과 전환 주소', () => {
  assert.equal(mapIdFrom(''), DEFAULT_MAP);
  // 2026-11-12 여의도 공개: dev 없이도 공개 사이트에서 열린다.
  assert.equal(isPublic('yeouido'), true); assert.deepEqual(publicMaps().map((m) => m.id), ['gyeongbok', 'yeouido']);
  assert.equal(mapIdFrom('?map=yeouido&tod=3', false), 'yeouido');
  assert.equal(mapIdFrom('?map=yeouido', true), 'yeouido');
  assert.equal(mapIdFrom('?map=yeouido&dev=1&tod=3', true), 'yeouido');
  assert.equal(mapIdFrom('?map=__proto__'), DEFAULT_MAP);
  assert.equal(mapIdFrom('?map=nowhere'), DEFAULT_MAP);
  assert.equal(mapUrl('yeouido', 'https://x.test/p/?res=1&tod=9#850,1225,300&s=2'), 'https://x.test/p/?res=1&map=yeouido');   // 공개 지도라 dev 를 붙이지 않는다
  assert.equal(mapUrl('gyeongbok', 'https://x.test/p/?map=yeouido&dev=1#1,2,3'), 'https://x.test/p/');
  // 여의도에서는 경복궁 전용 기능이 꺼져 있다
  assert.equal(M.palace, null); assert.deepEqual(M.uplights, []);
  assert.equal(M.people, false); assert.equal(M.birds, false); assert.equal(M.finds, false);
  for (const m of Object.values(MAPS)) assert.ok(m.places.length >= 2 && m.shots.length >= 2, m.id);
});

test('여의도 자산: 파일이 있고 크기가 지도와 맞는다', { skip }, () => {
  const { proj, cls, dep } = load();
  assert.deepEqual([proj.W, proj.H], [2752, 1696]);
  assert.deepEqual([cls.w, cls.h], [2752, 1696]);
  assert.deepEqual([dep.w, dep.h], [2752, 1696]);
  assert.deepEqual(size(path.join(dir, 'bg_1x.png')), [2752, 1696]);
  assert.deepEqual(size(path.join(dir, 'bg.png')), [5504, 3392]);
  const man = JSON.parse(fs.readFileSync(path.join(dir, 'tiles/manifest.json'), 'utf8'));
  assert.deepEqual(man.map, [2752, 1696]);
  assert.deepEqual(size(path.join(dir, 'tiles', man.base)), [2752, 1696]);
  for (const [z, lv] of Object.entries(man.levels)) {
    assert.deepEqual(lv.size, [2752 * z, 1696 * z]);
    const solid = new Set((lv.solid || []).map(([x, y]) => `${x}_${y}`));
    let n = 0;
    for (let ty = 0; ty < lv.grid[1]; ty++) for (let tx = 0; tx < lv.grid[0]; tx++) if (!solid.has(`${tx}_${ty}`)) { assert.ok(fs.existsSync(path.join(dir, 'tiles', `z${z}_${tx}_${ty}.${lv.format || 'png'}`)), `z${z}_${tx}_${ty}`); n++; }
    assert.ok(n > 0);
  }
});

test('여의도 클래스 맵: 값이 0–11 안이고 물·도로·건물·수목이 다 있다', { skip }, () => {
  const { cls } = load();
  const n = new Array(256).fill(0);
  for (let i = 0; i < cls.data.length; i++) n[cls.data[i]]++;
  for (let k = 12; k < 256; k++) assert.equal(n[k], 0, `클래스 ${k}`);
  const tot = cls.data.length;
  assert.ok(n[4] / tot > 0.15, '한강(수면)이 15 % 이상');
  for (const k of [2, 6, 7, 10]) assert.ok(n[k] / tot > 0.02, `클래스 ${k} 가 2 % 이상`);
  assert.equal(n[5] + n[8] + n[9], 0, '궁궐 클래스(5·8·9)는 여의도에 없다(궁 조명·수면 반사가 켜지지 않는다)');
});

test('여의도 깊이 디코드: 지면은 0 m 근처, 가장 높은 곳은 고층 타워 높이', { skip }, () => {
  const { proj, heightAt, clsAt, scene } = load();
  assert.ok(scene.occlusion.D0_m > 0 && scene.occlusion.step_m > 0);
  // 16비트 안: 지도 네 귀퉁이 지면과 330 m 지붕이 0..65534 에 든다
  const code = (d) => (d - proj.D0) / proj.dstep;
  const g = (y) => -((proj.H / 2 - y) * proj.m + proj.cy) * proj.ey[2] / proj.vd[2] - proj.camDotVd;
  assert.ok(code(g(0)) < 65534 && code(g(proj.H) - 330 / -proj.vd[2]) > 0);
  const road = [], water = [];
  let top = -1e9;
  for (let y = 4; y < proj.H; y += 7) for (let x = 3; x < proj.W; x += 7) {
    const h = heightAt(x, y), c = clsAt(x, y);
    if (h > top) top = h;
    if (c === 2) road.push(h); else if (c === 4) water.push(h);
  }
  const med = (a) => a.sort((p, q) => p - q)[a.length >> 1];
  assert.ok(Math.abs(med(water)) < 3.5, `수면 높이 중앙값 ${med(water).toFixed(2)} m`);
  assert.ok(med(road) > -1 && med(road) < 3, `도로 높이 중앙값 ${med(road).toFixed(2)} m`);
  assert.ok(top > 200 && top < 400, `가장 높은 곳 ${top.toFixed(0)} m (파크원 약 320–330 m)`);
});

test('여의도 랜드마크 앵커: 지도 안에 있고, 건물 앵커는 건물 위에 놓인다', { skip }, () => {
  const { scene, proj, clsAt, heightAt } = load();
  for (const p of M.places) if (p.key) assert.ok(scene.anchors[p.key], `바로가기 ${p.name} 의 앵커 ${p.key}`);
  const BUILDINGS = ['63', 'parc1', 'ifc3', 'assembly'].filter((k) => scene.anchors[k]);
  assert.ok(BUILDINGS.length >= 3);
  for (const [k, a] of Object.entries(scene.anchors)) {
    const x = Math.round(a[0]), y = Math.round(a[1]);
    if (k === '63' || k === 'assembly' || k === 'parc1' || k === 'park' || k === 'hangang') assert.ok(x >= 0 && y >= 0 && x < proj.W && y < proj.H, `${k} 가 지도 안`);
  }
  for (const k of BUILDINGS) {
    const [x, y] = scene.anchors[k].map(Math.round);
    // 앵커 둘레 5×5 칸에 건물(지붕 6·벽 7)이 있고 땅보다 높다
    let hit = 0, hmax = 0;
    for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) {
      const xx = Math.min(proj.W - 1, Math.max(0, x + dx)), yy = Math.min(proj.H - 1, Math.max(0, y + dy));
      const c = clsAt(xx, yy);
      if (c === 6 || c === 7) { hit++; hmax = Math.max(hmax, heightAt(xx, yy)); }
    }
    assert.ok(hit >= 13, `${k} 앵커(${x},${y}) 둘레의 건물 칸 ${hit}/25`);
    assert.ok(hmax > 8, `${k} 앵커 자리 높이 ${hmax.toFixed(1)} m`);
  }
});

test('여의도 경로: 차로와 보행로가 건물 안을 지나지 않는다', { skip }, () => {
  const { scene, proj, heightAt, clsAt } = load();
  assert.ok(scene.lanes.length > 50 && scene.walkers.length > 50);
  const S = [0, 0, 0], P = [0, 0, 0];
  const scan = (list, step, zmax) => {
    let n = 0, inB = 0, hid = 0;
    for (const l of list) {
      const cum = cumLengths(l.pts), Lm = cum[cum.length - 1];
      for (let d = 0; d <= Lm; d += step) {
        pointAt(l.pts, cum, d, P);
        if (P[2] > zmax) continue;   // 교량 위는 따로 본다
        proj.project(P[0], P[1], P[2], S);
        const x = Math.round(S[0]), y = Math.round(S[1]);
        if (x < 2 || y < 2 || x >= proj.W - 2 || y >= proj.H - 2) continue;
        n++;
        // 건물 안 = 그 자리의 지면이 건물 바닥: 화면에서 그 칸이 건물이면서, 깊이로 잰 높이가 낮다(앞 건물에 가린 것이 아니라 그 건물의 밑동)
        const c = clsAt(x, y), h = heightAt(x, y);
        if ((c === 6 || c === 7) && h < 2.5) inB++;
        if (h > 6) hid++;   // 앞 건물·교량·나무에 가려 안 보이는 자리(가림은 정상)
      }
    }
    return { n, inB: inB / n, hid: hid / n };
  };
  const car = scan(scene.lanes, 8, 1.5), seen = new Set(), paths = [];
  for (const w of scene.walkers) if (!seen.has(w.pts)) { seen.add(w.pts); paths.push(w); }
  const walk = scan(paths, 5, 1.5);
  assert.ok(car.n > 2000 && walk.n > 500);
  assert.ok(car.inB < 0.02, `건물 밑동을 지나는 차로 점 ${(car.inB * 100).toFixed(2)} %`);
  assert.ok(walk.inB < 0.03, `건물 밑동을 지나는 보행로 점 ${(walk.inB * 100).toFixed(2)} %`);
  // 교량 위 차로: 상판 높이(z)로 투영한 자리가 교량·도로 칸이고, 깊이 맵의 그 자리 높이가 경로 z 와 비슷하다(차가 상판 위에 그려지고 가려지지 않는다)
  let nb = 0, ok = 0;
  for (const l of scene.lanes) {
    const cum = cumLengths(l.pts), Lm = cum[cum.length - 1];
    for (let d = 0; d <= Lm; d += 10) {
      pointAt(l.pts, cum, d, P);
      if (P[2] < 6) continue;
      proj.project(P[0], P[1], P[2], S);
      const x = Math.round(S[0]), y = Math.round(S[1]);
      if (x < 2 || y < 2 || x >= proj.W - 2 || y >= proj.H - 2) continue;
      nb++;
      if (Math.abs(heightAt(x, y) - P[2]) < 3.5) ok++;
    }
  }
  assert.ok(nb > 100, `교량 위 차로 점 ${nb}`);
  assert.ok(ok / nb > 0.85, `교량 상판 높이와 맞는 점 ${(ok / nb * 100).toFixed(1)} %`);
});

test('여의도 단순 교통: 차가 차로 위에 머물고 멈춰 서지 않는다', { skip }, () => {
  const { scene } = load();
  const a = createSimpleTraffic(scene, { seed: 7, targetCount: 300 }), b = createSimpleTraffic(scene, { seed: 7, targetCount: 300 });
  assert.ok(a.vehicles.length > 200 && a.vehicles.length < 420);
  const n0 = a.vehicles.length;
  for (let i = 0; i < 30 * 60; i++) { a.step(1 / 30); b.step(1 / 30); }
  assert.equal(a.vehicles.length, n0);
  let moving = 0;
  a.vehicles.forEach((v, i) => {
    assert.ok(Number.isFinite(v.x + v.y + v.z + v.th), '좌표가 유한');
    assert.ok(v.s >= 0 && v.s <= v.lane.L + 1e-6, '차로 길이 안');
    assert.ok(scene.vehicle_specs[v.kind]);
    assert.equal(v.x, b.vehicles[i].x); assert.equal(v.y, b.vehicles[i].y);   // 같은 시드면 같은 결과
    if (v.v > 2) moving++;
  });
  assert.ok(moving / n0 > 0.7, `달리는 차 ${(moving / n0 * 100).toFixed(0)} %`);
  // 같은 차로의 앞뒤 차가 겹치지 않는다
  let overlap = 0, pairs = 0;
  for (const l of a.lanes) { const c = [...l.cars].sort((p, q) => p.s - q.s); for (let i = 1; i < c.length; i++) { pairs++; if (c[i].s - c[i - 1].s < (c[i].len + c[i - 1].len) / 2 - 0.5) overlap++; } }
  assert.ok(overlap / Math.max(1, pairs) < 0.02, `겹친 앞뒤 쌍 ${overlap}/${pairs}`);
});

test('여의도 자리는 좌표가 아니라 랜드마크 이름으로 적는다: 설정·영상 대본에 지도 px 가 없고, 쓴 이름이 모두 장면 데이터에 있다', { skip }, () => {
  const { scene, proj } = load();
  const size = [proj.W, proj.H];
  // 푸는 규칙
  assert.deepEqual(resolveView([1, 2, 3], {}, size), [1, 2, 3]);
  assert.deepEqual(resolveView({ at: 'center', vh: 100 }, {}, [200, 100]), [100, 50, 100]);
  assert.deepEqual(resolveView({ at: ['a', 'b'], off: [1, -1], vh: 9 }, { a: [0, 0], b: [10, 20] }, size), [6, 9, 9]);
  assert.deepEqual(resolveBox({ at: 'a', w: 10, h: 4 }, { a: [50, 50] }, size), [45, 48, 55, 52]);
  const names = new Set();
  const spec = (v, what) => {
    if (v === null || v === undefined) return;
    assert.ok(!Array.isArray(v) && typeof v === 'object', `${what}: 지도 px 를 적지 않는다`);
    assert.ok(v.off === undefined, `${what}: off(지도 px 만큼 옮김)는 방위가 바뀌면 틀어진다`);
    for (const k of Array.isArray(v.at) ? v.at : [v.at]) if (k !== 'center') names.add(k);
  };
  for (const p of M.places) { assert.ok(p.x === undefined && p.y === undefined, `바로가기 ${p.name}`); spec({ at: p.key || p.at }, `바로가기 ${p.name}`); }
  for (const s of M.shots) { spec(s.a, `둘러보기 ${s.caption}`); spec(s.b, `둘러보기 ${s.caption}`); assert.ok(s.a && s.b); }
  spec(M.firstView.box, '첫 화면');
  const clipF = path.resolve(here, '../tools/clip.yeouido.json');   // 영상 대본은 작업 레포에만 있다(공개본에는 없음)
  if (fs.existsSync(clipF)) {
    const clip = JSON.parse(fs.readFileSync(clipF, 'utf8'));
    assert.ok(clip.shots[0].a, '영상 첫 샷은 시작 자리가 있어야 한다');
    for (const s of clip.shots) { spec(s.a, `영상 ${s.id}`); spec(s.b, `영상 ${s.id}`); }
  }
  for (const k of names) assert.ok(scene.anchors[k], `랜드마크 '${k}' 가 map.json 에 없다`);
  // 푼 자리는 지도 안
  for (const s of resolveShots(M.shots, scene.anchors, size)) for (const v of [s.a, s.b]) assert.ok(v[0] >= 0 && v[0] <= proj.W && v[1] >= 0 && v[1] <= proj.H && v[2] > 50, `${s.caption} ${v}`);
  assert.ok(makeTour(resolveShots(M.shots, scene.anchors, size)).total > 30);
});
