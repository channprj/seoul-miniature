// 단순 교통(신호·차로 변경 없음): 차로 중심선을 따라 달리고, 같은 차로의 앞차와 거리를 지키고, 차로 끝에서는 이어지는 차로로 넘어간다.
// 경복궁의 교통 sim(traffic.js)은 정지선·신호·진출입 정보가 든 차로 데이터가 필요하다. 그런 데이터가 없는 지도(여의도 1판)가 이것을 쓴다.
// 한계: 교차로에서 서로 양보하지 않는다(다른 차로의 차와 겹쳐 지나갈 수 있다). 차로를 넘어갈 때 앞차 확인은 넘어간 뒤부터 한다.
// 차로: scene.lanes = [{ pts: [[x, y, z], …], length, highway }] (m). 교량 구간은 pts 의 z 가 상판 높이다.
// 결과는 traffic.js 와 같은 모양: { time, vehicles: [{ kind, color, len, wid, x, y, z, th, px, py, pz, pth, braking }], signals: [], step(dt) }
import { cumLengths, pointAt, hash01 } from '../geom.js';

const VMAX = { trunk: 16, primary: 13, secondary: 11, tertiary: 9 };
const key = (p) => `${Math.round(p[0] * 2)},${Math.round(p[1] * 2)}`;   // 0.5 m 격자로 끝점을 맞춘다

export function createSimpleTraffic(scene, { seed = 7, targetCount = 200 } = {}) {
  const lanes = scene.lanes.map((ln, i) => {
    const cum = cumLengths(ln.pts);
    return { i, pts: ln.pts, cum, L: cum[cum.length - 1], vmax: VMAX[String(ln.highway || '').replace(/_link$/, '')] || 9, a: key(ln.pts[0]), b: key(ln.pts[ln.pts.length - 1]), next: [], hasPrev: false, cars: [] };
  }).filter((l) => l.L > 5);
  const starts = new Map();
  for (const l of lanes) { if (!starts.has(l.a)) starts.set(l.a, []); starts.get(l.a).push(l); }
  // 이어지는 차로: 내 끝점에서 시작하는 차로. 같은 길의 반대 방향(그 차로의 끝이 내 시작)은 뺀다(유턴 금지).
  for (const l of lanes) {
    l.next = (starts.get(l.b) || []).filter((n) => n !== l && n.b !== l.a);
    for (const n of l.next) n.hasPrev = true;
  }
  // 새로 나타나는 자리: 앞에 이어진 차로가 없는 차로(대개 지도 가장자리 밖에서 시작한다)
  const sources = lanes.filter((l) => !l.hasPrev);
  const pool = sources.length ? sources : lanes;
  const combos = [...new Set(scene.vehicle_atlas.frames.map((f) => f.kind + '|' + f.color))];
  let rn = seed * 7919;
  const rnd = () => hash01(rn++);
  const total = lanes.reduce((s, l) => s + l.L, 0);
  const vehicles = [];
  const P = [0, 0, 0], Q = [0, 0, 0];
  const place = (v) => {
    const l = v.lane;
    pointAt(l.pts, l.cum, v.s, P); pointAt(l.pts, l.cum, Math.min(l.L, v.s + 2), Q);
    v.x = P[0]; v.y = P[1]; v.z = P[2];
    if (Math.hypot(Q[0] - P[0], Q[1] - P[1]) > 0.05) v.th = Math.atan2(Q[1] - P[1], Q[0] - P[0]);
  };
  const snap = (v) => { v.px = v.x; v.py = v.y; v.pz = v.z; v.pth = v.th; };
  const pickCombo = () => {
    // 버스는 드물게(전체의 7 % 안팎)
    for (let k = 0; k < 6; k++) {
      const c = combos[Math.floor(rnd() * combos.length)];
      if (!c.startsWith('bus|') || rnd() < 0.3) return c;
    }
    return combos[0];
  };
  const make = (l, s) => {
    const [kind, color] = pickCombo().split('|');
    const sp = scene.vehicle_specs[kind];
    const v = { id: vehicles.length, kind, color, len: sp[0], wid: sp[1], h: sp[2], lane: l, s, v: l.vmax * 0.8, k: 0.85 + 0.3 * rnd(), x: 0, y: 0, z: 0, th: 0, px: 0, py: 0, pz: 0, pth: 0, braking: false };
    place(v); snap(v);
    l.cars.push(v); vehicles.push(v);
    return v;
  };
  // 처음 배치: 길이에 비례해 고르게
  for (const l of lanes) {
    const n = Math.floor(l.L / total * targetCount + rnd());
    for (let k = 0; k < n; k++) make(l, (k + 0.2 + 0.6 * rnd()) / n * l.L);
  }
  const respawn = (v) => {
    // 진입 차로의 맨 앞이 비어 있을 때만 들어온다. 없으면 이번에는 차로 끝에 서서 기다린다.
    for (let k = 0; k < 4; k++) {
      const l = pool[Math.floor(rnd() * pool.length)];
      if (l.cars.every((c) => c.s > 14)) { v.lane = l; v.s = 0; l.cars.push(v); place(v); snap(v); return true; }
    }
    return false;
  };
  return {
    time: 0, vehicles, signals: [], lanes,
    step(dt) {
      this.time += dt;
      for (const l of lanes) {
        if (!l.cars.length) continue;
        l.cars.sort((a, b) => b.s - a.s);   // 앞차부터
        for (let i = 0; i < l.cars.length; i++) {
          const v = l.cars[i], lead = i > 0 ? l.cars[i - 1] : null;
          if (v.at === this.time) continue;   // 이번 걸음에 앞 차로에서 넘어온 차는 이미 움직였다
          v.at = this.time;
          snap(v);
          let want = l.vmax * v.k;
          if (lead) {
            const gap = lead.s - v.s - (lead.len + v.len) / 2;
            want = Math.min(want, Math.max(0, (gap - 2.5) / 1.4));
          }
          const acc = Math.max(-6, Math.min(2.2, (want - v.v) / 0.6));
          v.braking = acc < -1.2;
          v.v = Math.max(0, v.v + acc * dt);
          v.s += v.v * dt;
        }
        // 차로 끝을 넘은 차를 다음 차로로
        for (let i = l.cars.length - 1; i >= 0; i--) {
          const v = l.cars[i];
          if (v.s <= l.L) continue;
          const nx = l.next.length ? l.next[Math.floor(hash01(v.id * 131 + Math.floor(this.time * 3)) * l.next.length)] : null;
          if (nx) { l.cars.splice(i, 1); v.s -= l.L; v.lane = nx; nx.cars.push(v); }
          else { l.cars.splice(i, 1); if (!respawn(v)) { v.s = l.L; v.v = 0; l.cars.push(v); } }
        }
      }
      for (const v of vehicles) place(v);
    },
  };
}
