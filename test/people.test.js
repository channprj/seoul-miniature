// 사람 행동(src/sim/people.js)과 모형(src/emotes.js) 검사 (node --test). 실제 classes.png·scene.json.gz 로 돌린다.
// 셰이더 출력은 여기서 못 본다 → 화면은 스크린샷으로 확인한다(docs/APP.md).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import zlib from 'node:zlib';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createPeople, CEREMONY_HOURS, PAL_OPEN, HANBOK, T } from '../src/sim/people.js';
import { buildCast, rasterCell, HANBOK_F } from '../src/emotes.js';
import { createBirds } from '../src/birds.js';
import { makeProjection, decodeDepth } from '../src/geom.js';

const here = path.dirname(fileURLToPath(import.meta.url));
// 8bit 비인터레이스 PNG(회색조 classes.png, RGB depth_rg8.png). 필터 0–4. 돌려주는 data 는 채널 ch 개씩.
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
const semPng = readPng(path.resolve(here, '../assets/redraw/classes.png'));
const grid = { w: semPng.w, h: semPng.h, cls: semPng.data };
const sceneText = zlib.gunzipSync(fs.readFileSync(path.resolve(here, '../assets/web-poc/scene.json.gz'))).toString();
// 브라우저(main.js)와 같은 입력: 투영과, 깊이 그림에서 읽은 지면 대비 높이. 이것이 다르면 자리 탐색 결과가 달라진다.
const depthPng = readPng(path.resolve(here, '../assets/redraw/depth_rg8.png'));
const heightFor = (proj) => {
  const dp = depthPng.data, DW = depthPng.w, C = depthPng.ch;
  const groundAt = (y) => -((proj.H / 2 - y) * proj.m + proj.cy) * proj.ey[2] / proj.vd[2] - proj.camDotVd;
  const depthAt = (x, y) => { const o = (y * DW + x) * C, d = decodeDepth(dp[o], dp[o + 1]); return Number.isFinite(d) ? d : groundAt(y + 0.5); };
  return (x, y) => (groundAt(y + 0.5) - depthAt(x, y)) * -proj.vd[2];
};
const DT = 1 / 30;
const make = (seed = 5) => {
  const scene = JSON.parse(sceneText);   // addCast 가 팔레트를 늘리므로 매번 새로 읽는다
  const birds = createBirds(grid, { seed: 11 });
  const proj = makeProjection(scene.camera);
  return { scene, birds, sys: createPeople(scene, grid, { seed, birds, proj, heightAt: heightFor(proj) }), proj };
};
const GROUND = new Set([1, 3, 5, 11]);   // 맨땅·잔디·궁궐 마당·광장/보행로
const ROAD = 2, WATER = 4;

test('결정론: 같은 시드면 같은 상태, 다른 시드면 다른 배치', () => {
  const run = (seed) => {
    const { sys, birds } = make(seed);
    for (let i = 0; i < 3000; i++) { birds.step(DT); sys.step(DT, { tod: 9 + i * DT * 24 / 150, season: 1 }); }
    return JSON.stringify(sys.snapshot());
  };
  const a = run(5);
  assert.equal(a, run(5));
  assert.notEqual(a, run(6));
});

