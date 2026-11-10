// Invariant tests for app/src/sim/traffic.js against the real scene export.
// Run: node --test app/test/
import { describe, it, before } from 'node:test';
import assert from 'node:assert/strict';
import zlib from 'node:zlib';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createTraffic } from '../src/sim/traffic.js';

const SCENE_PATH = fileURLToPath(new URL('../assets/web-poc/scene.json.gz', import.meta.url));
const DT = 1 / 30;
const TEN_MIN = 18000;
const TARGET = 260;
const V_MAX = 15; // m/s, above every class speed (primary 11–14) incl. per-driver variation

function loadScene() {
  return JSON.parse(zlib.gunzipSync(fs.readFileSync(SCENE_PATH)));
}

// Separating-axis test for two oriented boxes (centre x,y, heading th, size len×wid).
// Touching edges do not count as overlap.
function obbOverlap(a, b) {
  const ca = Math.cos(a.th), sa = Math.sin(a.th);
  const cb = Math.cos(b.th), sb = Math.sin(b.th);
  const dx = b.x - a.x, dy = b.y - a.y;
  const axes = [[ca, sa], [-sa, ca], [cb, sb], [-sb, cb]];
  for (const [ux, uy] of axes) {
    const pa = (a.len / 2) * Math.abs(ca * ux + sa * uy) + (a.wid / 2) * Math.abs(-sa * ux + ca * uy);
    const pb = (b.len / 2) * Math.abs(cb * ux + sb * uy) + (b.wid / 2) * Math.abs(-sb * ux + cb * uy);
    if (Math.abs(dx * ux + dy * uy) >= pa + pb) return false;
  }
  return true;
}

function snapshot(T) {
  return JSON.stringify({
    time: T.time,
    vehicles: T.vehicles.map((v) => [v.id, v.kind, v.color, v.lane, v.s, v.v, v.x, v.y, v.z, v.th]),
    signals: T.signals.map((s) => s.state),
  });
}

