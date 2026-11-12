// 단순 교통(신호·차로 변경 없음): 차로 중심선을 따라 달리고, 앞차와 거리를 지키고, 차로 끝에서는 이어지는 차로로 넘어간다.
// 경복궁의 교통 sim(traffic.js)은 정지선·신호·진출입 정보가 든 차로 데이터가 필요하다. 그런 데이터가 없는 지도(여의도)가 이것을 쓴다.
// 차로: scene.lanes = [{ pts: [[x, y, z], …], length, highway }] (m). 교량 구간은 pts 의 z 가 상판 높이다(차는 그 z 로 달린다).
// 결과는 traffic.js 와 같은 모양: { time, vehicles: [{ kind, color, len, wid, x, y, z, th, px, py, pz, pth, braking }], signals: [], step(dt) }
//
// 최소한의 교차로 양보(점유):
//   교차로 = 차로 끝점이 12 m 안에 모이고(높이 차 3 m 안) 서로 다른 차로가 3개 넘게 닿는 곳. 반경은 끝점 퍼짐 + 6 m.
//   교차로로 들어가는 차로의 끝 9 m 앞이 정지 자리다. 교차로 안에 나와 30~150° 엇갈리는 방향으로 지나는 차가 있으면 거기서 기다린다.
//   들어간 차는 교차로 중심에서 반경 밖으로 나가면 점유를 푼다. 4 초 넘게 기다린 차는 그냥 들어간다(서로 기다리다 멈추는 일이 없다).
// 앞차: 같은 차로의 앞차, 없으면 미리 고른 다음 차로(v.nx)의 맨 뒤 차까지 본다. 6 초 넘게 서 있던 차는 내다보기·양보 없이 움직인다(교착 없음).
// 수요: setDemand(f) — 0~1. 활동 대수 = 전체 × f. 넘치는 차는 지도 밖으로 나갈 때 쉬고, 모자라면 진입 차로에서 다시 들어온다.
import { cumLengths, pointAt, hash01 } from '../geom.js';

const VMAX = { trunk: 16, primary: 13, secondary: 11, tertiary: 9 };
// 차종 비율(도심): 승용 45 %, SUV 20 %, 택시 12 %, 승합 7 %, 화물 7 %, 버스 6 %(지도에 없는 차종은 빼고 다시 나눈다)
export const KIND_MIX = [['sedan', 0.45], ['suv', 0.2], ['taxi', 0.12], ['van', 0.07], ['truck', 0.07], ['bus', 0.06]];
// 시각별 수요(0~1): 밤 0.35, 출근 7~9:30 과 퇴근 17:30~20 에 1, 낮 0.76. 꺾은선(시, 값)
const DEMAND = [[0, 0.4], [4.5, 0.35], [6.5, 0.7], [7.5, 1], [9.3, 1], [10.2, 0.76], [16.8, 0.8], [17.6, 1], [19.8, 1], [21, 0.66], [23, 0.48], [24, 0.4]];
export const demandAt = (tod) => {
  const t = ((tod % 24) + 24) % 24;
  for (let i = 1; i < DEMAND.length; i++) if (t <= DEMAND[i][0]) { const [a, fa] = DEMAND[i - 1], [b, fb] = DEMAND[i]; return fa + (fb - fa) * (t - a) / (b - a); }
  return DEMAND[0][1];
};
const key = (p) => `${Math.round(p[0] * 2)},${Math.round(p[1] * 2)}`;   // 0.5 m 격자로 끝점을 맞춘다
const TAU = Math.PI * 2;