test('60분: 서는 자리·겹침·순간이동·시야 안 생성/소멸·상호작용 횟수', () => {
  const { sys, birds, proj } = make(5);
  const S = [0, 0, 0], P = [0, 0, 0], Q = [0, 0, 0];
  const N = 30 * 60 * 60;
  // 가까이 들여다보는 화면(폭 320 지도 px)이 장소 사이를 천천히 옮겨 다닌다
  const spots = [[850, 1225], [1215, 985], [1275, 800], [1830, 650], [640, 520], [330, 1230]];
  const view = [0, 0, 0, 0];
  const inView = (px, py) => px > view[0] && px < view[2] && py > view[1] && py < view[3];
  const actors = sys.actors, W = sys.walkers;
  const prev = actors.map((a) => ({ on: a.on, x: a.x, y: a.y }));
  const prevVis = W.map((w) => w.vis), prevS = sys.standing.map((s) => s.vis);
  const wp = new Float64Array(W.length * 2);
  let worst = '';
  const flipLog = [];
  let maxActorStep = 0, maxWalkerStep = 0, worstGap = 9, flipsInView = 0, badGround = [], checks = 0;
  for (let i = 0; i < N; i++) {
    const tod = (9 + i * DT * 24 / 150) % 24, season = Math.floor(i / (30 * 600)) % 4, rain = (i % (30 * 900)) > 30 * 800;
    const k = Math.floor(i / 2400) % spots.length, u = (i % 2400) / 2400, a0 = spots[k], a1 = spots[(k + 1) % spots.length];
    const cx = a0[0] + (a1[0] - a0[0]) * u, cy = a0[1] + (a1[1] - a0[1]) * u;
    view[0] = cx - 160; view[1] = cy - 100; view[2] = cx + 160; view[3] = cy + 100;
    birds.step(DT);
    sys.step(DT, { tod, season, rain, view });
    // 출연진: 켜진 채로는 한 스텝에 걸음 이상 움직이지 않는다 / 시야 안에서 켜지거나 꺼지지 않는다
    for (let j = 0; j < actors.length; j++) {
      const a = actors[j], p = prev[j];
      if (i > 0 && a.on !== p.on) { proj.project(a.on ? a.x : p.x, a.on ? a.y : p.y, 0, S); if (inView(S[0], S[1]) && !a.mayHide) { flipsInView++; flipLog.push(`actor ${a.id} ${sys.scenes.find((sc) => sc.actors.includes(a))?.kind} on=${a.on} t=${sys.time.toFixed(1)}`); } }
      if (a.on && p.on) maxActorStep = Math.max(maxActorStep, Math.hypot(a.x - p.x, a.y - p.y));
      p.on = a.on; p.x = a.x; p.y = a.y;
    }
    // 걷는 사람: 시야 안에서 나타나거나 사라지지 않는다(매 스텝), 순간이동 없음(처음 5분은 매 스텝)
    for (let j = 0; j < W.length; j++) {
      if (W[j].vis !== prevVis[j]) { sys.wpos(j, sys.time, P); proj.project(P[0], P[1], 0, S); if (i > 0 && inView(S[0], S[1])) { flipsInView++; flipLog.push(`walker ${j} t=${sys.time.toFixed(1)}`); } prevVis[j] = W[j].vis; }
      if (i < 9000) {
        sys.wpos(j, sys.time, P);
        if (i > 0) maxWalkerStep = Math.max(maxWalkerStep, Math.hypot(P[0] - wp[j * 2], P[1] - wp[j * 2 + 1]));
        wp[j * 2] = P[0]; wp[j * 2 + 1] = P[1];
      }
    }
    sys.standing.forEach((s, j) => { if (s.vis !== prevS[j]) { proj.project(s.x, s.y, 0, S); if (i > 0 && inView(S[0], S[1])) { flipsInView++; flipLog.push(`standing ${j}`); } prevS[j] = s.vis; } });
    if (i % 15) continue;
    // 서 있는(또는 걷는) 출연진·세운 사람·그 동행: 차도·물·건물 위가 아니다. 멈춘 사람끼리 0.6 m 안으로 겹치지 않는다.
    checks++;
    const still = [];
    for (const a of actors) {
      if (!a.on || a.mayHide) continue;
      const c = sys.clsAt(a.x, a.y);
      if (!GROUND.has(c)) badGround.push(['actor', a.id, c]);
      if (!a.moving) still.push(a);
    }
    for (const g of sys.guests) {
      for (const p of [g, ...g.fol]) { const c = sys.clsAt(p.x, p.y); if (!GROUND.has(c)) badGround.push(['guest', g.wi, c]); still.push(p); }
    }
    for (const s of sys.standing) if (s.vis) { const c = sys.clsAt(s.x, s.y); if (c === ROAD || c === WATER) badGround.push(['standing', c]); still.push(s); }
    still.sort((a, b) => a.x - b.x);
    for (let a = 0; a < still.length; a++) for (let b = a + 1; b < still.length && still[b].x - still[a].x < 0.6; b++) { const d = Math.hypot(still[a].x - still[b].x, still[a].y - still[b].y); if (d < worstGap) { worstGap = d; worst = [still[a], still[b]].map((p) => `${p.id ?? (p.wi !== undefined ? 'guest' : p.look && p.key !== undefined ? 'standing' : 'fol')}:${p.look.fam}@${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' / ') + ` t=${sys.time.toFixed(0)}`; } }
  }
  assert.deepEqual(badGround.slice(0, 5), [], `차도·물·건물 위에 선 사람 ${badGround.length}건`);
  assert.ok(worstGap >= 0.6, `멈춘 사람끼리 가장 가까운 거리 ${worstGap.toFixed(2)} m: ${worst}`);
  assert.ok(maxActorStep <= 7.0 * DT,   // 가장 빠른 것은 자동 흐름에서 줄인 교대 의식의 행진(약 6 m/s)
    `출연진 한 스텝 이동 ${maxActorStep.toFixed(3)} m`);
  assert.ok(maxWalkerStep <= 4.2 * DT, `걷는 사람 한 스텝 이동 ${maxWalkerStep.toFixed(3)} m`);
  assert.equal(flipsInView, 0, `시야 안에서 나타나거나 사라진 사람: ${flipLog.slice(0, 6).join(' | ')}`);
  // 상호작용 종류별 최소 횟수(60분, 하루 150초 × 24바퀴, 계절 10분씩, 비 15분마다 100초)
  const min = { chat: 60, ask: 15, askphoto: 5, kiddog: 1, photo: 100, nightphoto: 5, classphoto: 5, guide: 10, hanbok: 30, couple: 10, share: 1, pigeon: 10, picnic: 20, bench: 50, jog: 5, ceremony: 5, snow: 20, cat: 20, busk: 5, proposal: 5, kite: 5, soap: 20 };
  for (const [k, n] of Object.entries(min)) assert.ok(sys.stats[k] >= n, `${k}: ${sys.stats[k]}회 (최소 ${n})`);
  assert.ok(checks > 7000);
});

test('수문장 교대 의식: 10시·14시에 시작하고, 끝나면 수문장이 들어간다. 다른 시각에는 시작하지 않는다', () => {
  for (const h of CEREMONY_HOURS) {
    const { sys, birds } = make(5);
    const c = sys.ceremony;
    assert.ok(c, '의식 자리를 찾지 못했다');
    for (let i = 0; i < 60; i++) { birds.step(DT); sys.step(DT, { tod: h + 0.1 }); }
    assert.ok(c.st !== 'idle' && c.lastStart, `${h}시에 시작하지 않았다`);
    assert.ok(c.lastStart.tod >= h && c.lastStart.tod < h + 0.5);
    assert.ok(c.guards.every((g) => g.on));
    let n = 0, watched = 0;
    while (c.st !== 'idle' && n < 30 * 300) { birds.step(DT); sys.step(DT, { tod: h + 0.1 }); n++; if (c.st === 'hold') watched = c.watchers.filter((w) => Math.hypot(w.x - c.C[0], w.y - c.C[1]) < 12).length; }
    const dur = n * DT;
    assert.ok(c.lastEnd && dur > 35 && dur < 150, `의식 길이 ${dur.toFixed(0)} s`);
    assert.ok(c.guards.every((g) => !g.on), '끝난 뒤에도 수문장이 남아 있다');
    assert.ok(watched >= 4, `구경꾼 ${watched}명`);
  }
  const { sys, birds } = make(5);
  for (let i = 0; i < 30 * 120; i++) { birds.step(DT); sys.step(DT, { tod: 12 }); }
  assert.equal(sys.stats.ceremony, 0);
});

test('궁 안 한복 비율: 낮 방문객의 25~35 %, 도심은 드물다', () => {
  for (const seed of [5, 6, 7]) {
    const { sys, birds } = make(seed);
    for (let i = 0; i < 90; i++) { birds.step(DT); sys.step(DT, { tod: 13, season: 2 }); }
    const c = sys.census();
    assert.ok(c.visitors > 300, `궁 안 방문객 ${c.visitors}`);
    assert.ok(c.ratio >= 0.25 && c.ratio <= 0.35, `seed ${seed}: 한복 ${(c.ratio * 100).toFixed(1)} % (${c.hanbok}/${c.visitors})`);
    const city = sys.walkers.filter((w) => w.zone === 's');
    const hb = city.filter((w) => w.type === T.HANBOK).length / city.length;
    assert.ok(hb < HANBOK.near && hb > 0, `궁 밖 한복 ${(hb * 100).toFixed(1)} %`);
  }
});

test('유형: 모든 유형이 있고, 아이는 보호자 뒤 1 m 안에서 같은 경로를 걷는다', () => {
  const { sys } = make(5);
  const n = new Array(14).fill(0);
  for (const w of sys.walkers) n[w.type]++;
  for (const [name, t] of Object.entries(T)) assert.ok(n[t] >= 5, `${name}: ${n[t]}명`);
  const P = [0, 0, 0], Q = [0, 0, 0];
  sys.walkers.forEach((w, i) => {
    for (const f of w.fol) {
      assert.ok(Math.abs(f.dd) <= 3.2);
      for (const t of [0, 7.3, 31.9]) { sys.wpos(i, t, P); sys.wpos(i, t, Q, f.dd); assert.ok(Math.hypot(P[0] - Q[0], P[1] - Q[1]) <= Math.abs(f.dd) + 1e-6); }
      if (f.look.fam === 'k' || f.look.fam === 'hk') assert.ok(Math.abs(f.dd) <= 1);
    }
  });
});

test('탭: 가까운 사람이 반응하고, 잠깐 섰다가 그 자리에서 다시 걷는다(순간이동 없음). locate 로 따라갈 수 있다', () => {
  const { sys, birds, proj } = make(5);
  for (let i = 0; i < 30; i++) { birds.step(DT); sys.step(DT, { tod: 12 }); }
  const S = [0, 0, 0], P = [0, 0, 0];
  const wi = sys.walkers.findIndex((w, i) => { if (!w.vis || w.fol.length) return false; sys.wpos(i, sys.time, P); return sys.clsAt(P[0], P[1]) === 11; });
  sys.wpos(wi, sys.time, P); proj.project(P[0], P[1], P[2], S);
  const hit = sys.tap(S[0], S[1] - 2, 3);
  assert.ok(hit && hit.wi >= 0);
  assert.equal(sys.stats.tap, 1);
  const p0 = sys.locate(hit).slice();
  let maxStep = 0, last = [P[0], P[1]];
  for (let i = 0; i < 30 * 6; i++) { birds.step(DT); sys.step(DT, { tod: 12 }); sys.wpos(hit.wi, sys.time, P); maxStep = Math.max(maxStep, Math.hypot(P[0] - last[0], P[1] - last[1])); last = [P[0], P[1]]; }
  assert.ok(maxStep < 0.15, `탭한 사람의 한 스텝 이동 ${maxStep}`);
  const p1 = sys.locate(hit);
  assert.ok(p1 && Math.hypot(p1[0] - p0[0], p1[1] - p0[1]) > 0.5, '다시 걷지 않는다');
  assert.equal(sys.tap(-500, -500, 3), null);
});

test('찾아보기: 가까이 본 화면 안의 장면만 잡힌다', () => {
  const { sys, birds } = make(5);
  for (let i = 0; i < 30; i++) { birds.step(DT); sys.step(DT, { tod: 12, season: 2 }); }
  const p = sys.force('proposal');
  assert.ok(p);
  assert.ok(sys.spot([p.x - 100, p.y - 60, p.x + 100, p.y + 60]).includes('proposal'));
  assert.ok(!sys.spot([p.x + 300, p.y - 60, p.x + 500, p.y + 60]).includes('proposal'));
  assert.deepEqual(sys.spot([0, 0, 2752, 1696]), [], '멀리서 본 화면은 세지 않는다');
});

test('모형: 모든 칸이 세 해상도에서 칸 안에 그려진다. 치마저고리 12벌 이상', () => {
  const { scene } = make(5);
  const reg = buildCast(scene);
  assert.ok(HANBOK_F.length >= 12 && reg.hf.length === HANBOK_F.length);
  for (const k of [1, 2, 4]) {
    for (const c of reg.cells) {
      let n = 0;
      rasterCell(c, k, (x, y) => { n++; assert.ok(x >= 0 && y >= 0 && x < c.w * k && y < c.h * k); });
      assert.ok(n > 0, `빈 칸 #${c.i} (k=${k})`);
    }
  }
  // 한복은 실루엣으로 구분된다: 기본 해상도에서 치마 밑단이 어깨보다 넓다
  const rows = [];
  rasterCell(reg.hf[0][2], 1, (x, y) => { rows[y] = (rows[y] || 0) + 1; });
  assert.ok(rows[10] >= 6 && rows[4] <= 4);
});

test('자동 흐름(하루 150초)에서도 교대 의식이 10시와 14시에 한 번씩 열리고, 넓힌 대열로 선다', () => {
  const { sys, birds } = make(5);
  const c = sys.ceremony, starts = [];
  assert.ok(c.form[2] >= 1.6, `늘어선 줄 간격 ${c.form[2]} m`);
  assert.ok(c.len <= 35, `행진 거리 ${c.len.toFixed(0)} m`);
  let tod = 9, st = 'idle', minGap = 9;
  for (let i = 0; i < 30 * 68; i++) {
    tod += DT * 24 / 150;
    birds.step(DT); sys.step(DT, { tod });
    if (c.st !== st) { if (c.st === 'out') starts.push(tod); st = c.st; }
    if (c.st === 'hold') for (let a = 0; a < c.guards.length; a++) for (let b = a + 1; b < c.guards.length; b++) minGap = Math.min(minGap, Math.hypot(c.guards[a].x - c.guards[b].x, c.guards[a].y - c.guards[b].y));
  }
  assert.equal(starts.length, 2, `시작 시각 ${starts.map((t) => t.toFixed(2))}`);
  assert.ok(starts[0] >= 10 && starts[0] < 10.3 && starts[1] >= 14 && starts[1] < 15, `시작 시각 ${starts.map((t) => t.toFixed(2))}`);
  assert.ok(minGap >= 1.5, `늘어선 수문장 사이 ${minGap.toFixed(2)} m`);
  assert.equal(c.st, 'idle');
});

test('관람 시간 밖에는 궁 안에 방문객·안내원·장면이 없다. 야경 사진은 담 밖에서만', () => {
  const { sys, birds } = make(5);
  for (const tod of [12, 21, 7]) {
    for (let i = 0; i < 30 * 30; i++) { birds.step(DT); sys.step(DT, { tod, season: 2 }); }
    const inP = sys.walkers.filter((w) => w.vis && w.zone === 'p').length + sys.standing.filter((s) => s.vis && s.zone === 'p').length;
    const scP = sys.scenes.filter((sc) => sc.on && sc.inPal).length;
    if (tod >= PAL_OPEN[0] && tod < PAL_OPEN[1]) { assert.ok(inP > 300 && scP > 10); continue; }
    assert.equal(inP, 0, `${tod}시 궁 안 사람 ${inP}`);
    assert.equal(scP, 0, `${tod}시 궁 안 장면 ${scP}`);
    assert.equal(sys.census().visitors, 0);
  }
  const before = sys.stats.nightphoto;
  for (let i = 0; i < 30 * 120; i++) { birds.step(DT); sys.step(DT, { tod: 21, season: 2 }); }
  assert.ok(sys.stats.nightphoto - before >= 3, `밤 사진 ${sys.stats.nightphoto - before}회`);
  assert.ok(sys.scenes.filter((sc) => sc.kind === 'photo' && sc.on).every((sc) => !sc.inPal));
});

test('해치: 광화문 앞에 대칭으로 한 쌍, 보도·광장 위. 사람이 0.8 m 안에 서거나 지나가지 않는다', () => {
  const { sys, birds } = make(5);
  assert.equal(sys.haechi.length, 2);
  const [a, b] = sys.haechi;
  assert.ok(Math.abs(a.y - b.y) < 1e-6 && b.x - a.x >= 18 && b.x - a.x <= 40, `간격 ${(b.x - a.x).toFixed(1)} m`);
  for (const h of sys.haechi) for (const [dx, dy] of [[0, 0], [1.2, 0], [-1.2, 0], [0, 1.2], [0, -1.2]]) assert.ok([1, 11].includes(sys.clsAt(h.x + dx, h.y + dy)), `클래스 ${sys.clsAt(h.x + dx, h.y + dy)}`);
  assert.ok(sys.scenes.filter((sc) => sc.haechi).length >= 2, '해치 앞 사진 자리');
  const P = [0, 0, 0];
  let near = 9;
  const see = (x, y) => { for (const h of sys.haechi) near = Math.min(near, Math.hypot(x - h.x, y - h.y)); };
  for (let i = 0; i < 30 * 240; i++) {
    birds.step(DT); sys.step(DT, { tod: 9 + i * DT * 24 / 150, season: 2 });
    if (i % 5) continue;
    for (const a2 of sys.actors) if (a2.on) see(a2.x, a2.y);
    for (const g of sys.guests) { see(g.x, g.y); for (const f of g.fol) see(f.x, f.y); }
    for (const s2 of sys.standing) if (s2.vis) see(s2.x, s2.y);
    for (let j = 0; j < sys.walkers.length; j++) if (sys.walkers[j].vis) { sys.wpos(j, sys.time, P); see(P[0], P[1]); }
    for (const r of sys.runners) if (r.vis) { sys.rpos(r, 1, P); see(P[0], P[1]); }
  }
  assert.ok(near >= 0.8, `해치에 가장 가까이 간 사람 ${near.toFixed(2)} m`);
  assert.ok(sys.spot([0, 0, 0, 0]).length === 0);
  const px = sys.toPx(a.x, a.y);
  assert.ok(sys.spot([px[0] - 100, px[1] - 60, px[0] + 100, px[1] + 60]).includes('haechi'));
});

test('궁 둘레 러너: 담길(보도) 위만 달리고 차도·궁 안에 들어가지 않는다. 아침·저녁에 많고 낮에도 있다. 크루는 줄지어 달린다', () => {
  const { sys, birds } = make(5);
  const total = sys.runChains.reduce((s2, c) => s2 + c.L, 0);
  assert.ok(total > 1500, `담길 ${total.toFixed(0)} m`);
  assert.ok(sys.runners.some((r) => r.fol.length >= 3) && sys.runners.filter((r) => !r.fol.length).length > 10);
  // 구간을 이어 붙였다: 가로수에 가려 끊겼던 곳이 합쳐져 긴 구간(500 m 이상)이 둘 넘게 나온다. 클래스 10 = 가로수 수관에 가려진 담길(화면 공간 클래스 맵).
  assert.ok(sys.runChains.filter((c) => c.L >= 500).length >= 2, `구간 ${sys.runChains.map((c) => c.L.toFixed(0))}`);
  const P = [0, 0, 0], Q = [0, 0, 0];
  const view = [1400, 1000, 1720, 1200];   // 동쪽 담길을 가까이 보는 화면
  // 보고 있는 화면 안의 러너는 사라지지 않으므로(그게 규칙) 수를 셀 때는 화면 밖만 센다
  const count = () => sys.runners.filter((r) => { if (!r.vis) return false; sys.rpos(r, 1, P); const s2 = sys.toPx(P[0], P[1]); return !(s2[0] > view[0] - 60 && s2[0] < view[2] + 60 && s2[1] > view[1] - 60 && s2[1] < view[3] + 60); }).reduce((n, r) => n + 1 + r.fol.length, 0);
  const n = {};
  let bad = [], maxStep = 0, flips = 0;
  const inView = (x, y) => { const s2 = sys.toPx(x, y); return s2[0] > view[0] && s2[0] < view[2] && s2[1] > view[1] && s2[1] < view[3]; };
  const prev = sys.runners.map((r) => { sys.rpos(r, 1, P); return [P[0], P[1], r.vis]; });
  for (const [tod, season, rain, key] of [[7.5, 2, false, 'am'], [12, 2, false, 'noon'], [19.5, 2, false, 'pm'], [3, 2, false, 'night'], [7.5, 2, true, 'rain'], [7.5, 3, false, 'winter']]) {
    for (let i = 0; i < 30 * 45; i++) {
      birds.step(DT); sys.step(DT, { tod, season, rain, view });
      sys.runners.forEach((r, j) => {
        sys.rpos(r, 1, P);
        if (i > 0 || key !== 'am') {
          maxStep = Math.max(maxStep, Math.hypot(P[0] - prev[j][0], P[1] - prev[j][1]));
          if (r.vis !== prev[j][2] && inView(P[0], P[1])) flips++;
        }
        prev[j][0] = P[0]; prev[j][1] = P[1]; prev[j][2] = r.vis;
        if (!r.vis || i % 6) return;
        for (const dd of [0, ...r.fol.map((f) => f.dd)]) { sys.rpos(r, 1, Q, dd); const c = sys.clsAt(Q[0], Q[1]); if ((c !== 1 && c !== 11 && c !== 10) || sys.inPalace(Q[0], Q[1])) bad.push([key, r.id, dd, c]); }
      });
    }
    n[key] = count();
  }
  assert.deepEqual(bad.slice(0, 5), [], `보도 밖 ${bad.length}건`);
  assert.ok(maxStep <= 0.3, `러너 한 스텝 이동 ${maxStep.toFixed(3)} m`);
  assert.equal(flips, 0, '시야 안에서 나타나거나 사라진 러너');
  assert.ok(n.am >= 55 && n.pm >= 55, `아침 ${n.am} 저녁 ${n.pm}`);
  assert.ok(n.noon >= 20 && n.noon <= n.am * 0.65, `낮 ${n.noon}`);
  assert.ok(n.night <= 8, `새벽 ${n.night}`);
  assert.ok(n.rain <= n.am * 0.45 && n.winter < n.am, `비 ${n.rain} 겨울 ${n.winter}`);
});