describe('traffic sim, 10 minutes at 1/30 s (seed 1)', () => {
  const m = {
    sameLane: [], obb: [], red: [], nan: [], jump: [],
    visMin: Infinity, visMax: 0, visSum: 0, speedSum: 0, speedN: 0,
    lastMinSpeedSum: 0, lastMinN: 0, maxJump: 0, statesSeen: [],
  };
  let scene;
  let T;
  let initialVisible;
  let initialAlive;

  before(() => {
    scene = loadScene();
    T = createTraffic(scene, { seed: 1, targetCount: TARGET });
    initialVisible = T.vehicles.filter((v) => v.vis).length;
    initialAlive = T.vehicles.length;
    m.statesSeen = T.signals.map(() => new Set());
    const laneId = (i) => scene.lanes[i]?.id ?? i;
    const grid = new Map();
    const byLane = new Map();

    for (let step = 0; step < TEN_MIN; step++) {
      const pre = new Map();
      for (const v of T.vehicles) pre.set(v.id, { lane: v.lane, conn: v.conn, s: v.s, len: v.len, x: v.x, y: v.y, v: v.v });
      const sigBefore = T.signals.map((s) => s.state);

      T.step(DT);
      const V = T.vehicles;

      // signals: red at both ends of the step means the stop line was closed for the whole step
      for (let i = 0; i < T.signals.length; i++) {
        const S = T.signals[i];
        m.statesSeen[i].add(S.state);
        if (sigBefore[i] !== 'r' || S.state !== 'r') continue;
        for (const v of V) {
          const p = pre.get(v.id);
          if (!p || p.conn || p.lane !== S.lane) continue;
          if (p.s + p.len / 2 > S.s + 1e-6) continue; // already past the line
          const front = !v.conn && v.lane === S.lane ? v.s + v.len / 2 : Infinity;
          if (front > S.s + 1e-6) m.red.push({ step, id: v.id, lane: laneId(S.lane), line: S.s, from: p.s, to: v.s });
        }
      }

      // finiteness and per-step displacement (spawns excluded: no pre-step record)
      for (const v of V) {
        if (![v.x, v.y, v.z, v.th, v.v, v.s, v.px, v.py, v.pz, v.pth].every(Number.isFinite)) m.nan.push({ step, id: v.id });
        const p = pre.get(v.id);
        if (!p) continue;
        const d = Math.hypot(v.x - p.x, v.y - p.y);
        if (d > m.maxJump) m.maxJump = d;
        if (d > V_MAX * DT + 0.02) m.jump.push({ step, id: v.id, d, lane: laneId(v.lane) });
      }

      // same lane: bumper gap >= 0.5 m between consecutive vehicles on a lane
      byLane.clear();
      for (const v of V) {
        if (v.conn) continue;
        let a = byLane.get(v.lane);
        if (!a) byLane.set(v.lane, (a = []));
        a.push(v);
      }
      for (const [ln, a] of byLane) {
        a.sort((p, q) => p.s - q.s);
        for (let i = 1; i < a.length; i++) {
          const gap = a[i].s - a[i].len / 2 - (a[i - 1].s + a[i - 1].len / 2);
          if (gap < 0.5) m.sameLane.push({ step, lane: laneId(ln), a: a[i - 1].id, b: a[i].id, gap });
        }
      }

      // global footprint overlap, 12 m buckets
      grid.clear();
      for (const v of V) {
        const k = `${Math.floor(v.x / 12)},${Math.floor(v.y / 12)}`;
        let a = grid.get(k);
        if (!a) grid.set(k, (a = []));
        a.push(v);
      }
      for (const v of V) {
        const cx = Math.floor(v.x / 12), cy = Math.floor(v.y / 12);
        for (let gx = cx - 1; gx <= cx + 1; gx++) {
          for (let gy = cy - 1; gy <= cy + 1; gy++) {
            const a = grid.get(`${gx},${gy}`);
            if (!a) continue;
            for (const w of a) {
              if (w.id <= v.id) continue;
              if (obbOverlap(v, w)) m.obb.push({ step, a: v.id, b: w.id, la: laneId(v.lane), lb: laneId(w.lane) });
            }
          }
        }
      }

      let vis = 0;
      for (const v of V) {
        if (v.vis) vis++;
        m.speedSum += v.v;
        m.speedN++;
      }
      m.visSum += vis;
      m.visMin = Math.min(m.visMin, vis);
      m.visMax = Math.max(m.visMax, vis);
      if (step >= TEN_MIN - 1800) {
        let sv = 0;
        for (const v of V) sv += v.v;
        m.lastMinSpeedSum += sv / Math.max(1, V.length);
        m.lastMinN++;
      }
    }
    // reported in the test log
    console.log(
      `10 min: visible avg ${(m.visSum / TEN_MIN).toFixed(1)} min ${m.visMin} max ${m.visMax}; ` +
        `speed avg ${(m.speedSum / m.speedN).toFixed(2)} m/s, last minute ${(m.lastMinSpeedSum / m.lastMinN).toFixed(2)} m/s; ` +
        `max step displacement ${m.maxJump.toFixed(3)} m; stats ${JSON.stringify(T.stats)}`,
    );
  });

  it('starts with the road already populated', () => {
    assert.ok(initialAlive > 0);
    assert.ok(initialVisible >= TARGET * 0.7 && initialVisible <= TARGET * 1.3, `visible at t=0: ${initialVisible}`);
  });

  it('has no same-lane overlap (bumper gap >= 0.5 m)', () => {
    assert.equal(m.sameLane.length, 0, JSON.stringify(m.sameLane.slice(0, 5)));
  });

  it('has no global OBB overlap', () => {
    assert.equal(m.obb.length, 0, JSON.stringify(m.obb.slice(0, 5)));
  });

  it('never crosses a stop line on red', () => {
    assert.ok(T.signals.length > 0, 'expected signals at major junctions');
    assert.equal(m.red.length, 0, JSON.stringify(m.red.slice(0, 5)));
  });

  it('cycles every signal through green, yellow and red', () => {
    for (let i = 0; i < T.signals.length; i++) {
      assert.deepEqual([...m.statesSeen[i]].sort(), ['g', 'r', 'y'], `signal ${i}`);
    }
  });

  it('produces no NaN or infinite values', () => {
    assert.equal(m.nan.length, 0, JSON.stringify(m.nan.slice(0, 5)));
  });

  it('keeps the visible count within ±30% of targetCount', () => {
    assert.ok(m.visMin >= TARGET * 0.7, `min visible ${m.visMin}`);
    assert.ok(m.visMax <= TARGET * 1.3, `max visible ${m.visMax}`);
  });

  it('keeps traffic moving in the last minute (avg speed > 1 m/s)', () => {
    assert.ok(m.lastMinSpeedSum / m.lastMinN > 1, `avg ${m.lastMinSpeedSum / m.lastMinN}`);
  });

  it('despawns vehicles at sinks', () => {
    assert.ok(T.stats.despawned > 0);
  });

  it('does not teleport (per-step move <= v_max·dt, spawns excluded)', () => {
    assert.equal(m.jump.length, 0, JSON.stringify(m.jump.slice(0, 5)));
  });

  it('only uses (kind, color) pairs that exist in the vehicle atlas', () => {
    const combos = new Set(scene.vehicle_atlas.frames.map((f) => `${f.kind}|${f.color}`));
    assert.equal(combos.size, 29);
    for (const v of T.vehicles) assert.ok(combos.has(`${v.kind}|${v.color}`), `${v.kind} ${v.color}`);
  });

  it('exposes the vehicle and signal contract', () => {
    const keys = ['id', 'kind', 'color', 'len', 'wid', 'h', 'lane', 's', 'v', 'x', 'y', 'z', 'th', 'px', 'py', 'pz', 'pth', 'braking'];
    for (const v of T.vehicles.slice(0, 20)) for (const k of keys) assert.ok(k in v, `vehicle.${k}`);
    for (const s of T.signals) {
      for (const k of ['x', 'y', 'z', 'th', 'state']) assert.ok(k in s, `signal.${k}`);
      assert.ok(['g', 'y', 'r'].includes(s.state));
    }
    assert.ok(Math.abs(T.time - TEN_MIN * DT) < 1e-6);
  });
});

