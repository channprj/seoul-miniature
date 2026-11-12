// 테헤란로 지도 검사(node --test). 자산(assets/teheran/)이 없으면 건너뛴다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { MAPS, isPublic, mapIdFrom, resolveShots } from '../src/maps.js';
import { sceneFromMap } from '../src/mapscene.js';
import { makeProjection } from '../src/geom.js';
import { decodePng } from '../src/png.js';
import { makeTour } from '../src/tour.js';
import { createSimpleTraffic } from '../src/sim/simple-traffic.js';
import { createPeople, addCast } from '../src/sim/people.js';

const M = MAPS.teheran;
const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../assets', M.dir);
const skip = fs.existsSync(path.join(dir, M.map)) ? false : '테헤란로 자산이 없음';
const png = async (name) => { const p = await decodePng(new Uint8Array(fs.readFileSync(path.join(dir, name)))); return { w: p.width, h: p.height, data: p.data }; };

let L = null;
const load = async () => {
  if (L) return L;
  const map = JSON.parse(fs.readFileSync(path.join(dir, M.map), 'utf8'));
  const scene = sceneFromMap(map), proj = makeProjection(scene.camera, scene.occlusion);
  const c4 = await png('classes.png'), dep = await png('depth_rg8.png');
  const cls = Uint8Array.from({ length: c4.w * c4.h }, (_, i) => c4.data[i * 4]);
  const groundAt = (y) => -((proj.H / 2 - y) * proj.m + proj.cy) * proj.ey[2] / proj.vd[2] - proj.camDotVd;
  const heightAt = (x, y) => { const o = (y * dep.w + x) * 4; return (groundAt(y + 0.5) - proj.decodeDepth(dep.data[o], dep.data[o + 1])) * -proj.vd[2]; };
  return (L = { map, scene, proj, cls, w: c4.w, h: c4.h, heightAt });
};

test('테헤란로 지도 고르기: 공개 지도이고 ?map=teheran 으로 열린다', () => {
  assert.equal(isPublic('teheran'), true);
  assert.equal(mapIdFrom('?map=teheran', false), 'teheran');
});

test('테헤란로 자산: 크기와 축척이 지도 규격과 맞고 타일이 다 있다', { skip }, async () => {
  const { map, proj, w, h } = await load();
  assert.deepEqual([proj.W, proj.H, w, h], [2752, 1696, 2752, 1696]);
  assert.equal(map.map_m_per_px, 1.25);
  const man = JSON.parse(fs.readFileSync(path.join(dir, 'tiles/manifest.json'), 'utf8'));
  for (const [z, lv] of Object.entries(man.levels)) {
    const solid = new Set((lv.solid || []).map(([x, y]) => `${x}_${y}`));
    for (let ty = 0; ty < lv.grid[1]; ty++) for (let tx = 0; tx < lv.grid[0]; tx++) if (!solid.has(`${tx}_${ty}`)) assert.ok(fs.existsSync(path.join(dir, 'tiles', `z${z}_${tx}_${ty}.${lv.format || 'png'}`)), `z${z}_${tx}_${ty}`);
  }
});

test('테헤란로 장소: 강남·역삼·선릉·삼성역, 선릉, 위워크타워가 지도 안에 있고 바로가기·둘러보기가 가리키는 이름이 다 있다', { skip }, async () => {
  const { scene, proj } = await load();
  const names = new Set(['station_강남', 'station_역삼', 'station_선릉', 'station_삼성', 'seolleung', 'tomb_seongjong', 'tomb_jungjong', 'wework', 'coex', 'trade']);
  for (const p of M.places) if ((p.key || p.at) !== 'center') names.add(p.key || p.at);
  for (const s of M.shots) for (const v of [s.a, s.b]) for (const k of [].concat(v.at)) if (k !== 'center') names.add(k);
  for (const k of [].concat(M.firstView.box.at)) names.add(k);
  for (const k of names) {
    const a = scene.anchors[k];
    assert.ok(a, `랜드마크 '${k}' 가 map.json 에 없다`);
    assert.ok(a[0] > 0 && a[0] < proj.W && a[1] > 0 && a[1] < proj.H, `${k} 가 지도 밖 ${a}`);
  }
  // 테헤란로를 따라 강남역(왼쪽 아래) → 삼성역(오른쪽 위) 순서로 놓인다
  const xs = ['강남', '역삼', '선릉', '삼성'].map((n) => scene.anchors['station_' + n]);
  for (let i = 1; i < xs.length; i++) assert.ok(xs[i][0] > xs[i - 1][0] && xs[i][1] < xs[i - 1][1], '역 순서');
  assert.ok(makeTour(resolveShots(M.shots, scene.anchors, [proj.W, proj.H])).total > 30);
});