export function createSimpleTraffic(scene, { seed = 7, targetCount = 200, demand = 1 } = {}) {
  const lanes = scene.lanes.map((ln, i) => {
    const cum = cumLengths(ln.pts);
    return { i, pts: ln.pts, cum, L: cum[cum.length - 1], vmax: VMAX[String(ln.highway || '').replace(/_link$/, '')] || 9, a: key(ln.pts[0]), b: key(ln.pts[ln.pts.length - 1]), next: [], hasPrev: false, cars: [], box: null, endTh: 0 };
  }).filter((l) => l.L > 5);
  const starts = new Map();
  for (const l of lanes) { if (!starts.has(l.a)) starts.set(l.a, []); starts.get(l.a).push(l); }
  // 이어지는 차로: 내 끝점에서 시작하는 차로. 같은 길의 반대 방향(그 차로의 끝이 내 시작)은 뺀다(유턴 금지).
  for (const l of lanes) {
    l.next = (starts.get(l.b) || []).filter((n) => n !== l && n.b !== l.a);
    for (const n of l.next) n.hasPrev = true;
    const p = l.pts, q = p[p.length - 1], r = p[Math.max(0, p.length - 2)];
    l.endTh = Math.atan2(q[1] - r[1], q[0] - r[0]);
  }
  // ── 교차로(끝점 모임)
  const ends = [];
  for (const l of lanes) { const p0 = l.pts[0], p1 = l.pts[l.pts.length - 1]; ends.push({ l, x: p0[0], y: p0[1], z: p0[2] || 0, end: false }, { l, x: p1[0], y: p1[1], z: p1[2] || 0, end: true }); }
  const par = ends.map((_, i) => i), find = (i) => { while (par[i] !== i) i = par[i] = par[par[i]]; return i; };
  const eg = new Map(), EK = (x, y) => (Math.floor(x / 12) + 4096) * 8192 + Math.floor(y / 12) + 4096;
  ends.forEach((e, i) => { const k = EK(e.x, e.y); let a = eg.get(k); if (!a) eg.set(k, a = []); a.push(i); });
  ends.forEach((e, i) => {
    const kx = Math.floor(e.x / 12), ky = Math.floor(e.y / 12);
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) for (const j of eg.get((kx + dx + 4096) * 8192 + ky + dy + 4096) || []) {
      if (j <= i) continue;
      const f = ends[j];
      if (Math.hypot(e.x - f.x, e.y - f.y) < 12 && Math.abs(e.z - f.z) < 3) par[find(i)] = find(j);
    }
  });
  const groups = new Map();
  ends.forEach((e, i) => { const r = find(i); let g = groups.get(r); if (!g) groups.set(r, g = []); g.push(e); });
  const boxes = [];
  for (const g of groups.values()) {
    const ls = new Set(g.map((e) => e.l));
    if (ls.size < 4) continue;   // 두 길이 이어지기만 하는 곳(차로 2 + 반대 2 = 4 미만)은 교차로가 아니다
    let x = 0, y = 0; for (const e of g) { x += e.x; y += e.y; } x /= g.length; y /= g.length;
    let r = 0; for (const e of g) r = Math.max(r, Math.hypot(e.x - x, e.y - y));
    const box = { id: boxes.length, x, y, r: r + 6, occ: [] };
    boxes.push(box);
    for (const e of g) if (e.end) e.l.box = box;
  }
  // 새로 나타나는 자리: 앞에 이어진 차로가 없는 차로(대개 지도 가장자리 밖에서 시작한다)
  const sources = lanes.filter((l) => !l.hasPrev);
  const pool = sources.length ? sources : lanes;
  const combos = [...new Set(scene.vehicle_atlas.frames.map((f) => f.kind + '|' + f.color))];
  const byKind = new Map();
  for (const c of combos) { const k = c.split('|')[0]; if (!byKind.has(k)) byKind.set(k, []); byKind.get(k).push(c); }
  const mix = KIND_MIX.filter(([k]) => byKind.has(k));
  const mixT = mix.reduce((a, [, p]) => a + p, 0);
  let rn = seed * 7919;
  const rnd = () => hash01(rn++);
  const total = lanes.reduce((s, l) => s + l.L, 0);
  const all = [], vehicles = [], dormant = [];
  const P = [0, 0, 0], Q = [0, 0, 0];
  const place = (v) => {
    const l = v.lane;
    pointAt(l.pts, l.cum, v.s, P); pointAt(l.pts, l.cum, Math.min(l.L, v.s + 2), Q);
    v.x = P[0]; v.y = P[1]; v.z = P[2];
    if (Math.hypot(Q[0] - P[0], Q[1] - P[1]) > 0.05) v.th = Math.atan2(Q[1] - P[1], Q[0] - P[0]);
  };
  const snap = (v) => { v.px = v.x; v.py = v.y; v.pz = v.z; v.pth = v.th; };
  const pickCombo = () => {
    let u = rnd() * mixT;
    for (const [k, p] of mix) { if ((u -= p) < 0) { const l = byKind.get(k); return l[Math.floor(rnd() * l.length)]; } }
    return combos[0];
  };
  const pickNext = (v, l) => (l.next.length ? l.next[Math.floor(hash01(v.id * 131 + v.hops * 17 + 5) * l.next.length)] : null);
  const enter = (v, l, s) => { v.lane = l; v.s = s; v.hops++; v.nx = pickNext(v, l); v.wait = 0; l.cars.push(v); };
  const make = (l, s) => {
    const [kind, color] = pickCombo().split('|');
    const sp = scene.vehicle_specs[kind];
    const v = { id: all.length, kind, color, len: sp[0], wid: sp[1], h: sp[2], lane: l, s, v: l.vmax * 0.8, k: kind === 'bus' || kind === 'truck' ? 0.75 + 0.15 * rnd() : 0.85 + 0.3 * rnd(), x: 0, y: 0, z: 0, th: 0, px: 0, py: 0, pz: 0, pth: 0, braking: false, hops: 0, nx: null, wait: 0, inBox: null, at: -1, stall: 0 };
    enter(v, l, s);
    place(v); snap(v);
    all.push(v); vehicles.push(v);
    return v;
  };
  // 처음 배치: 길이에 비례해 고르게
  for (const l of lanes) {
    const n = Math.floor(l.L / total * targetCount + rnd());
    for (let k = 0; k < n; k++) make(l, (k + 0.2 + 0.6 * rnd()) / n * l.L);
  }
  // 처음 수요만큼만 남기고 나머지는 쉰다(골고루: 번호 해시로)
  const sleep = (v) => { const i = vehicles.indexOf(v); if (i >= 0) vehicles.splice(i, 1); const li = v.lane.cars.indexOf(v); if (li >= 0) v.lane.cars.splice(li, 1); leaveBox(v); dormant.push(v); };
  let want = Math.round(all.length * Math.max(0, Math.min(1, demand)));
  for (const v of [...all].sort((a, b) => hash01(a.id * 37 + 11) - hash01(b.id * 37 + 11))) if (vehicles.length > want) sleep(v);
  const respawn = (v) => {
    // 진입 차로의 맨 앞이 비어 있을 때만 들어온다
    for (let k = 0; k < 4; k++) {
      const l = pool[Math.floor(rnd() * pool.length)];
      if (l.cars.every((c) => c.s > 14)) { enter(v, l, 0); v.v = l.vmax * 0.7; place(v); snap(v); return true; }
    }
    return false;
  };
  function leaveBox(v) { if (v.inBox) { const o = v.inBox.occ, i = o.indexOf(v); if (i >= 0) o.splice(i, 1); v.inBox = null; } }
  const crossing = (a, b) => { let d = Math.abs(a - b) % TAU; if (d > Math.PI) d = TAU - d; return d > Math.PI / 6 && d < Math.PI * 5 / 6; };
  const stats = { yields: 0, forced: 0, respawned: 0, slept: 0 };
  return {
    time: 0, vehicles, signals: [], lanes, boxes, stats, all,
    get active() { return vehicles.length; },
    // 수요(0~1): 출퇴근 1, 낮 0.75, 밤 0.35 처럼 main.js 가 시각으로 정한다
    setDemand(f) { want = Math.round(all.length * Math.max(0, Math.min(1, f))); },
    step(dt) {
      this.time += dt;
      // 점유 정리: 반경 밖으로 나간 차
      for (const b of boxes) for (let i = b.occ.length - 1; i >= 0; i--) { const v = b.occ[i]; if (Math.hypot(v.x - b.x, v.y - b.y) > b.r + 1) { b.occ.splice(i, 1); v.inBox = null; } }
      for (const l of lanes) {
        if (!l.cars.length) continue;
        l.cars.sort((a, b) => b.s - a.s);   // 앞차부터
        for (let i = 0; i < l.cars.length; i++) {
          const v = l.cars[i], lead = i > 0 ? l.cars[i - 1] : null;
          if (v.at === this.time) continue;   // 이번 걸음에 앞 차로에서 넘어온 차는 이미 움직였다
          v.at = this.time;
          snap(v);
          let wantV = l.vmax * v.k;
          if (lead) {
            const gap = lead.s - v.s - (lead.len + v.len) / 2;
            wantV = Math.min(wantV, Math.max(0, (gap - 2.5) / 1.4));
          } else if (v.nx && v.nx.cars.length && v.stall < 6) {
            // 다음 차로의 맨 뒤 차
            let back = null; for (const c of v.nx.cars) if (!back || c.s < back.s) back = c;
            const gap = l.L - v.s + back.s - (back.len + v.len) / 2;
            if (gap < 40) wantV = Math.min(wantV, Math.max(0, (gap - 2.5) / 1.4));
          }
          // 교차로 앞에서 양보
          const box = l.box;
          if (box && !v.inBox && v.stall < 6) {
            const toStop = l.L - 9 - v.s;
            if (toStop < 14 && toStop > -9) {
              let blocked = false;
              for (const o of box.occ) if (o !== v && crossing(o.th, l.endTh)) { blocked = true; break; }
              if (blocked && v.wait < 4) {
                v.wait += dt;
                if (toStop > 0) wantV = Math.min(wantV, Math.max(0, (toStop - 0.5) / 1.2));
                else wantV = 0;
                if (v.wait <= dt) stats.yields++;
              } else if (toStop < 1.5) {
                if (blocked) stats.forced++;
                v.inBox = box; box.occ.push(v); v.wait = 0;
              }
            }
          }
          const acc = Math.max(-6, Math.min(2.2, (wantV - v.v) / 0.6));
          v.braking = acc < -1.2;
          v.v = Math.max(0, v.v + acc * dt);
          v.s += v.v * dt;
          v.stall = v.v < 0.2 ? v.stall + dt : v.v > 1.5 ? 0 : v.stall;   // 6 초 넘게 서 있으면 내다보기·양보를 건너뛴다(순환 대기 끊기)
        }
        // 차로 끝을 넘은 차를 다음 차로로
        for (let i = l.cars.length - 1; i >= 0; i--) {
          const v = l.cars[i];
          if (v.s <= l.L) continue;
          const nx = v.nx;
          l.cars.splice(i, 1);
          if (nx) enter(v, nx, v.s - l.L);
          else if (vehicles.length > want) { sleep(v); stats.slept++; }
          else if (!respawn(v)) { v.s = l.L; v.v = 0; l.cars.push(v); }
        }
      }
      // 모자라면 쉬던 차를 진입 차로로(한 걸음에 몇 대씩)
      for (let k = 0; k < 6 && vehicles.length < want && dormant.length; k++) {
        const v = dormant[dormant.length - 1];
        if (!respawn(v)) break;
        dormant.pop(); vehicles.push(v); stats.respawned++;
      }
      for (const v of vehicles) place(v);
    },
  };
}