// Congestion acceptance (seed 7, 6 simulated minutes per target). White-box: reads the sim's
// internal wait bookkeeping (_why, _zr, _lead, _ovv, _atRed, _stuck).
// "Stuck" = standing (< 0.1 m/s) for more than 20 s. A stuck vehicle counts as a red-light
// queue when, at some point of its current standing episode, the chain of vehicles it waits
// behind (leader, vehicle ordered ahead at a merge, leader beyond a box it may not block) reached
// a vehicle held by a red light. Everything else is a logical / spill-back wait.
const CONGESTION_STEPS = 6 * 60 * 30;
const MAX_CYCLE = 2 * (36 + 3 + 2); // two-group controller: max green + yellow + all-red, twice

function waitsBehind(v) {
  if (v._why === 'lead') return v._lead;
  if (v._why === 'merge') return v._ovv;
  if (v._why === 'zone' && (v._zr === 'dbb' || v._zr === 'queue')) return v._lead ?? v._ovv;
  return null;
}

function inRedQueue(v) {
  for (let w = v, d = 0; w && d < 80; w = waitsBehind(w), d++) if (w._atRed) return true;
  return false;
}

function runCongestion(scene, target) {
  const T = createTraffic(scene, { seed: 7, targetCount: target });
  const redEpisode = new Set();
  const r = { notRedMax: 0, notRedAt: -1, maxStuck: 0, visSum: 0 };
  // Signal-approach delay: from the moment a vehicle on a signalled lane first drops below 2 m/s
  // until its front crosses that lane's stop line (or it leaves the lane past it).
  const linesOf = new Map();
  for (const S of T.signals) linesOf.set(S.lane, [...(linesOf.get(S.lane) ?? []), S.s]);
  const approach = new Map();
  const delays = [];
  for (let step = 1; step <= CONGESTION_STEPS; step++) {
    T.step(DT);
    r.visSum += T.visibleCount;
    const t = step * DT;
    for (const v of T.vehicles) {
      const front = v.s + v.len / 2;
      let a = approach.get(v.id);
      if (a && (v.conn || v.lane !== a.lane || front > a.line)) {
        if (a.t0 !== null) delays.push(t - a.t0);
        approach.delete(v.id);
        a = null;
      }
      if (!a && !v.conn && linesOf.has(v.lane)) {
        const line = linesOf.get(v.lane).find((s) => s >= front - 0.01);
        if (line !== undefined) approach.set(v.id, (a = { lane: v.lane, line, t0: null }));
      }
      if (a && a.t0 === null && v.v < 2) a.t0 = t;
    }
    if (step % 300 === 0) for (const id of approach.keys()) if (!T.vehicles.some((v) => v.id === id)) approach.delete(id);
    for (const v of T.vehicles) if (v._stuck > r.maxStuck) r.maxStuck = v._stuck;
    if (step % 30) continue;
    for (const v of T.vehicles) {
      if (v._stuck === 0) redEpisode.delete(v.id);
      else if (!redEpisode.has(v.id) && inRedQueue(v)) redEpisode.add(v.id);
    }
    if (step % 900) continue;
    let n = 0;
    for (const v of T.vehicles) if (v._stuck > 20 && !redEpisode.has(v.id)) n++;
    if (n > r.notRedMax) {
      r.notRedMax = n;
      r.notRedAt = step * DT;
    }
  }
  delays.sort((a, b) => a - b);
  r.approachN = delays.length;
  r.approachP95 = delays[Math.floor(0.95 * delays.length)];
  r.approachMax = delays[delays.length - 1];
  r.stats = { ...T.stats };
  r.visAvg = r.visSum / CONGESTION_STEPS;
  console.log(`congestion target ${target}: ${JSON.stringify({ ...r, visSum: undefined })}`);
  return r;
}