test('테헤란로 클래스·깊이: 도로·건물·수목이 있고, 궁궐 클래스는 없고, 가장 높은 곳은 고층 타워', { skip }, async () => {
  const { cls, w, h, heightAt } = await load();
  const n = new Array(256).fill(0);
  for (let i = 0; i < cls.length; i++) n[cls[i]]++;
  for (let k = 12; k < 256; k++) assert.equal(n[k], 0, `클래스 ${k}`);
  for (const k of [2, 6, 7, 10]) assert.ok(n[k] / cls.length > 0.02, `클래스 ${k} 가 2 % 이상`);
  assert.equal(n[5] + n[8] + n[9], 0);
  let top = 0;
  for (let y = 4; y < h; y += 9) for (let x = 3; x < w; x += 9) top = Math.max(top, heightAt(x, y));
  assert.ok(top > 150 && top < 320, `가장 높은 곳 ${top.toFixed(0)} m`);
});

test('삼성역 광장: 원형 광장은 걸을 수 있는 포장 바닥이고, 강철 기둥·달걀꼴 조형탑·내리막 계단이 있다', { skip }, async () => {
  const { scene, cls, w, heightAt } = await load();
  const [ax, ay] = scene.anchors.millennium.map(Math.round);   // 원형 광장 가운데(1 px = 1.25 m). 깊이 맵은 칸의 가장 가까운 면이라 평지가 약 +0.5 m 로 읽힌다
  let plaza = 0, n = 0, pylon = 0, egg = 0, stair = 0;
  for (let dy = -40; dy <= 40; dy++) for (let dx = -40; dx <= 40; dx++) {
    const x = ax + dx, y = ay + dy, c = cls[y * w + x], hgt = heightAt(x, y), r = Math.hypot(dx, dy);
    n++;
    if (c === 11) plaza++;
    if (r < 14 && hgt > 3 && hgt < 8) pylon++;            // 기둥 4.4–6.2 m
    if (r < 32 && hgt > 12 && hgt < 22) egg++;            // 조형탑 18 m
    if (c === 11 && r < 22 && hgt < -0.5) stair++;        // 계단 바닥 −1.4 m
  }
  assert.ok(plaza / n > 0.25, `포장 광장 비율 ${(plaza / n).toFixed(2)}`);
  assert.ok(pylon > 8, `기둥 칸 ${pylon}`);
  assert.ok(egg > 8, `조형탑 칸 ${egg}`);
  assert.ok(stair > 6, `내리막 계단 칸 ${stair}`);
});

test('테헤란로 교통·사람: 차가 차로를 달리고, 사람 장면이 예외 없이 돈다', { skip }, async () => {
  const { scene, cls, w, h, proj, heightAt } = await load();
  assert.ok(scene.lanes.length > 100 && scene.walkers.length > 50);
  const t = createSimpleTraffic(scene, { seed: 7, targetCount: 300 });
  for (let i = 0; i < 30 * 30; i++) t.step(1 / 30);
  assert.ok(t.vehicles.filter((v) => v.v > 2).length / t.vehicles.length > 0.7);
  addCast(scene);
  const p = createPeople(scene, { w, h, cls }, { seed: 5, proj, heightAt, profile: 'city' });
  for (let i = 0; i < 60; i++) p.step(1 / 30, { tod: 12.5, season: 1, rain: 0, view: [0, 0, 2, 2] });
  assert.ok(p.counts().people > 300, `사람 ${JSON.stringify(p.counts())}`);
});