for (const target of [150, 190]) {
  describe(`traffic congestion at targetCount ${target} (seed 7, 6 minutes)`, () => {
    let r;
    before(() => {
      r = runCongestion(loadScene(), target);
    });

    it('keeps vehicles stuck > 20 s outside red-light queues at <= 5 (sampled every 30 s)', () => {
      assert.ok(r.notRedMax <= 5, `max ${r.notRedMax} at t=${r.notRedAt} s`);
    });

    it('never leaves a vehicle standing without a break for two signal cycles', () => {
      assert.ok(r.maxStuck < 2 * MAX_CYCLE, `longest stand ${r.maxStuck.toFixed(1)} s`);
    });

    it('gets 95 % of vehicles that queue at a signal over the stop line within two cycles', () => {
      assert.ok(r.approachN > 200, `only ${r.approachN} approach crossings`);
      assert.ok(r.approachP95 < 2 * MAX_CYCLE, `p95 ${r.approachP95.toFixed(0)} s, max ${r.approachMax.toFixed(0)} s`);
    });

    it('removes no vehicle by force', () => {
      assert.equal(r.stats.forcedRemovals, 0);
    });

    it('rarely needs the escape hatch or the footprint guard (logical waits resolve by the rules)', () => {
      assert.ok(r.stats.escapes <= 300, `escape steps ${r.stats.escapes}`); // <= 10 vehicle-seconds
      assert.ok(r.stats.guardStops <= 30, `guard stops ${r.stats.guardStops}`);
    });

    it('still shows about targetCount vehicles', () => {
      assert.ok(r.visAvg >= target * 0.9, `visible avg ${r.visAvg.toFixed(1)}`);
    });
  });
}

describe('traffic sim determinism and fleet mix', () => {
  let scene;
  before(() => {
    scene = loadScene();
  });

  it('same seed gives an identical state; a different seed does not', () => {
    const run = (seed) => {
      const T = createTraffic(scene, { seed });
      for (let i = 0; i < 1800; i++) T.step(DT);
      return snapshot(T);
    };
    const a = run(7);
    const b = run(7);
    const c = run(8);
    assert.equal(a, b);
    assert.notEqual(a, c);
  });

  it('every spawned vehicle uses an atlas combo; buses are rare; taxis are orange or white', () => {
    const combos = new Set(scene.vehicle_atlas.frames.map((f) => `${f.kind}|${f.color}`));
    const T = createTraffic(scene, { seed: 3 });
    const seen = new Map();
    for (let i = 0; i < 3600; i++) {
      T.step(DT);
      for (const v of T.vehicles) seen.set(v.id, v);
    }
    const kinds = {};
    for (const v of seen.values()) {
      assert.ok(combos.has(`${v.kind}|${v.color}`), `${v.kind} ${v.color}`);
      kinds[v.kind] = (kinds[v.kind] ?? 0) + 1;
      if (v.kind === 'taxi') assert.ok(['#e8892f', '#f4f4f0'].includes(v.color.toLowerCase()), `taxi ${v.color}`);
    }
    const total = seen.size;
    assert.ok((kinds.bus ?? 0) / total < 0.08, `bus share ${(kinds.bus ?? 0) / total}`);
    assert.ok((kinds.sedan ?? 0) > (kinds.suv ?? 0), JSON.stringify(kinds));
  });
});

// 버스: 차체가 길어 굽은 길·차로 변경에서 옆 차로를 쓸고 지나간다 (축 모델 자세 + 쓸고 가는 자리
// 잠금 구역). 버스가 실제로 다니고, 그래도 겹침·강제 제거·오래 선 버스가 없어야 한다.
describe('buses (seed 7, targetCount 150, 10 minutes)', () => {
  const r = { ids: new Set(), initial: new Set(), maxNow: 0, maxVisNow: 0, overlap: [], maxBusStuck: 0 };
  let T;
  before(() => {
    T = createTraffic(loadScene(), { seed: 7, targetCount: 150 });
    for (const v of T.vehicles) if (v.kind === 'bus') r.initial.add(v.id);
    for (let step = 0; step < TEN_MIN; step++) {
      T.step(DT);
      const V = T.vehicles;
      const buses = V.filter((v) => v.kind === 'bus');
      r.maxNow = Math.max(r.maxNow, buses.length);
      r.maxVisNow = Math.max(r.maxVisNow, buses.filter((v) => v.vis).length);
      for (const b of buses) {
        r.ids.add(b.id);
        if (b._stuck > r.maxBusStuck) r.maxBusStuck = b._stuck;
        for (const o of V) {
          if (o === b || (o.kind === 'bus' && o.id < b.id)) continue;
          if (Math.abs(o.x - b.x) > 14 || Math.abs(o.y - b.y) > 14) continue;
          if (obbOverlap(b, o)) r.overlap.push({ step, bus: b.id, other: o.id, kind: o.kind });
        }
      }
    }
    console.log(`buses: ${r.ids.size} seen (${[...r.ids].filter((id) => !r.initial.has(id)).length} spawned), max ${r.maxNow} at once (${r.maxVisNow} on the map), longest bus stand ${r.maxBusStuck.toFixed(1)} s; stats ${JSON.stringify(T.stats)}`);
  });

  it('spawns buses and shows several at once', () => {
    assert.ok([...r.ids].some((id) => !r.initial.has(id)), 'no bus spawned after the start');
    assert.ok(r.maxVisNow >= 4, `at most ${r.maxVisNow} buses on the map at once`);
  });

  it('never overlaps a bus footprint with another vehicle', () => {
    assert.equal(r.overlap.length, 0, JSON.stringify(r.overlap.slice(0, 5)));
  });

  it('removes no vehicle by force and needs no footprint guard stops', () => {
    assert.equal(T.stats.forcedRemovals, 0);
    assert.equal(T.stats.guardStops, 0);
  });

  it('never leaves a bus standing for two signal cycles', () => {
    assert.ok(r.maxBusStuck < 2 * MAX_CYCLE, `longest bus stand ${r.maxBusStuck.toFixed(1)} s`);
  });
});
