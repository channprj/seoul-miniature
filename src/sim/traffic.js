// Live traffic simulation for the iso-seoul-map web app.
// Pure ES module: no DOM, no Node APIs, no Math.random. Deterministic for a given seed.
//
// Model summary
// - Scene lanes are polylines in local metres with no explicit topology. The lane graph is
//   inferred from endpoint proximity: "direct" links (end ~ start, aligned) and synthetic
//   Bezier "connectors" (lane drops, lane changes at lane ends, turns, merges into the middle
//   of another lane).
// - Vehicles follow a pre-drawn route (random walk to a sink) and are positioned by a
//   single route distance r (centre of body).
// - Longitudinal control: IDM against the leader found along the route (including vehicles
//   whose rear still hangs over a previous segment), signal stop lines and conflict-zone
//   entry points. A hard position clamp guarantees no same-path overlap.
// - Conflict zones: for every pair of segments whose centre lines come within ZONE_D metres
//   (excluding a lane and its direct successor) a mutual-exclusion zone with one s-interval
//   per side. A vehicle must claim (atomically, for a chain of closely spaced zones) before
//   its body enters an interval and releases it when its rear has left. Fairness: the side
//   that has waited longest goes first. Vehicles holding both sides (merging) do not block.
// - Signals: fixed-time controllers at hand-picked junctions, approach stop lines found
//   automatically from lane ends near the junction.

const TAU = Math.PI * 2;
const ZONE_D = 3.0; // centre-line distance that counts as a conflict (max width 2.5 + margin)
const PAR_COS = Math.cos((20 * Math.PI) / 180);
const SAMPLE = 0.5;
const ORDER_MAX_ANGLE = (20 * Math.PI) / 180; // gentler merges/diverges use ordering, not locks
const ORDER_LOOK = 45; // sampling step for zone detection, m
const CONN_MAX_LATERAL = 30; // max distance from a lane end to the lane it connects into
const DIRECT_EPS = 0.8; // end->start distance that counts as the same lane continuing
const LOOKAHEAD_MAX = 120;

const HW_SPEED = {
  primary: 12.5,
  primary_link: 7,
  secondary: 10,
  secondary_link: 6.5,
  tertiary: 8,
  tertiary_link: 6,
};

const SPEC_FALLBACK = {
  sedan: [4.7, 1.85, 1.45],
  suv: [4.8, 1.95, 1.75],
  taxi: [4.7, 1.8, 1.5],
  bus: [11, 2.5, 3.2],
  van: [5.2, 1.95, 2.0],
};

// replay mix: sedan 178, suv 69, taxi 61, van 43, bus 12 (of 363)
const KIND_WEIGHTS = [
  ['sedan', 178],
  ['suv', 69],
  ['taxi', 61],
  ['van', 43],
];
const BUS_SHARE_ON_BUS_ROUTES = 0.25;
// 긴 차(버스)의 축간 거리 = len·2·AXLE. 앞뒤 축이 경로 위에 있고 차체는 두 축을 잇는 선 위:
// 굽은 길에서 끝단은 바깥, 가운데는 안쪽으로 벗어난다. len/√2 이면 양쪽 최대 이탈이 비슷해진다
// (중심을 경로에 둘 때의 약 1.0 m -> 0.6 m).
const AXLE = 1 / (2 * Math.SQRT2);
const CAR_COLORS = ['#f4f4f0', '#f4f4f0', '#f4f4f0', '#22252b', '#22252b', '#a7aeb6', '#a7aeb6', '#646b74', '#1f4f9a', '#c8312b', '#2a8c86', '#e9e2cf'];

// Signalised junctions (local metres). Approaches are found automatically.
const JUNCTIONS = [
  { name: 'gwanghwamun', x: 36, y: -58, r: 42 },
  { name: 'dongsipjagak', x: 262, y: 12, r: 42 },
  { name: 'hyoja', x: -215, y: 0, r: 32 },
];

function mulberry32(seed) {
  let a = seed >>> 0;
  return function rand() {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function angDiff(a, b) {
  let d = (a - b) % TAU;
  if (d > Math.PI) d -= TAU;
  if (d < -Math.PI) d += TAU;
  return d;
}

// ---------------------------------------------------------------- polyline segments

function makeSeg(X, Y, Z) {
  const n = X.length;
  const cum = new Float64Array(n);
  for (let i = 1; i < n; i++) cum[i] = cum[i - 1] + Math.hypot(X[i] - X[i - 1], Y[i] - Y[i - 1]);
  return { X, Y, Z, cum, len: cum[n - 1] };
}

// position on a segment at arc length s (linear extrapolation outside [0, len])
function segPos(seg, s, out) {
  const { X, Y, Z, cum } = seg;
  const n = X.length;
  if (s <= 0) {
    const L = cum[1] - cum[0] || 1;
    out[0] = X[0] + ((X[1] - X[0]) * s) / L;
    out[1] = Y[0] + ((Y[1] - Y[0]) * s) / L;
    out[2] = Z[0];
    return out;
  }
  if (s >= seg.len) {
    const L = cum[n - 1] - cum[n - 2] || 1;
    const e = s - seg.len;
    out[0] = X[n - 1] + ((X[n - 1] - X[n - 2]) * e) / L;
    out[1] = Y[n - 1] + ((Y[n - 1] - Y[n - 2]) * e) / L;
    out[2] = Z[n - 1];
    return out;
  }
  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const m = (lo + hi) >> 1;
    if (cum[m] <= s) lo = m;
    else hi = m;
  }
  const L = cum[hi] - cum[lo];
  const t = L > 0 ? (s - cum[lo]) / L : 0;
  out[0] = X[lo] + (X[hi] - X[lo]) * t;
  out[1] = Y[lo] + (Y[hi] - Y[lo]) * t;
  out[2] = Z[lo] + (Z[hi] - Z[lo]) * t;
  return out;
}

const _p0 = [0, 0, 0];
const _p1 = [0, 0, 0];
function segHeading(seg, s) {
  segPos(seg, Math.max(0, s - 1.5), _p0);
  segPos(seg, Math.min(seg.len, s + 1.5), _p1);
  return Math.atan2(_p1[1] - _p0[1], _p1[0] - _p0[0]);
}

// nearest point on segment to (x, y): returns [s, dist]
function segNearest(seg, x, y) {
  const { X, Y, cum } = seg;
  let best = Infinity;
  let bestS = 0;
  for (let i = 1; i < X.length; i++) {
    const dx = X[i] - X[i - 1];
    const dy = Y[i] - Y[i - 1];
    const L2 = dx * dx + dy * dy;
    let t = L2 > 0 ? ((x - X[i - 1]) * dx + (y - Y[i - 1]) * dy) / L2 : 0;
    t = t < 0 ? 0 : t > 1 ? 1 : t;
    const px = X[i - 1] + dx * t;
    const py = Y[i - 1] + dy * t;
    const d = Math.hypot(x - px, y - py);
    if (d < best) {
      best = d;
      bestS = cum[i - 1] + (cum[i] - cum[i - 1]) * t;
    }
  }
  return [bestS, best];
}

function bezierSeg(P, u, Q, w, z0, z1) {
  const D = Math.hypot(Q[0] - P[0], Q[1] - P[1]);
  const k = D * 0.4;
  const c1x = P[0] + Math.cos(u) * k;
  const c1y = P[1] + Math.sin(u) * k;
  const c2x = Q[0] - Math.cos(w) * k;
  const c2y = Q[1] - Math.sin(w) * k;
  const n = Math.max(4, Math.ceil(D / 0.5));
  const X = new Float64Array(n + 1);
  const Y = new Float64Array(n + 1);
  const Z = new Float64Array(n + 1);
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const a = (1 - t) * (1 - t) * (1 - t);
    const b = 3 * (1 - t) * (1 - t) * t;
    const c = 3 * (1 - t) * t * t;
    const d = t * t * t;
    X[i] = a * P[0] + b * c1x + c * c2x + d * Q[0];
    Y[i] = a * P[1] + b * c1y + c * c2y + d * Q[1];
    Z[i] = z0 + (z1 - z0) * t;
  }
  return makeSeg(X, Y, Z);
}

// ---------------------------------------------------------------- graph

function buildGraph(scene) {
  const lanes = scene.lanes;
  const fr = scene.bounds?.fit_rect_local_xy ?? [-1e9, -1e9, 1e9, 1e9];
  const inMap = (x, y) => x >= fr[0] && x <= fr[2] && y >= fr[1] && y <= fr[3];
  // on the background canvas (the map picture is wider than fit_rect: its beige border and the
  // lane ends there are drawn too). Without a camera, fall back to the map rectangle.
  const cam = scene.camera;
  const SCREEN_PAD = 40; // px
  const onScreen = cam?.res && cam.screen_x_axis && cam.screen_y_axis
    ? (x, y, z) => {
        const ex = cam.screen_x_axis;
        const ey = cam.screen_y_axis;
        const m = cam.m_per_px_screen;
        const px = (x * ex[0] + y * ex[1] + z * ex[2] - cam.cx) / m + cam.res[0] / 2;
        const py = cam.res[1] / 2 - (x * ey[0] + y * ey[1] + z * ey[2] - cam.cy) / m;
        return px >= -SCREEN_PAD && px <= cam.res[0] + SCREEN_PAD && py >= -SCREEN_PAD && py <= cam.res[1] + SCREEN_PAD;
      }
    : (x, y) => inMap(x, y);
  const segs = [];
  const skipped = [];
  const laneSeg = new Int32Array(lanes.length).fill(-1);

  lanes.forEach((L, li) => {
    const P = L.pts;
    const X = Float64Array.from(P, (p) => p[0]);
    const Y = Float64Array.from(P, (p) => p[1]);
    const Z = Float64Array.from(P, (p) => p[2] ?? 0);
    const g = makeSeg(X, Y, Z);
    const chord = Math.hypot(X[X.length - 1] - X[0], Y[Y.length - 1] - Y[0]);
    if (P.length < 2 || g.len < 5 || chord < 5) {
      skipped.push({ id: L.id, reason: `degenerate (len ${g.len.toFixed(1)} m, start-end ${chord.toFixed(1)} m)` });
      return;
    }
    Object.assign(g, {
      idx: segs.length,
      lane: li,
      id: L.id,
      conn: false,
      hw: L.highway || 'tertiary',
      next: [],
      prev: [],
      zl: [],
      stops: [],
    });
    laneSeg[li] = g.idx;
    segs.push(g);
  });

  const real = segs.slice();
  const tmp = [0, 0, 0];

  const stopS = (L, g) => (L.stopline && L.b > 5 && L.b < g.len - 1.5 ? L.b : g.len);
  for (const A of real) {
    const LA = lanes[A.lane];
    const n = A.X.length;
    A.stopS = stopS(LA, A);
    A.a = Math.max(0, Math.min(LA.a ?? 0, A.len));
  }
  for (const A of real) {
    const n = A.X.length;
    const Pe = [A.X[n - 1], A.Y[n - 1]];
    const ue = segHeading(A, A.len);
    for (const B of real) {
      if (B === A) continue;
      const w0 = segHeading(B, 0);
      if (Math.hypot(B.X[0] - Pe[0], B.Y[0] - Pe[1]) < DIRECT_EPS && Math.abs(angDiff(ue, w0)) < (40 * Math.PI) / 180) {
        A.next.push({ seg: B.idx, entry: 0, exit: A.len, w: 1 });
        B.prev.push(A.idx);
      }
    }
  }
  const recs = [];
  for (const A of real) {
    const hasDirect = A.next.length > 0;
    const hasStop = A.stopS < A.len;
    // origins: the lane end (continuations, and turns when there is no stop line) and the stop
    // line (turns only: the part of the lane after it is the junction box)
    const origins = [{ s: A.len, cont: !hasDirect, turns: !hasStop }];
    if (hasStop) origins.push({ s: A.stopS, cont: false, turns: true });
    for (const O of origins) {
      segPos(A, O.s, tmp);
      const P = [tmp[0], tmp[1]];
      const z0 = tmp[2];
      const u = segHeading(A, O.s);
      const cands = [];
      for (const B of real) {
        if (B === A || A.next.some((nx) => nx.seg === B.idx)) continue;
        const [sn, e] = segNearest(B, P[0], P[1]);
        if (e > CONN_MAX_LATERAL) continue;
        const tn = segHeading(B, sn);
        segPos(B, sn, tmp);
        const vx = P[0] - tmp[0];
        const vy = P[1] - tmp[1];
        const lat = Math.abs(-Math.sin(tn) * vx + Math.cos(tn) * vy);
        const lon = Math.cos(tn) * vx + Math.sin(tn) * vy; // >0: P is past B(sn)
        const phi = Math.abs(angDiff(tn, u));
        if (phi > (120 * Math.PI) / 180) continue;
        const isTurn = phi >= (30 * Math.PI) / 180;
        if (isTurn ? !O.turns : !O.cont || lat > 4.5) continue;
        const f = 4 - 3 * Math.min(1, phi / (Math.PI / 2));
        const st = sn + Math.max(5, lat * f + Math.min(0, lon));
        if (st > B.stopS - 3) continue; // never enter a lane inside its junction box
        segPos(B, st, tmp);
        const Q = [tmp[0], tmp[1]];
        const w = segHeading(B, st);
        const dx = Q[0] - P[0];
        const dy = Q[1] - P[1];
        const D = Math.hypot(dx, dy);
        if (D < 3 || D > 45) continue;
        if ((Math.cos(u) * dx + Math.sin(u) * dy) / D < 0.15) continue; // target must be ahead
        if ((Math.cos(w) * dx + Math.sin(w) * dy) / D < 0.15) continue; // and approached along B
        const turn = Math.abs(angDiff(w, u));
        if (turn > (120 * Math.PI) / 180) continue;
        if (turn > Math.PI / 4 && D < 8) continue; // too tight for a turn
        cands.push({ B, st, Q, w, e, lat, turn, sgn: Math.sign(angDiff(w, u)), isTurn: turn >= (30 * Math.PI) / 180, z1: tmp[2] });
      }
      cands.sort((p, q) => p.e - q.e || p.B.idx - q.B.idx);
      recs.push({ A, O, P, z0, u, cands, hasDirect });
    }
  }

  // Turn lane discipline: a multi-lane approach turning into a multi-lane road maps lanes in
  // order from the turning side (rightmost -> rightmost for right turns), instead of every
  // lane fanning out to every target lane (which would make all turn paths cross).
  const cross = (h, dx, dy) => Math.cos(h) * dy - Math.sin(h) * dx;
  for (const R of recs) {
    R.groups = [];
    for (const c of R.cands) {
      if (!c.isTurn) continue;
      let g = R.groups.find((G) => G.sgn === c.sgn && Math.abs(angDiff(c.w, G.w)) < (25 * Math.PI) / 180 && Math.hypot(c.Q[0] - G.Q[0], c.Q[1] - G.Q[1]) < 15);
      if (!g) {
        g = { sgn: c.sgn, w: c.w, Q: c.Q, members: [], key: '' };
        R.groups.push(g);
      }
      g.members.push(c);
    }
    for (const g of R.groups) {
      // order targets from the turning side
      const key = (c) => cross(g.w, c.Q[0] - g.Q[0], c.Q[1] - g.Q[1]);
      g.members.sort((p, q) => (g.sgn < 0 ? key(p) - key(q) : key(q) - key(p)) || p.B.idx - q.B.idx);
      g.key = `${lanes[g.members[0].B.lane].name ?? ''}|${Math.round(((g.w + TAU) % TAU) / (Math.PI / 6))}|${g.sgn}`;
      g.keep = null;
    }
  }
  const byKey = new Map();
  for (const R of recs) for (const g of R.groups) {
    if (!byKey.has(g.key)) byKey.set(g.key, []);
    byKey.get(g.key).push({ R, g });
  }
  for (const [, list] of byKey) {
    const done = new Set();
    for (const it of list) {
      if (done.has(it)) continue;
      // approach = same key, similar heading, nearby origin
      const appr = list.filter((o) => !done.has(o) && Math.abs(angDiff(o.R.u, it.R.u)) < (25 * Math.PI) / 180 && Math.hypot(o.R.P[0] - it.R.P[0], o.R.P[1] - it.R.P[1]) < 30);
      const sgn = it.g.sgn;
      const key = (o) => cross(it.R.u, o.R.P[0] - it.R.P[0], o.R.P[1] - it.R.P[1]);
      appr.sort((p, q) => (sgn < 0 ? key(p) - key(q) : key(q) - key(p)) || p.R.A.idx - q.R.A.idx);
      appr.forEach((o, rank) => {
        done.add(o);
        if (rank < o.g.members.length) o.g.keep = o.g.members[rank];
      });
    }
  }

  for (const R of recs) {
    const { A, O, P, z0, u } = R;
    const keep = R.cands.filter((c) => !c.isTurn).slice(0, 3);
    for (const g of R.groups) if (g.keep) keep.push(g.keep);
    keep.sort((p, q) => p.e - q.e || p.B.idx - q.B.idx);
    for (const c of keep) {
      const C = bezierSeg(P, u, c.Q, c.w, z0, c.z1);
      Object.assign(C, {
        idx: segs.length,
        lane: c.B.lane,
        id: `${A.id}>${c.B.id}`,
        conn: true,
        from: A.idx,
        fromExit: O.s,
        to: c.B.idx,
        toEntry: c.st,
        hw: A.hw.endsWith('_link') ? A.hw : c.B.hw,
        next: [],
        prev: [A.idx],
        zl: [],
        stops: [],
        a: 0,
      });
      C.stopS = C.len;
      C.next.push({ seg: c.B.idx, entry: c.st, exit: C.len, w: 1 });
      segs.push(C);
      A.next.push({ seg: C.idx, entry: 0, exit: O.s, w: R.hasDirect ? 0.6 : 1 });
      c.B.prev.push(C.idx);
    }
  }

  // lanes that begin beside another lane's end (a lane is added) get a continuation connector
  for (const B of real) {
    if (segs.some((h) => h.next.some((nx) => nx.seg === B.idx && nx.entry < 15))) continue;
    const w0 = segHeading(B, 0);
    let best = null;
    for (const A of real) {
      if (A === B || A.next.some((nx) => nx.seg === B.idx || (segs[nx.seg].conn && segs[nx.seg].to === B.idx))) continue;
      const n = A.X.length;
      const d = Math.hypot(B.X[0] - A.X[n - 1], B.Y[0] - A.Y[n - 1]);
      const ue = segHeading(A, A.len);
      if (d > 5 || Math.abs(angDiff(ue, w0)) > (30 * Math.PI) / 180) continue;
      if (!best || d < best.d) best = { A, d, ue };
    }
    if (!best) continue;
    const A = best.A;
    const n = A.X.length;
    const P = [A.X[n - 1], A.Y[n - 1]];
    const st = Math.min(B.stopS - 3, Math.max(5, best.d * 4));
    if (st < 3) continue;
    segPos(B, st, tmp);
    const Q = [tmp[0], tmp[1]];
    const w = segHeading(B, st);
    const C = bezierSeg(P, best.ue, Q, w, A.Z[n - 1], tmp[2]);
    Object.assign(C, {
      idx: segs.length,
      lane: B.lane,
      id: `${A.id}>${B.id}`,
      conn: true,
      from: A.idx,
      fromExit: A.len,
      to: B.idx,
      toEntry: st,
      hw: B.hw,
      next: [{ seg: B.idx, entry: st, exit: 0, w: 1 }],
      prev: [A.idx],
      zl: [],
      stops: [],
      a: 0,
    });
    C.next[0].exit = C.len;
    C.stopS = C.len;
    segs.push(C);
    A.next.push({ seg: C.idx, entry: 0, exit: A.len, w: 0.6 });
    B.prev.push(C.idx);
  }

  for (const g of segs) {
    // spawn points: lane starts nothing feeds. A lane fed only mid-way spawns only if it starts off-map
    const feeds = segs.filter((h) => h.next.some((nx) => nx.seg === g.idx)).map((h) => h.next.find((nx) => nx.seg === g.idx).entry);
    g.onMapStart = inMap(g.X[0], g.Y[0]);
    g.onMapEnd = inMap(g.X[g.X.length - 1], g.Y[g.Y.length - 1]);
    g.isSource = !g.conn && (feeds.length === 0 || (!g.onMapStart && Math.min(...feeds) >= 15));
    g.isSink = g.next.length === 0;
    g.baseV = HW_SPEED[g.hw] ?? 8;
    if (g.conn) g.baseV = Math.min(segs[g.from].baseV ?? HW_SPEED[segs[g.from].hw] ?? 8, HW_SPEED[g.hw] ?? 8);
  }
  return { segs, laneSeg, skipped, inMap, onScreen };
}

// curvature-limited speed caps, propagated backwards over successors
function buildSpeedCaps(segs) {
  const ALAT = 2.0;
  const BDEC = 1.4;
  for (const g of segs) {
    const n = Math.max(2, Math.ceil(g.len) + 1);
    const lim = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const s = Math.min(g.len, i);
      const h0 = segHeading(g, Math.max(0, s - 3));
      const h1 = segHeading(g, Math.min(g.len, s + 3));
      const span = Math.min(g.len, s + 3) - Math.max(0, s - 3);
      const k = Math.abs(angDiff(h1, h0)) / Math.max(1, span);
      const vc = k > 1e-4 ? Math.sqrt(ALAT / k) : 99;
      lim[i] = Math.min(g.baseV, vc);
    }
    g.lim = lim;
    g.vcap = Float32Array.from(lim);
  }
  for (const g of segs) {
    const n = g.vcap.length;
    for (let i = n - 2; i >= 0; i--) {
      const v = Math.sqrt(g.vcap[i + 1] * g.vcap[i + 1] + 2 * BDEC);
      if (v < g.vcap[i]) g.vcap[i] = v;
    }
  }
}

// ---------------------------------------------------------------- conflict zones

function nearS(B, A, sa) {
  const p = segPos(A, sa, [0, 0, 0]);
  return segNearest(B, p[0], p[1])[0];
}

// Merge / diverge detection. Returns [refA, refB]: arc length on each segment of the common
// point (merge point downstream, or split point upstream), or null for a crossing.
let SEGS = [];
function shareRef(A, B) {
  // merges
  if (A.conn && A.to === B.idx) return [A.len, A.toEntry];
  if (B.conn && B.to === A.idx) return [B.toEntry, B.len];
  // common downstream lane within two hops (lane -> connector -> lane)
  const reach = (g) => {
    const out = [];
    for (const nx of g.next) {
      out.push({ seg: nx.seg, entry: nx.entry, base: nx.exit });
      const h = SEGS[nx.seg];
      if (h.conn) for (const n2 of h.next) out.push({ seg: n2.seg, entry: n2.entry, base: nx.exit + h.len });
    }
    return out;
  };
  const ra = reach(A);
  const rb = reach(B);
  for (const x of ra) {
    for (const y of rb) {
      if (x.seg !== y.seg) continue;
      const M = Math.max(x.entry, y.entry);
      return [x.base + (M - x.entry), y.base + (M - y.entry)];
    }
  }
  // diverges
  if (A.conn && A.from === B.idx) return [0, A.fromExit];
  if (B.conn && B.from === A.idx) return [B.fromExit, 0];
  if (A.conn && B.conn && A.from === B.from && Math.abs(A.fromExit - B.fromExit) < 1) return [0, 0];
  const fromA = A.prevStart ?? [];
  const fromB = B.prevStart ?? [];
  if (fromA.some((x) => fromB.includes(x))) return [0, 0];
  return null;
}

function closestRef(A, B, a0, a1) {
  let best = Infinity;
  let ra = a0;
  let rb = 0;
  const p = [0, 0, 0];
  for (let sa = a0; sa <= a1 + 1e-9; sa += 0.25) {
    segPos(A, sa, p);
    const [sb, d] = segNearest(B, p[0], p[1]);
    if (d < best - 1e-6) {
      best = d;
      ra = sa;
      rb = sb;
    }
  }
  return [ra, rb];
}

function buildZones(segs) {
  SEGS = segs;
  // segments that begin exactly at another segment's end (direct links and end connectors)
  for (const g of segs) g.prevStart = [];
  for (const g of segs) for (const nx of g.next) if (nx.entry === 0 && nx.exit >= g.len - 1e-6) segs[nx.seg].prevStart.push(g.idx);
  for (const g of segs) {
    let ok = g.hw === 'primary' || g.hw === 'secondary';
    if (g.conn && Math.min(...g.vcap) < 4.5) ok = false;
    g.busOk = ok;
    g.maxW = ok ? 2.5 : 1.95;
  }
  // samples
  const cell = ZONE_D;
  const grid = new Map();
  const samp = segs.map((g) => {
    const n = Math.max(2, Math.ceil(g.len / SAMPLE) + 1);
    const xs = new Float64Array(n);
    const ys = new Float64Array(n);
    const ss = new Float64Array(n);
    const hs = new Float64Array(n);
    const p = [0, 0, 0];
    for (let i = 0; i < n; i++) {
      const s = (g.len * i) / (n - 1);
      segPos(g, s, p);
      xs[i] = p[0];
      ys[i] = p[1];
      ss[i] = s;
      hs[i] = segHeading(g, s);
      const key = Math.floor(p[0] / cell) * 100003 + Math.floor(p[1] / cell);
      let arr = grid.get(key);
      if (!arr) grid.set(key, (arr = []));
      arr.push(g.idx, i);
    }
    return { xs, ys, ss, hs };
  });

  // a lane and a successor that starts exactly at its end form one path: not a conflict
  const excluded = (a, b) => {
    const A = segs[a];
    const B = segs[b];
    if (A.next.some((n) => n.seg === b && n.entry === 0 && n.exit >= A.len - 1e-6)) return true;
    if (B.next.some((n) => n.seg === a && n.entry === 0 && n.exit >= B.len - 1e-6)) return true;
    return false;
  };

  // pair -> per A-sample matched B-sample ranges
  const pairs = new Map();
  for (const A of segs) {
    const { xs, ys } = samp[A.idx];
    for (let i = 0; i < xs.length; i++) {
      const cx = Math.floor(xs[i] / cell);
      const cy = Math.floor(ys[i] / cell);
      for (let gx = cx - 1; gx <= cx + 1; gx++) {
        for (let gy = cy - 1; gy <= cy + 1; gy++) {
          const arr = grid.get(gx * 100003 + gy);
          if (!arr) continue;
          for (let k = 0; k < arr.length; k += 2) {
            const b = arr[k];
            if (b <= A.idx) continue;
            const j = arr[k + 1];
            const sb = samp[b];
            const dd = Math.hypot(sb.xs[j] - xs[i], sb.ys[j] - ys[i]);
            if (dd >= ZONE_D) continue;
            // side by side (same or opposite direction): only real lateral overlap counts
            const wsum = (A.maxW + segs[b].maxW) / 2;
            if (Math.abs(Math.cos(sb.hs[j] - samp[A.idx].hs[i])) > PAR_COS) {
              if (dd >= wsum + 0.15) continue;
            } else if (dd >= wsum + 0.5) continue;
            const key = A.idx * 4096 + b;
            let rec = pairs.get(key);
            if (!rec) {
              if (excluded(A.idx, b)) {
                pairs.set(key, null);
                continue;
              }
              rec = { a: A.idx, b, hits: new Map() };
              pairs.set(key, rec);
            }
            if (rec === null) continue;
            const h = rec.hits.get(i);
            if (!h) rec.hits.set(i, [j, j]);
            else {
              if (j < h[0]) h[0] = j;
              if (j > h[1]) h[1] = j;
            }
          }
        }
      }
    }
  }

  const zones = [];
  const keys = [...pairs.keys()].sort((x, y) => x - y);
  for (const key of keys) {
    const rec = pairs.get(key);
    if (!rec) continue;
    zonesFromHits(segs, zones, rec, samp[rec.a].ss, samp[rec.b].ss, -1);
  }
  for (const g of segs) g.zl.sort((p, q) => p.s0 - q.s0 || p.zone - q.zone);
  return zones;
}

// rec.hits (A 표본 번호 -> B 표본 번호 범위) 를 구간으로 묶어 구역을 만든다.
// busSide >= 0: 버스 구역 (buildBusZones). 0 = side 0 만 버스 전용, 2 = 양쪽 버스 전용
// mate: 같은 차선 쌍의 기존 순서 구역. 버스 대 아무 차 구역이 합류·분류 쌍이면 그와 같은 기준점으로
// 순서를 매긴다 (잠금이면 끼어들기 줄에서 옆 차선이 비는 때가 없어 버스가 못 들어간다)
function zonesFromHits(segs, zones, rec, sa, sb, busSide, mate) {
  const idxs = [...rec.hits.keys()].sort((x, y) => x - y);
  // split into runs (gap tolerance 2 samples)
  let run = null;
  const runs = [];
  for (const i of idxs) {
    const h = rec.hits.get(i);
    if (run && i - run.i1 <= 3) {
      run.i1 = i;
      run.j0 = Math.min(run.j0, h[0]);
      run.j1 = Math.max(run.j1, h[1]);
    } else {
      run = { i0: i, i1: i, j0: h[0], j1: h[1] };
      runs.push(run);
    }
  }
  // merge runs whose B ranges overlap
  runs.sort((p, q) => p.j0 - q.j0);
  const merged = [];
  for (const r of runs) {
    const m = merged[merged.length - 1];
    if (m && r.j0 <= m.j1 + 3) {
      m.i0 = Math.min(m.i0, r.i0);
      m.i1 = Math.max(m.i1, r.i1);
      m.j1 = Math.max(m.j1, r.j1);
    } else merged.push({ ...r });
  }
  const A = segs[rec.a];
  const B = segs[rec.b];
  for (const r of merged) {
    let a0 = Math.max(0, sa[r.i0] - SAMPLE);
    let a1 = Math.min(A.len, sa[r.i1] + SAMPLE);
    let b0 = Math.max(0, sb[r.j0] - SAMPLE);
    let b1 = Math.min(B.len, sb[r.j1] + SAMPLE);
    // a connector merging into the middle of a lane: the lane side ends at the entry point
    // (순서를 따르는 버스 구역은 자르지 않는다: 합류 전 버스 앞머리가 합류점 너머 차로까지 휘두른다)
    if (!mate) {
      if (A.conn && A.to === B.idx) b1 = Math.min(b1, A.toEntry);
      if (B.conn && B.to === A.idx) a1 = Math.min(a1, B.toEntry);
      // a connector branching off mid-lane: the lane side starts at the branch point
      if (A.conn && A.from === B.idx) b0 = Math.max(b0, A.fromExit);
      if (B.conn && B.from === A.idx) a0 = Math.max(a0, B.fromExit);
    }
    if (a1 <= a0 || b1 <= b0) continue;
    const ha = segHeading(A, (a0 + a1) / 2);
    const hb = segHeading(B, (b0 + b1) / 2);
    const z = {
      id: zones.length,
      seg: [rec.a, rec.b],
      iv: [
        [a0, a1],
        [b0, b1],
      ],
      angle: Math.max(
        Math.abs(angDiff(ha, hb)),
        Math.abs(angDiff(segHeading(A, a0), segHeading(B, nearS(B, A, a0)))),
        Math.abs(angDiff(segHeading(A, a1), segHeading(B, nearS(B, A, a1)))),
      ),
      order: false,
      ref: [0, 0],
      part: [[], []],
      holders: [[], []],
      waitSince: [Infinity, Infinity],
      waitId: [0, 0],
      waitV: [null, null],
      waitStep: [-10, -10],
    };
    // Merges and diverges (paths that share a point) and near-parallel weaves: order vehicles
    // by distance to the common point instead of locking the whole zone. Real crossings and
    // opposing traffic keep the lock.
    // 그 밖의 버스 구역은 잠금: 순서는 앞뒤만 정하므로 뒤에 선 차 옆으로 버스 꼬리가 휘두르는 것을
    // 막지 못한다 (순서 구역엔 상자 막지 않기 규칙도 없다)
    if (busSide >= 0) {
      z.bus = true;
      z.busSide = busSide;
      z.armStep = -10;
    }
    const topo = busSide < 0 ? shareRef(A, B) : null;
    if (mate) {
      z.order = true;
      z.ref = mate.seg[0] === rec.a ? mate.ref.slice() : [mate.ref[1], mate.ref[0]];
    } else if (topo) {
      z.order = true;
      z.ref = topo;
    } else if (z.angle < ORDER_MAX_ANGLE && busSide < 0) {
      z.order = true;
      z.ref = closestRef(A, B, a0, a1);
    }
    // extra longitudinal clearance when the streams meet at an angle (body width matters)
    if (mate) z.extra = mate.extra;
    else z.extra = z.order ? Math.min(2.5, (Math.max(A.maxW, B.maxW) * Math.sin(Math.min(z.angle, Math.PI / 2))) / 1.2) : 0;
    zones.push(z);
    const bus = busSide >= 0;
    A.zl.push({ zone: z.id, side: 0, s0: a0, s1: a1, bus });
    B.zl.push({ zone: z.id, side: 1, s0: b0, s1: b1, bus });
  }
}

// ---------------------------------------------------------------- bus swept-path zones

// 두 직사각형(중심, 방향, 반길이, 반폭)이 겹치는지 (분리축)
function obbHit(ax, ay, ath, ahl, ahw, bx, by, bth, bhl, bhw) {
  const dx = bx - ax;
  const dy = by - ay;
  const ca = Math.cos(ath);
  const sa = Math.sin(ath);
  const cb = Math.cos(bth);
  const sb = Math.sin(bth);
  const cab = Math.abs(ca * cb + sa * sb);
  const sab = Math.abs(sa * cb - ca * sb);
  if (Math.abs(dx * ca + dy * sa) >= ahl + bhl * cab + bhw * sab) return false;
  if (Math.abs(-dx * sa + dy * ca) >= ahw + bhl * sab + bhw * cab) return false;
  if (Math.abs(dx * cb + dy * sb) >= bhl + ahl * cab + ahw * sab) return false;
  if (Math.abs(-dx * sb + dy * cb) >= bhw + ahl * sab + ahw * cab) return false;
  return true;
}

// 버스(bodyPose 의 축 모델 자세)가 버스 가능 차선을 지날 때의 차체와, 다른 차선 위 각 위치에 선
// 차의 차체가 BUS_PAD 안으로 닿는 곳마다 잠금 구역을 하나 더 둔다. 구간은 양쪽 모두 차체 "중심"
// 위치 범위다 (encountersFor 가 차 길이 반만큼 앞뒤로 옮겨 잡고 놓는다): 차체가 구간을 덮는 동안이
// 아니라 실제로 닿을 수 있는 자세인 동안만 잡는다.
// - 버스 대 아무 차 (busSide 0): 상대 차는 가장 큰 승용 차체. 버스 쪽은 버스만, 상대 쪽은 버스가
//   다가올 때(armed)만 참여한다: 버스가 없으면 승용차 흐름은 그대로다.
// - 버스 대 버스 (busSide 2): 상대 차선도 버스 가능이면 버스 차체끼리. 양쪽 모두 버스만.
// 기존 잠금 구역이 이미 두 자세를 모두 덮는 닿음은 빼서 (교차로 대부분) 같은 충돌을 두 번 잠그지 않는다.
const BUS_PAD = 0.15; // m, 차체 사이 여유 (발자국 가드 2·GUARD_PAD 포함)
function buildBusZones(segs, zones, L, W, carL, carW, carMinL) {
  const cell = 4;
  const grid = new Map();
  const a = L * AXLE;
  const p = [0, 0, 0];
  const q = [0, 0, 0];
  // 표본마다 그 자리에 선 승용차 / 버스 자세 (구간 밖은 직선 연장)
  const samp = segs.map((g) => {
    const n = Math.max(2, Math.ceil(g.len / SAMPLE) + 1);
    const ss = new Float64Array(n);
    const cx = new Float64Array(n);
    const cy = new Float64Array(n);
    const ct = new Float64Array(n);
    const bx = g.busOk ? new Float64Array(n) : null;
    const by = g.busOk ? new Float64Array(n) : null;
    const bt = g.busOk ? new Float64Array(n) : null;
    for (let i = 0; i < n; i++) {
      const s = (g.len * i) / (n - 1);
      ss[i] = s;
      segPos(g, s, p);
      cx[i] = p[0];
      cy[i] = p[1];
      ct[i] = segHeading(g, s);
      const key = Math.floor(p[0] / cell) * 100003 + Math.floor(p[1] / cell);
      let arr = grid.get(key);
      if (!arr) grid.set(key, (arr = []));
      arr.push(g.idx, i);
      if (bx) {
        segPos(g, s - a, p);
        segPos(g, s + a, q);
        bx[i] = (p[0] + q[0]) / 2;
        by[i] = (p[1] + q[1]) / 2;
        bt[i] = Math.atan2(q[1] - p[1], q[0] - p[0]);
      }
    }
    return { ss, cx, cy, ct, bx, by, bt, step: g.len / (n - 1) };
  });
  const linked = (A, B) => A.next.some((n) => n.seg === B.idx && n.entry === 0 && n.exit >= A.len - 1e-6);
  const hl = L / 2 + BUS_PAD / 2;
  const hw = W / 2 + BUS_PAD / 2;
  const chl = carL / 2 + BUS_PAD / 2;
  const chw = carW / 2 + BUS_PAD / 2;
  const span = Math.ceil((Math.hypot(L / 2, W / 2) + Math.hypot(L / 2, W / 2) + BUS_PAD) / cell);
  const pairs = [new Map(), new Map()]; // 버스 대 아무 차, 버스 대 버스
  const base = zones.length;
  // 기존 잠금 구역이 덮는가: 버스 중심 s, 상대 중심 t (상대 길이 ol) 에서 둘 다 그 구역을 잡고 있다
  const covered = (X, s, B, t, ol) => {
    for (const zl of X.zl) {
      const z = zones[zl.zone];
      if (z.order || z.seg[1 - zl.side] !== B.idx) continue;
      const o = z.iv[1 - zl.side];
      if (s >= zl.s0 - L / 2 && s <= zl.s1 + L / 2 && t >= o[0] - ol / 2 && t <= o[1] + ol / 2) return true;
    }
    return false;
  };
  for (const X of segs) {
    if (!X.busOk) continue;
    // X 앞뒤로 버스가 이어 달 수 있는 구간 조합마다 (차체 끝이 앞뒤 구간에 걸치므로)
    const preds = [];
    for (const P of segs) if (P.busOk) for (const nx of P.next) if (nx.seg === X.idx) preds.push({ g: P, exit: nx.exit, entry: nx.entry });
    if (!preds.length) preds.push(null);
    const succs = X.next.filter((nx) => segs[nx.seg].busOk).map((nx) => ({ g: segs[nx.seg], exit: nx.exit, entry: nx.entry }));
    if (!succs.length) succs.push(null);
    const sx = samp[X.idx];
    for (const pr of preds) {
      for (const su of succs) {
        const en = pr ? pr.entry : 0;
        const ex = su ? su.exit : X.len;
        if (ex - en < SAMPLE) continue;
        const pos = (s, out) => {
          if (s < en && pr) return segPos(pr.g, pr.exit - (en - s), out);
          if (s > ex && su) return segPos(su.g, su.entry + (s - ex), out);
          return segPos(X, s, out);
        };
        for (let s = en; s <= ex + 1e-9; s += SAMPLE) {
          pos(s - a, p);
          pos(s + a, q);
          const ox = (p[0] + q[0]) / 2;
          const oy = (p[1] + q[1]) / 2;
          const th = Math.atan2(q[1] - p[1], q[0] - p[0]);
          const c = Math.cos(th);
          const sn = Math.sin(th);
          const gx0 = Math.floor(ox / cell);
          const gy0 = Math.floor(oy / cell);
          for (let gx = gx0 - span; gx <= gx0 + span; gx++) {
            for (let gy = gy0 - span; gy <= gy0 + span; gy++) {
              const arr = grid.get(gx * 100003 + gy);
              if (!arr) continue;
              for (let k = 0; k < arr.length; k += 2) {
                const b = arr[k];
                if (b === X.idx || (pr && b === pr.g.idx) || (su && b === su.g.idx)) continue;
                const j = arr[k + 1];
                const sb = samp[b];
                const B = segs[b];
                for (let w = 0; w < 2; w++) {
                  const hit = w === 0 ? obbHit(ox, oy, th, hl, hw, sb.cx[j], sb.cy[j], sb.ct[j], chl, chw) : sb.bx && obbHit(ox, oy, th, hl, hw, sb.bx[j], sb.by[j], sb.bt[j], hl, hw);
                  if (!hit) continue;
                  if (covered(X, s, B, sb.ss[j], w === 0 ? carMinL : L)) continue;
                  const P = pairs[w];
                  const key = X.idx * 4096 + b;
                  let rec = P.get(key);
                  if (rec === undefined) {
                    rec = linked(X, B) || linked(B, X) ? null : { a: X.idx, b, hits: new Map() };
                    P.set(key, rec);
                  }
                  if (rec === null) continue;
                  const i = Math.round(s / sx.step);
                  const h = rec.hits.get(i);
                  if (!h) rec.hits.set(i, [j, j]);
                  else {
                    if (j < h[0]) h[0] = j;
                    if (j > h[1]) h[1] = j;
                  }
                }
              }
            }
          }
        }
      }
    }
  }
  for (let w = 0; w < 2; w++) {
    const keys = [...pairs[w].keys()].sort((x, y) => x - y);
    for (const key of keys) {
      const rec = pairs[w].get(key);
      // 버스 대 버스는 같은 차선 쌍이 양방향으로 두 번 나온다: 하나만
      if (!rec || (w === 1 && rec.a > rec.b && pairs[1].get(rec.b * 4096 + rec.a))) continue;
      let mate = null;
      for (let zi = 0; zi < base && !mate && w === 0; zi++) {
        const z = zones[zi];
        if (z.order && ((z.seg[0] === rec.a && z.seg[1] === rec.b) || (z.seg[0] === rec.b && z.seg[1] === rec.a))) mate = z;
      }
      zonesFromHits(segs, zones, rec, samp[rec.a].ss, samp[rec.b].ss, w === 0 ? 0 : 2, mate);
    }
  }
  for (const g of segs) g.zl.sort((p, q) => p.s0 - q.s0 || p.zone - q.zone);
  return zones.length - base;
}

// ---------------------------------------------------------------- signals

const YELLOW = 3;
const ALL_RED = 2;
const MIN_GREEN = 10;
const MAX_GREEN = 36;
const DEMAND_D = 40; // m before a stop line that count as demand

function buildSignals(segs, zones, junctions) {
  const ctrls = [];
  const pub = [];
  const tmp = [0, 0, 0];
  const zoneMid = zones.map((z) => {
    const g = segs[z.seg[0]];
    segPos(g, (z.iv[0][0] + z.iv[0][1]) / 2, tmp);
    return [tmp[0], tmp[1]];
  });
  junctions.forEach((J, ji) => {
    const inJ = (x, y) => Math.hypot(x - J.x, y - J.y) <= J.r;
    const approaches = [];
    for (const g of segs) {
      if (g.conn) continue;
      if (inJ(g.X[0], g.Y[0])) continue; // lanes that begin inside the junction leave it
      // first conflict zone of this junction along the lane
      let first = Infinity;
      for (const zl of g.zl) {
        const m = zoneMid[zl.zone];
        if (!inJ(m[0], m[1])) continue;
        const z = zones[zl.zone];
        const other = segs[z.seg[1 - zl.side]];
        // diverging from our own branch point is not a reason to stop
        if (other.conn && other.from === g.idx) continue;
        if (zl.s0 < first) first = zl.s0;
      }
      let stopAt = Infinity;
      if (g.stopS < g.len) {
        segPos(g, g.stopS, tmp);
        if (inJ(tmp[0], tmp[1])) stopAt = g.stopS;
      }
      if (first < Infinity) stopAt = Math.min(stopAt, first - 0.5);
      if (stopAt === Infinity) {
        // lane ends inside the junction and turns there
        const n = g.X.length - 1;
        if (inJ(g.X[n], g.Y[n]) && g.next.some((nx) => segs[nx.seg].conn)) stopAt = g.len - 1;
      }
      if (!(stopAt < Infinity)) continue;
      stopAt = Math.max(5, Math.min(stopAt, g.len - 1));
      segPos(g, stopAt, tmp);
      if (!inJ(tmp[0], tmp[1])) continue;
      const th = segHeading(g, stopAt);
      approaches.push({ seg: g.idx, s: stopAt, x: tmp[0], y: tmp[1], z: tmp[2], th });
    }
    if (approaches.length < 2) return;
    // group approaches by road axis (heading mod pi)
    const axis = (th) => ((th % Math.PI) + Math.PI) % Math.PI;
    const groups = [];
    for (const ap of approaches.sort((p, q) => p.seg - q.seg)) {
      const ax = axis(ap.th);
      let gi = groups.findIndex((G) => {
        const d = Math.abs(ax - G.axis);
        return Math.min(d, Math.PI - d) < (35 * Math.PI) / 180;
      });
      if (gi < 0) {
        groups.push({ axis: ax, aps: [] });
        gi = groups.length - 1;
      }
      groups[gi].aps.push(ap);
    }
    if (groups.length < 2) return;
    // main axis (more approaches) gets the longer green
    const ctrl = {
      name: J.name,
      x: J.x,
      y: J.y,
      groups: groups.length,
      active: ji % groups.length,
      phase: 'G',
      phaseStart: -((ji * 7) % MIN_GREEN),
      stops: groups.map(() => []),
      state: new Array(groups.length).fill('r'),
      remain: new Array(groups.length).fill(0),
    };
    const ci = ctrls.length;
    ctrls.push(ctrl);
    groups.forEach((G, gi) => {
      for (const ap of G.aps) {
        segs[ap.seg].stops.push({ ctrl: ci, group: gi, s: ap.s, pub: pub.length });
        ctrl.stops[gi].push({ seg: ap.seg, s: ap.s });
        pub.push({ x: ap.x, y: ap.y, z: ap.z, th: ap.th, state: 'r', lane: segs[ap.seg].lane, s: ap.s, junction: J.name, group: gi });
      }
    });
  });
  return { ctrls, pub };
}

// Vehicle-actuated control: a group keeps green while vehicles keep arriving (up to MAX_GREEN)
// and gives way after MIN_GREEN once its approaches are empty and another group is waiting.
// demand(c, g) reports whether group g has a vehicle near its stop lines.
function updateSignals(sig, t, demand) {
  for (const c of sig.ctrls) {
    const el = t - c.phaseStart;
    if (c.phase === 'G') {
      let other = false;
      for (let k = 1; k < c.groups; k++) if (demand(c, (c.active + k) % c.groups)) other = true;
      const mine = demand(c, c.active);
      if ((el >= MAX_GREEN && other) || (el >= MIN_GREEN && !mine && other)) {
        c.phase = 'Y';
        c.phaseStart = t;
      }
    } else if (c.phase === 'Y') {
      if (el >= YELLOW) {
        c.phase = 'AR';
        c.phaseStart = t;
      }
    } else if (el >= ALL_RED) {
      c.active = (c.active + 1) % c.groups;
      c.phase = 'G';
      c.phaseStart = t;
    }
    for (let g = 0; g < c.groups; g++) {
      c.state[g] = g === c.active ? (c.phase === 'G' ? 'g' : c.phase === 'Y' ? 'y' : 'r') : 'r';
      c.remain[g] = g === c.active && c.phase === 'Y' ? YELLOW - (t - c.phaseStart) : 0;
    }
  }
}

// ---------------------------------------------------------------- simulation

// Intelligent Driver Model acceleration towards an obstacle `gap` metres ahead closing at dv
function idmAcc(v, vd, A, T, gap, dv, s0) {
  const ss = s0 + Math.max(0, v * T + (v * dv) / (2 * Math.sqrt(A * B_COMF)));
  const g = Math.max(gap, 0.05);
  return A * (1 - Math.pow(v / vd, 4) - (ss / g) * (ss / g));
}

const DT_MAX = 0.1;
const MIN_GAP = 0.6; // hard bumper-to-bumper minimum on a shared path
const B_COMF = 2.0;
const B_YELLOW = 3.5;
const MUST_GO_DEC = 6.0;
const B_COMMIT = 4.0; // deceleration that defines the zone commit distance
const STUCK_LIMIT = 150;
const DBB_PATIENCE = 20; // s a vehicle waits for full room behind a box before it takes any room
const ESCAPE_T = 25; // s of logical (non-signal) standing before locks / ordering are ignored
const FADE_D = 6;
const EXIT_MARGIN = 40; // m a route runs on after leaving the map rectangle for the last time
const SRC_SLOW_MAX = 8;
const JAM_FRAC = 0.45; // share of a lane covered by standing vehicles that counts as jammed // queued vehicles a source may have before it pauses
const GUARD_PAD = 0.05; // m of extra clearance in the footprint guard
const BLEND = 15; // m over which a direct-link gap is blended out

export function createTraffic(scene, opts = {}) {
  const seed = (opts.seed ?? 1) >>> 0;
  const target = opts.targetCount ?? 260;
  const rand = mulberry32(seed * 2654435761 + 12345);
  const G = buildGraph(scene);
  const segs = G.segs;
  buildSpeedCaps(segs);
  const zones = buildZones(segs);
  const sig = buildSignals(segs, zones, opts.junctions ?? JUNCTIONS);
  const pubSignals = sig.pub;
  const stopRecs = [];
  for (const g of segs) for (const st of g.stops) stopRecs.push(st);

  const specs = { ...SPEC_FALLBACK, ...(scene.vehicle_specs ?? {}) };
  // 신호 위치를 정한 뒤에 만든다 (정지선 탐색에 끼지 않게)
  {
    // 상대 차선의 차는 가장 큰 승용 차체로 본다
    let carL = 0;
    let carW = 0;
    let carMinL = Infinity;
    for (const [k] of KIND_WEIGHTS) {
      carL = Math.max(carL, specs[k][0]);
      carW = Math.max(carW, specs[k][1]);
      carMinL = Math.min(carMinL, specs[k][0]);
    }
    buildBusZones(segs, zones, specs.bus[0], specs.bus[1], carL, carW, carMinL);
  }
  const combos = new Set();
  for (const f of scene.vehicle_atlas?.frames ?? []) combos.add(`${f.kind}|${f.color}`);
  const hasCombo = (k, c) => combos.size === 0 || combos.has(`${k}|${c}`);
  const colorsFor = {};
  for (const k of Object.keys(specs)) colorsFor[k] = [...combos].filter((x) => x.startsWith(`${k}|`)).map((x) => x.slice(k.length + 1)).sort();

  const sources = segs.filter((g) => g.isSource);
  const nextSpawn = new Float64Array(sources.length);

  // total in-map lane length (for the initial density)
  let mapLen = 0;
  {
    const p = [0, 0, 0];
    for (const g of segs) {
      if (g.conn) continue;
      for (let s = 0.5; s < g.len; s += 1) {
        segPos(g, s, p);
        if (G.inMap(p[0], p[1])) mapLen += 1;
      }
    }
  }

  const vehicles = [];
  const stats = { spawned: 0, despawned: 0, forcedRemovals: 0, guardStops: 0, escapes: 0, escapeEvents: 0, steps: 0 };
  let simT = 0; // internal clock (includes warm-up)
  let stepNo = 0;
  let nextId = 1;

  // occupancy: per segment, entries sorted by s (centre). Ghost entries = rear overhang.
  const occ = segs.map(() => []);
  const pool = [];
  let poolUsed = 0;
  const entry = (v, s) => {
    let e = pool[poolUsed];
    if (!e) pool[poolUsed] = e = { v: null, s: 0, ghost: false };
    poolUsed++;
    e.v = v;
    e.s = s;
    return e;
  };

  // ------------------------------------------------ routes
  function pickNext(g, visited) {
    let tot = 0;
    for (const nx of g.next) if (!visited.has(nx.seg)) tot += nx.w;
    if (tot <= 0) return null;
    let x = rand() * tot;
    for (const nx of g.next) {
      if (visited.has(nx.seg)) continue;
      x -= nx.w;
      if (x <= 0) return nx;
    }
    for (let i = g.next.length - 1; i >= 0; i--) if (!visited.has(g.next[i].seg)) return g.next[i];
    return null;
  }

  function makeRoute(seg0) {
    const rs = [seg0];
    const en = [0];
    const ex = [];
    const visited = new Set([seg0]);
    let cur = seg0;
    for (let hop = 0; hop < 60; hop++) {
      const nx = pickNext(segs[cur], visited);
      if (!nx) break;
      ex.push(nx.exit);
      rs.push(nx.seg);
      en.push(nx.entry);
      visited.add(nx.seg);
      cur = nx.seg;
    }
    ex.push(segs[cur].len);
    const n = rs.length;
    const start = new Float64Array(n);
    for (let k = 1; k < n; k++) start[k] = start[k - 1] + (ex[k - 1] - en[k - 1]);
    const end = start[n - 1] + (ex[n - 1] - en[n - 1]);
    // direct links may have a small gap between lane end and next lane start: blend it out
    const offX = new Float64Array(n);
    const offY = new Float64Array(n);
    for (let k = 1; k < n; k++) {
      const A = segs[rs[k - 1]];
      const B = segs[rs[k]];
      if (en[k] !== 0 || A.conn || B.conn || ex[k - 1] < A.len) continue;
      offX[k] = A.X[A.X.length - 1] - B.X[0];
      offY[k] = A.Y[A.Y.length - 1] - B.Y[0];
    }
    return clipRoute({ seg: Int32Array.from(rs), entry: Float64Array.from(en), exit: Float64Array.from(ex), start, end, n, busOk: true, offX, offY });
  }

  // A route ends EXIT_MARGIN metres after it leaves the map rectangle for the last time. Driving
  // it on to a far sink only lets junctions outside the map (unsignalled, fed by outside
  // sources) back their queues up into the map. The end lies on the picture's beige border at
  // worst, like most lane-end sinks already do. `inMap` tells whether the route is on the map
  // at all.
  function clipRoute(R) {
    let last = -1;
    for (let r = 0; r <= R.end; r += 4) {
      routePosR(R, r, _bp);
      if (G.inMap(_bp[0], _bp[1])) last = r;
    }
    R.inMap = last >= 0;
    const cut = last + EXIT_MARGIN;
    if (last >= 0 && cut < R.end - 1) {
      let k = 0;
      while (k < R.n - 1 && cut >= R.start[k + 1]) k++;
      const n = k + 1;
      R.seg = R.seg.slice(0, n);
      R.entry = R.entry.slice(0, n);
      R.exit = R.exit.slice(0, n);
      R.start = R.start.slice(0, n);
      R.offX = R.offX.slice(0, n);
      R.offY = R.offY.slice(0, n);
      R.exit[k] = R.entry[k] + (cut - R.start[k]);
      R.n = n;
      R.end = cut;
      R.clipped = true;
    }
    for (let k = 0; k < R.n; k++) if (!segs[R.seg[k]].busOk) R.busOk = false;
    return R;
  }

  // bus: 버스 전용 쪽(busSide) 구역은 버스만 받는다. 반대쪽은 bz 표시: 버스가 다가올 때만 유효 (live)
  // 버스 구역의 구간은 차체 중심 범위: len/2 만큼 옮겨 앞이 닿을 때 잡고 뒤가 지날 때 놓게 한다
  function encountersFor(route, bus, len) {
    const enc = [];
    const stops = [];
    for (let k = 0; k < route.n; k++) {
      const g = segs[route.seg[k]];
      const en = route.entry[k];
      const ex = route.exit[k];
      for (const zl of g.zl) {
        const lo = Math.max(zl.s0, en);
        const hi = Math.min(zl.s1, ex);
        if (hi - lo <= 0.05) continue; // interval lies beyond where this route leaves the segment
        const z = zones[zl.zone];
        if (z.bus && !bus && (z.busSide === 2 || zl.side === z.busSide)) continue;
        const sh = z.bus ? len / 2 : 0;
        enc.push({
          zone: zl.zone,
          side: zl.side,
          enter: route.start[k] + lo - en + sh,
          exit: route.start[k] + hi - en - sh,
          held: false,
          order: z.order,
          off: route.start[k] - en + z.ref[zl.side], // ordering coordinate p = r - off
          bz: z.bus === true && z.busSide !== 2 && zl.side !== z.busSide,
        });
      }
      for (const st of g.stops) {
        if (st.s >= en && st.s <= ex) stops.push({ rec: st, at: route.start[k] + st.s - en });
      }
    }
    enc.sort((p, q) => p.enter - q.enter || p.zone - q.zone);
    stops.sort((p, q) => p.at - q.at);
    return { enc, stops };
  }

  const _bp = [0, 0, 0];
  function routePosR(R, rr, out) {
    return routePosK(R, 0, rr, out);
  }
  // k: 탐색 시작 구간 힌트
  function routePosK(R, k, rr, out) {
    while (k > 0 && rr < R.start[k]) k--;
    while (k < R.n - 1 && rr >= R.start[k + 1]) k++;
    const d = rr - R.start[k];
    segPos(segs[R.seg[k]], d + R.entry[k], out);
    if (d < BLEND && (R.offX[k] !== 0 || R.offY[k] !== 0)) {
      const w = 1 - Math.max(0, d) / BLEND;
      out[0] += R.offX[k] * w;
      out[1] += R.offY[k] * w;
    }
    return out;
  }
  // 차체 자세 -> _px, _py, _pz, _pth. 경로 위치 rr 은 차체 중심.
  const _ba = [0, 0, 0];
  const _bb = [0, 0, 0];
  let _px = 0;
  let _py = 0;
  let _pz = 0;
  let _pth = 0;
  function bodyPose(R, k, rr, len) {
    if (len > 6) {
      const a = len * AXLE;
      routePosK(R, k, rr - a, _ba);
      routePosK(R, k, rr + a, _bb);
      _px = (_ba[0] + _bb[0]) / 2;
      _py = (_ba[1] + _bb[1]) / 2;
      _pz = (_ba[2] + _bb[2]) / 2;
    } else {
      routePosK(R, k, rr, _ba);
      _px = _ba[0];
      _py = _ba[1];
      _pz = _ba[2];
      routePosK(R, k, rr - 1.5, _ba);
      routePosK(R, k, rr + 1.5, _bb);
    }
    _pth = Math.atan2(_bb[1] - _ba[1], _bb[0] - _ba[0]);
  }

  function pickKind(route) {
    const busOk = route.busOk;
    if (busOk && rand() < BUS_SHARE_ON_BUS_ROUTES && colorsFor.bus?.length) return 'bus';
    let tot = 0;
    for (const [, w] of KIND_WEIGHTS) tot += w;
    let x = rand() * tot;
    for (const [k, w] of KIND_WEIGHTS) {
      x -= w;
      if (x <= 0) return k;
    }
    return 'sedan';
  }

  function pickColor(kind) {
    const avail = colorsFor[kind] ?? [];
    if (kind === 'taxi') {
      const c = rand() < 0.7 ? '#e8892f' : '#f4f4f0';
      return hasCombo(kind, c) ? c : avail[0];
    }
    if (kind === 'bus') {
      const x = rand();
      const c = x < 0.6 ? '#2f6fd0' : x < 0.84 ? '#3aa45a' : '#d23b2f';
      return hasCombo(kind, c) ? c : avail[0];
    }
    for (let i = 0; i < 4; i++) {
      const c = CAR_COLORS[Math.floor(rand() * CAR_COLORS.length)];
      if (hasCombo(kind, c)) return c;
    }
    return avail[Math.floor(rand() * avail.length)] ?? '#f4f4f0';
  }

  function newVehicle(route, r) {
    const kind = pickKind(route);
    const color = pickColor(kind);
    const [len, wid, h] = specs[kind];
    const bus = kind === 'bus';
    const { enc, stops } = encountersFor(route, bus, len);
    const veh = {
      id: nextId++,
      kind,
      color,
      len,
      wid,
      h,
      lane: segs[route.seg[0]].lane,
      s: r,
      v: 0,
      x: 0,
      y: 0,
      z: 0,
      th: 0,
      px: 0,
      py: 0,
      pz: 0,
      pth: 0,
      braking: false,
      conn: false,
      vis: false,
      fade: 1,
      _route: route,
      _ri: 0,
      _r: r,
      _r0: r,
      _enc: enc,
      _ei: 0,
      _stops: stops,
      _si: 0,
      _vf: (bus ? 0.85 : kind === 'taxi' ? 1.04 : 1) * (0.92 + 0.16 * rand()),
      _A: bus ? 1.0 : kind === 'taxi' ? 1.9 : kind === 'van' ? 1.4 : 1.7,
      _T: kind === 'taxi' ? 0.9 : bus ? 1.4 : 1.05,
      _acc: 0,
      _maxFront: Infinity,
      _stuck: 0,
      _zLim: Infinity,
      _dbbT: 0, // s standing in front of a box for lack of room behind it
      _lw: 0, // s standing still on a purely logical wait (zone / merge), red-light time excluded
      _nw: 0, // s standing still while not held by a red light
      _stopR: Infinity,
      _src: -1,
      _req: Infinity,
      _atRed: false,
      _occ: -1,
      _fadeIn: segs[route.seg[0]].onMapStart && !segs[route.seg[0]].conn,
      _fadeOut: !route.clipped && segs[route.seg[route.n - 1]].onMapEnd,
    };
    // skip encounters/stops already behind the body
    while (veh._ei < enc.length && enc[veh._ei].exit < r - len / 2) veh._ei++;
    while (veh._si < stops.length && stops[veh._si].at < r + len / 2) veh._si++;
    return veh;
  }

  // route-aware desired speed
  function desiredSpeed(v) {
    const R = v._route;
    let k = v._ri;
    const g = segs[R.seg[k]];
    const s = v._r - R.start[k] + R.entry[k];
    const i = Math.max(0, Math.min(g.vcap.length - 1, Math.round(s)));
    let vd = g.vcap[i];
    let d = R.exit[k] - s;
    for (k = k + 1; k < R.n && d < 80; k++) {
      const h = segs[R.seg[k]];
      const j = Math.max(0, Math.min(h.vcap.length - 1, Math.round(R.entry[k])));
      const c = Math.sqrt(h.vcap[j] * h.vcap[j] + 2 * 1.4 * Math.max(0, d));
      if (c < vd) vd = c;
      d += R.exit[k] - R.entry[k];
    }
    return Math.max(1.0, vd * v._vf);
  }

  // ------------------------------------------------ occupancy
  function buildOcc() {
    poolUsed = 0;
    for (const L of occ) L.length = 0;
    for (const v of vehicles) {
      const R = v._route;
      const k = v._ri;
      const e = entry(v, v._r - R.start[k] + R.entry[k]);
      e.ghost = false;
      occ[R.seg[k]].push(e);
      const rear = v._r - v.len / 2;
      for (let kk = k - 1; kk >= 0; kk--) {
        if (rear >= R.start[kk + 1]) break;
        const g = entry(v, R.exit[kk] + (v._r - R.start[kk + 1]));
        g.ghost = true;
        occ[R.seg[kk]].push(g);
      }
    }
    for (const L of occ) {
      for (let i = 1; i < L.length; i++) {
        const e = L[i];
        let j = i - 1;
        while (j >= 0 && (L[j].s > e.s || (L[j].s === e.s && L[j].v.id > e.v.id))) {
          L[j + 1] = L[j];
          j--;
        }
        L[j + 1] = e;
      }
      for (let i = 0; i < L.length; i++) if (!L[i].ghost) L[i].v._occ = i;
    }
  }

  // leader along the route: returns gap (bumper to bumper, route metres), sets _lv (speed), _lr (rear in route coords)
  let _lv = 0;
  let _lr = Infinity;
  let _lveh = null; // the leader itself (for the wait-for chain)
  function findLeader(v) {
    const R = v._route;
    const k0 = v._ri;
    const front = v._r + v.len / 2;
    const L = occ[R.seg[k0]];
    for (let i = v._occ + 1; i < L.length; i++) {
      const e = L[i];
      if (e.v === v) continue;
      _lv = e.v.v;
      _lveh = e.v;
      _lr = R.start[k0] + (e.s - e.v.len / 2) - R.entry[k0];
      return _lr - front;
    }
    for (let k = k0 + 1; k < R.n; k++) {
      if (R.start[k] - front > LOOKAHEAD_MAX) break;
      const M = occ[R.seg[k]];
      const en = R.entry[k];
      for (let i = 0; i < M.length; i++) {
        const e = M[i];
        if (e.v === v) continue;
        if (e.s + e.v.len / 2 <= en) continue; // still upstream of where we join
        let rear = e.s - e.v.len / 2;
        if (en > 0 && rear < en) rear = en;
        _lv = e.v.v;
        _lveh = e.v;
        _lr = R.start[k] + rear - en;
        return _lr - front;
      }
    }
    _lv = 0;
    _lveh = null;
    _lr = Infinity;
    return Infinity;
  }

  // ------------------------------------------------ zones
  let _bh = null; // holder found by the last blocked() / waiter found by fairnessDenies()
  // 버스 구역의 상대 쪽은 이번 걸음에 버스가 다가와 있을 때만 (buildParticipants 에서 armStep)
  const live = (e) => !e.bz || zones[e.zone].armStep === stepNo;
  function blocked(z, side, v) {
    // 버스 쪽: 상대 구간에 실제로 있거나 곧 들어설(편한 제동으로 못 서는) 차가 있어도 막힌다.
    // 상대 쪽 차는 버스가 다가올 때만 잡으므로 그 전에 들어선 차는 잡은 자가 아니다.
    if (z.bus && side === z.busSide) {
      const ob = 1 - side;
      const b0 = z.iv[ob][0];
      const b1 = z.iv[ob][1];
      const L = occ[z.seg[ob]];
      for (let i = 0; i < L.length; i++) {
        const e = L[i];
        const o = e.v;
        if (o === v || o === v._lead) continue; // 내 앞차는 어차피 따라간다
        if (e.s >= b1 || e.s + (o.v * o.v) / (2 * B_COMMIT) + 0.5 <= b0) continue;
        _bh = o;
        return true;
      }
    }
    const other = z.holders[1 - side];
    for (let i = 0; i < other.length; i++) {
      const h = other[i];
      if (h === v) continue;
      if (z.holders[side].indexOf(h) >= 0) continue; // merging vehicle on both sides
      if (z.bus && h._lead === v) continue; // 나를 따라오는 버스: 내가 먼저 지나간다
      _bh = h;
      return true;
    }
    return false;
  }

  // fairness: a zone remembers the oldest waiting request per side (refreshed every step).
  // Requests are totally ordered by (time of first denial, id), so fairness alone can never
  // produce a circular wait: the globally oldest waiter only waits for actual holders.
  function fairnessDenies(z, side, v) {
    const o = 1 - side;
    if (z.waitStep[o] < stepNo - 1) return false;
    const mine = v._req < Infinity ? v._req : simT;
    if (z.bus && z.waitV[o] && z.waitV[o]._lead === v) return false;
    // 먼저 온 차가 (몇 대 건너) 나를 기다리고 있으면 양보는 순환 대기만 만든다: 양보는 물리 제약이 아니다
    if (z.waitV[o] && waitsFor(z.waitV[o], v)) return false;
    if (z.waitSince[o] < mine || (z.waitSince[o] === mine && z.waitId[o] < v.id)) {
      _bh = z.waitV[o];
      return true;
    }
    return false;
  }

  // w 가 기다리는 차를 (지난 판단 기준으로) 따라가다 v 에 닿는가
  function waitsFor(w, v) {
    for (let d = 0; d < 6 && w; d++) {
      const why = w._why;
      if (why === 'lead') w = w._lead;
      else if (why === 'merge') w = w._ovv;
      else if (why === 'zone') w = w._zr === 'dbb' || w._zr === 'queue' ? w._lead ?? w._ovv : w._zh;
      else return false;
      if (w === v) return true;
    }
    return false;
  }

  function registerWait(z, side, v) {
    const t = v._req;
    if (z.waitStep[side] < stepNo - 1 || t < z.waitSince[side] || (t === z.waitSince[side] && v.id < z.waitId[side])) {
      z.waitSince[side] = t;
      z.waitId[side] = v.id;
      z.waitV[side] = v;
    }
    z.waitStep[side] = stepNo;
  }

  function release(v, e) {
    if (!e.held) return;
    const H = zones[e.zone].holders[e.side];
    const i = H.indexOf(v);
    if (i >= 0) H.splice(i, 1);
    e.held = false;
  }

  function releaseAll(v) {
    for (const e of v._enc) release(v, e);
  }

  const chain = [];
  // returns the route position the front must not pass because of zones (Infinity if none)
  function claimZones(v, front, look, limit, oLim) {
    const enc = v._enc;
    const rear = v._r - v.len / 2;
    let i = v._ei;
    while (i < enc.length && (enc[i].held || enc[i].order || enc[i].exit < rear || !live(enc[i]))) i++;
    if (i >= enc.length) return Infinity;
    const e0 = enc[i];
    if (e0.enter - front > look) return Infinity;
    if (e0.enter >= limit) return Infinity; // must stop earlier anyway (red light)
    // never reserve a zone the vehicle ahead on our path has not entered yet: it gets there
    // first, and reserving past it can deadlock (we would hold what it waits for)
    v._zr = 'queue';
    if (e0.enter > _lr) return e0.enter;
    chain.length = 0;
    let chainEnd = e0.exit;
    for (let j = i; j < enc.length && chain.length < 16; j++) {
      const e = enc[j];
      if (e.order || !live(e)) continue;
      if (e.enter > chainEnd + v.len + 4 || e.enter > _lr) break;
      if (e.exit > chainEnd) chainEnd = e.exit;
      if (!e.held) chain.push(e);
    }
    const dist = e0.enter - front;
    const mustGo = dist < (v.v * v.v) / (2 * MUST_GO_DEC);
    // approach phase: far from the zone we only check that the way is clear and slow down
    // smoothly if it is not; the lock is taken at the commit distance (hard-braking range),
    // which keeps zones held only for the time a vehicle actually needs them
    if (dist > (v.v * v.v) / (2 * B_COMMIT) + 1.5 + v.v * 0.1) {
      for (const e of chain) {
        const z = zones[e.zone];
        if (blocked(z, e.side, v) || fairnessDenies(z, e.side, v)) {
          v._zr = 'yield';
          v._zb = e.zone;
          v._zh = _bh;
          return e0.enter;
        }
      }
      return Infinity;
    }
    let ok = true;
    for (const e of chain) {
      const z = zones[e.zone];
      const bl = blocked(z, e.side, v);
      if (bl || (!mustGo && fairnessDenies(z, e.side, v))) {
        v._zr = bl ? 'blocked' : 'fair';
        v._zb = e.zone;
        if (ok) v._zh = _bh;
        if (ok && v._req === Infinity) v._req = simT;
        ok = false;
        registerWait(z, e.side, v);
      }
    }
    if (!ok) return e0.enter;
    // do not block the box: the whole body must fit after the chain, counting only the room the
    // vehicle ahead is sure to make (its comfortable stopping distance). A leader that is merely
    // rolling may stop a moment later and leave us standing inside the box.
    // After DBB_PATIENCE s of standing for room it falls back to the old rule (wait only while
    // the vehicle ahead is nearly standing): otherwise a stream that merges in behind the box
    // takes every gap and it starves.
    v._zr = 'dbb';
    const patient = v._dbbT < DBB_PATIENCE;
    // a leader pulling away (accelerating from a green) is trusted to clear: counting only its
    // stopping distance there held every follower back and cut the stop line's discharge rate
    const lStrict = patient && !(_lveh && _lveh._acc > 0.3 && _lv > 0.5);
    const lr = lStrict ? _lr + (_lv * _lv) / (2 * B_COMF) : _lv < 1.5 ? _lr : Infinity;
    const ol = patient ? oLim + (_ovl * _ovl) / (2 * B_COMF) : _ovl < 1.5 ? oLim : Infinity;
    if (!mustGo && lr < Infinity && lr - MIN_GAP - 1.0 - v.len < chainEnd) return e0.enter;
    if (!mustGo && ol < Infinity && ol - 1.0 - v.len < chainEnd) return e0.enter;
    for (const e of chain) {
      const z = zones[e.zone];
      z.holders[e.side].push(v);
      e.held = true;
      if (z.waitStep[e.side] >= stepNo - 1 && z.waitId[e.side] === v.id) z.waitStep[e.side] = -10;
    }
    v._req = Infinity;
    return Infinity;
  }

  // ------------------------------------------------ ordered (merge / diverge) zones
  const orderZones = zones.filter((z) => z.order);
  function buildParticipants() {
    for (const z of orderZones) {
      z.part[0].length = 0;
      z.part[1].length = 0;
    }
    for (const v of vehicles) {
      const front = v._r + v.len / 2;
      const rear = v._r - v.len / 2;
      const enc = v._enc;
      for (let i = v._ei; i < enc.length; i++) {
        const e = enc[i];
        if (e.enter - front > ORDER_LOOK) break;
        if (rear > e.exit) continue;
        // 버스가 ORDER_LOOK 안으로 다가온 버스 구역: 상대 쪽 차도 잡고 기다리기 시작한다
        if (v.kind === 'bus' && !e.bz && zones[e.zone].bus) zones[e.zone].armStep = stepNo;
        if (!e.order) continue;
        // a vehicle held by a red light before this zone does not take part in its ordering, nor
        // does one standing still at a lock it has not got (last step's limit at or before this
        // zone): it cannot come in first, and others yielding to it can starve behind it for good
        if (v._stopR <= e.enter) continue;
        if (v.v < 0.5 && v._zLim <= e.enter + 0.05) continue;
        zones[e.zone].part[e.side].push(entry(v, v._r - e.off));
      }
    }
  }

  // Virtual leader from merge/diverge zones: vehicles of both streams are ordered by their
  // distance to the common point; a vehicle may not enter the zone closer than the bumper of
  // the vehicle ordered ahead of it. Returns the front limit (route coordinates).
  let _ovl = 0;
  function orderLimit(v, front) {
    const enc = v._enc;
    const rear = v._r - v.len / 2;
    let lim = Infinity;
    _ovl = 0;
    for (let i = v._ei; i < enc.length; i++) {
      const e = enc[i];
      if (e.enter - front > ORDER_LOOK) break;
      if (!e.order || rear > e.exit) continue;
      const pMe = v._r - e.off;
      const O = zones[e.zone].part[1 - e.side];
      for (let j = 0; j < O.length; j++) {
        const o = O[j];
        if (o.v === v) continue;
        if (!(o.s > pMe || (o.s === pMe && o.v.id < v.id))) continue;
        // 앞 순서인 차가 내가 잡은 잠금을 기다리고 있으면 내가 먼저 (안 그러면 서로 기다린다)
        if (o.v._why === 'zone' && o.v._zr === 'blocked' && o.v._zh === v) continue;
        const L = Math.max(e.enter, o.s - o.v.len / 2 + e.off - MIN_GAP - zones[e.zone].extra);
        if (L < lim) {
          lim = L;
          _ovl = o.v.v;
          v._ovid = o.v.id;
          v._ovv = o.v;
          v._ovz = e.zone;
        }
      }
    }
    return lim;
  }

  // ------------------------------------------------ per-vehicle decision
  function decide(v) {
    const front = v._r + v.len / 2;
    const vd = desiredSpeed(v);
    const A = v._A;
    const T = v._T;
    let acc = A * (1 - Math.pow(v.v / vd, 4));
    let maxFront = Infinity;
    const idm = (gap, dv, s0) => idmAcc(v.v, vd, A, T, gap, dv, s0);
    const prevWhy = v._why;
    v._why = 'free';

    const gap = findLeader(v);
    v._lead = _lveh;
    if (gap < Infinity) {
      const a = idm(gap, v.v - _lv, 2.0);
      if (a < acc) {
        acc = a;
        v._why = 'lead';
      }
      maxFront = Math.min(maxFront, _lr - MIN_GAP);
    }

    // escape hatch for purely logical waits: after ESCAPE_T standing still in a wait that does
    // not end at a red light or a moving vehicle (see waitsOnQueue) the vehicle ignores
    // ordering/locks; the footprint guard still applies
    const escape = v._lw > ESCAPE_T && (prevWhy === 'merge' || prevWhy === 'zone' || prevWhy === 'escape');
    if (escape && !v._esc) {
      v._esc = true;
      stats.escapeEvents++;
    }
    const oLim = escape ? Infinity : orderLimit(v, front);
    if (oLim < Infinity) {
      const a = idm(oLim + MIN_GAP - front, v.v - _ovl, 2.0);
      if (a < acc) {
        acc = a;
        v._why = 'merge';
      }
      maxFront = Math.min(maxFront, oLim);
    }

    // signals
    let stopAt = Infinity;
    v._atRed = false;
    const stops = v._stops;
    while (v._si < stops.length && stops[v._si].at < front - 1e-9) v._si++;
    for (let i = v._si; i < stops.length; i++) {
      const st = stops[i];
      const d = st.at - front;
      if (d > LOOKAHEAD_MAX) break;
      const ctrl = sig.ctrls[st.rec.ctrl];
      const state = ctrl.state[st.rec.group];
      let stop = false;
      if (state === 'r') stop = true;
      else if (state === 'y') {
        // go only if stopping would be too harsh and the line is cleared before red
        const canStop = d >= (v.v * v.v) / (2 * B_YELLOW) - 0.01;
        stop = canStop || v.v < 0.5 || d / v.v > ctrl.remain[st.rec.group] - 0.1;
      }
      if (stop) {
        stopAt = st.at;
        v._atRed = true;
        break;
      }
    }
    v._stopR = stopAt;
    if (stopAt < Infinity) {
      const a = idm(stopAt - front, v.v, 0.3);
      if (a < acc) {
        acc = a;
        v._why = 'signal';
      }
      maxFront = Math.min(maxFront, stopAt);
    }

    // conflict zones
    const look = (v.v * v.v) / (2 * B_COMF) + v.v * 1.0 + 8;
    const zLim = escape ? Infinity : claimZones(v, front, look, stopAt, oLim);
    v._zLim = zLim;
    if (escape) {
      stats.escapes++;
      if (v._why === 'free') v._why = 'escape';
    }
    if (zLim < Infinity) {
      const a = idm(zLim - front, v.v, 0.5);
      if (a < acc) {
        acc = a;
        v._why = 'zone';
      }
      maxFront = Math.min(maxFront, zLim);
    }

    // a vehicle that will stop short of every zone it holds (red light ahead of them, or standing
    // in a queue before the box) gives the reservations back: holding them would stop cross
    // traffic for a whole red phase. It claims again when it gets going.
    let minEnter = Infinity;
    const enc = v._enc;
    for (let i = v._ei; i < enc.length; i++) {
      const e = enc[i];
      if (e.enter > front + 250) break;
      if (!e.held) continue;
      if (e.enter <= front + 0.05) {
        minEnter = -Infinity; // already inside one: keep the whole chain
        break;
      }
      if (e.enter < minEnter) minEnter = e.enter;
    }
    if (minEnter < Infinity && minEnter > -Infinity && (stopAt <= minEnter || (v.v < 0.1 && maxFront < minEnter - 0.3))) {
      for (let i = v._ei; i < enc.length; i++) if (enc[i].held) release(v, enc[i]);
    }

    if (acc < -9) acc = -9;
    v._acc = acc;
    v._maxFront = maxFront;
  }

  // Does the standing vehicle v wait on a physical queue? Follow what it waits for (leader,
  // vehicle ordered ahead at a merge, zone holder or older waiter) until the chain reaches a red
  // light or a vehicle that is moving: then the wait resolves by itself. A chain that comes back
  // to v (circular wait) or ends at a vehicle that stands for no logical reason (footprint guard)
  // is a logical wait, the only kind the escape hatch is for.
  function waitsOnQueue(v) {
    let w = v;
    for (let d = 0; d < 40; d++) {
      const why = w._why;
      let b;
      if (why === 'lead') b = w._lead;
      else if (why === 'merge') b = w._ovv;
      else if (why === 'zone') b = w._zr === 'dbb' || w._zr === 'queue' ? w._lead ?? w._ovv : w._zh;
      else return why === 'signal' || (w !== v && w._acc > 0.3);
      if (!b || b._dead) return true;
      if (b === v) return false;
      if (b.v > 0.5 || (b._acc > 0.3 && b._why !== 'escape')) return true;
      w = b;
    }
    return true;
  }

  // ------------------------------------------------ pose

  function pose(v) {
    const R = v._route;
    // heading from the chord over +-1.5 m (doc 04); 버스는 앞뒤 축을 경로에 둔다 (bodyPose)
    bodyPose(R, v._ri, v._r, v.len);
    v.x = _px;
    v.y = _py;
    v.z = _pz;
    v.th = _pth;
    const k = v._ri;
    const g = segs[R.seg[k]];
    const s = v._r - R.start[k] + R.entry[k];
    if (g.conn) {
      v.lane = g.lane;
      v.s = g.toEntry - (g.len - s);
      v.conn = true;
    } else {
      v.lane = g.lane;
      v.s = s;
      v.conn = false;
    }
    v.vis = G.inMap(v.x, v.y);
    v._scr = G.onScreen(v.x, v.y, v.z);
    let f = 1;
    if (v._fadeIn) f = Math.min(f, (v._r - v._r0) / FADE_D);
    if (v._fadeOut) f = Math.min(f, (R.end - v._r) / FADE_D);
    v.fade = f < 0 ? 0 : f > 1 ? 1 : f;
  }

  function savePrev(v) {
    v.px = v.x;
    v.py = v.y;
    v.pz = v.z;
    v.pth = v.th;
  }

  // ------------------------------------------------ footprint guard
  const GRID = 16;
  const grid = new Map();
  const gridKeys = [];
  function buildGrid() {
    for (const k of gridKeys) grid.get(k).length = 0;
    gridKeys.length = 0;
    for (const v of vehicles) {
      const k = Math.floor(v.x / GRID) * 65536 + Math.floor(v.y / GRID);
      let a = grid.get(k);
      if (!a) grid.set(k, (a = []));
      if (a.length === 0) gridKeys.push(k);
      a.push(v);
    }
  }

  // separating-axis test of two oriented boxes, inflated by GUARD_PAD
  function boxesTouch(ax, ay, ath, al, aw, bx, by, bth, bl, bw) {
    const dx = bx - ax;
    const dy = by - ay;
    const reach = (al + bl) / 2 + (aw + bw) / 2 + 2 * GUARD_PAD;
    if (dx * dx + dy * dy > reach * reach) return false;
    const ca = Math.cos(ath);
    const sa = Math.sin(ath);
    const cb = Math.cos(bth);
    const sb = Math.sin(bth);
    const ha = al / 2 + GUARD_PAD;
    const wa = aw / 2 + GUARD_PAD;
    const hb = bl / 2 + GUARD_PAD;
    const wb = bw / 2 + GUARD_PAD;
    // axes: a's length/width directions, then b's
    const cab = Math.abs(ca * cb + sa * sb); // |cos(a-b)|
    const sab = Math.abs(sa * cb - ca * sb); // |sin(a-b)|
    if (Math.abs(dx * ca + dy * sa) > ha + hb * cab + wb * sab) return false;
    if (Math.abs(-dx * sa + dy * ca) > wa + hb * sab + wb * cab) return false;
    if (Math.abs(dx * cb + dy * sb) > hb + ha * cab + wa * sab) return false;
    if (Math.abs(-dx * sb + dy * cb) > wb + ha * sab + wa * cab) return false;
    return true;
  }

  function poseAt(v, rr) {
    bodyPose(v._route, v._ri, rr, v.len);
  }

  function touchesAny(v, rr) {
    poseAt(v, rr);
    const cx = Math.floor(_px / GRID);
    const cy = Math.floor(_py / GRID);
    for (let gx = cx - 1; gx <= cx + 1; gx++) {
      for (let gy = cy - 1; gy <= cy + 1; gy++) {
        const a = grid.get(gx * 65536 + gy);
        if (!a) continue;
        for (let j = 0; j < a.length; j++) {
          const o = a[j];
          if (o === v || o._dead) continue;
          if (boxesTouch(_px, _py, _pth, v.len, v.wid, o.x, o.y, o.th, o.len, o.wid)) {
            // only refuse moves that make things worse: if already touching (should not
            // happen), allow moves that increase the distance
            if (!boxesTouch(v.x, v.y, v.th, v.len, v.wid, o.x, o.y, o.th, o.len, o.wid)) return true;
            if (Math.hypot(_px - o.x, _py - o.y) < Math.hypot(v.x - o.x, v.y - o.y)) return true;
          }
        }
      }
    }
    return false;
  }

  function touchesAnyAtSpawn(v) {
    for (const o of vehicles) {
      if (o === v) continue;
      if (boxesTouch(v.x, v.y, v.th, v.len, v.wid, o.x, o.y, o.th, o.len, o.wid)) return true;
    }
    return false;
  }

  // ------------------------------------------------ spawning
  function tryClaimAll(v) {
    // claim every zone the body already overlaps (spawn / initial placement)
    const front = v._r + v.len / 2;
    const rear = v._r - v.len / 2;
    const need = [];
    for (let i = v._ei; i < v._enc.length; i++) {
      const e = v._enc[i];
      if (e.enter > front + 2) break;
      if (e.exit < rear || !live(e)) continue;
      const z = zones[e.zone];
      if (blocked(z, e.side, v)) return false;
      need.push(e);
    }
    for (const e of need) {
      zones[e.zone].holders[e.side].push(v);
      e.held = true;
    }
    return true;
  }

  function routeJammed(route) {
    for (let k = 0; k < route.n; k++) {
      const g = segs[route.seg[k]];
      if (!g.conn && segSlow[g.idx] > JAM_FRAC * Math.min(g.len, 300)) return true;
    }
    return false;
  }

  function spawnAt(src, visibleNow) {
    // drivers avoid jammed roads: re-draw the route a few times, give up if all are jammed
    let route = makeRoute(src.idx);
    for (let t = 0; t < 3 && (routeJammed(route) || !route.inMap); t++) route = makeRoute(src.idx);
    if (!route.inMap) {
      _fail.offmap = (_fail.offmap || 0) + 1;
      return false;
    }
    if (routeJammed(route)) {
      _fail.jam = (_fail.jam || 0) + 1;
      srcStat[srcIndex.get(src.idx)].jam++;
      return false;
    }
    const v = newVehicle(route, 0);
    const r = v.len / 2 + 0.2;
    v._r = r;
    v._r0 = r;
    while (v._ei < v._enc.length && v._enc[v._ei].exit < r - v.len / 2) v._ei++;
    for (const nv of vehicles) {
      // vehicles spawned this very step on the same source are not in occ yet
      if (nv._route.seg[nv._ri] === src.idx && nv._spawnStep === stepNo) {
        nextId--;
        return false;
      }
    }
    // nearest vehicle ahead along the whole route (start-of-step positions)
    v._occ = -1;
    const gap = findLeader(v);
    const lv = _lv;
    const vd = desiredSpeed(v);
    // fast enough to join the flow, slow enough to stop comfortably behind the leader
    const room = Math.max(0, gap - 2.5);
    const v0 = Math.min(vd * 0.9, room / v._T, Math.sqrt(lv * lv + 2 * B_COMF * room));
    // only spawn into flowing traffic: a source never feeds a standing queue
    if (gap < v.len + 8 || v0 < Math.max(3, 0.5 * vd)) {
      _fail.space = (_fail.space || 0) + 1;
      srcStat[srcIndex.get(src.idx)].space++;
      nextId--;
      return false;
    }
    if (!tryClaimAll(v)) {
      nextId--;
      return false;
    }
    v.v = v0;
    v._src = srcIndex.get(src.idx) ?? -1;
    v._spawnStep = stepNo;
    pose(v);
    if (touchesAnyAtSpawn(v)) {
      releaseAll(v);
      nextId--;
      return false;
    }
    savePrev(v);
    vehicles.push(v);
    stats.spawned++;
    srcStat[srcIndex.get(src.idx)].ok++;
    return true;
  }

  // Demand control. Global: stop spawning above the target count. Per source: a source whose
  // own vehicles are standing in queues pauses, so congested corridors are not overfed while
  // free-flowing ones keep the count up.
  const _fail = {};
  const forcedLog = [];
  const srcSlow = new Int32Array(sources.length);
  const segSlow = new Float64Array(segs.length); // metres of standing vehicles per segment
  const srcIndex = new Map(sources.map((g, i) => [g.idx, i]));
  const srcStat = sources.map(() => ({ ok: 0, space: 0, jam: 0, slow: 0 }));
  function spawnStep(visibleNow) {
    if (vehicles.length >= target * 1.8 || visibleNow >= target * 1.03) return;
    srcSlow.fill(0);
    segSlow.fill(0);
    for (const v of vehicles) {
      if (v.v >= 2) continue;
      if (v._src >= 0) srcSlow[v._src]++;
      segSlow[v._route.seg[v._ri]] += v.len + 2;
    }
    const ratio = visibleNow / Math.max(1, target);
    const f = Math.min(4, Math.max(0.25, ratio * ratio * ratio));
    for (let i = 0; i < sources.length; i++) {
      if (simT < nextSpawn[i]) continue;
      if (srcSlow[i] >= SRC_SLOW_MAX) {
        _fail.src = (_fail.src || 0) + 1;
        srcStat[i].slow++;
        nextSpawn[i] = simT + 2;
        continue;
      }
      const src = sources[i];
      const base = src.baseV >= 10 ? 1.8 : src.hw.endsWith('_link') ? 9 : src.onMapStart ? 8 : 3.5;
      if (spawnAt(src, visibleNow)) nextSpawn[i] = simT + base * f * (0.4 + 1.2 * rand());
      else nextSpawn[i] = simT + 0.5;
    }
  }

  function removeAt(i) {
    const v = vehicles[i];
    releaseAll(v);
    // drop wait-for references so a removed vehicle does not keep a chain of others alive
    v._lead = null;
    v._ovv = null;
    v._zh = null;
    for (const z of [0, 1]) for (const e of v._enc) if (zones[e.zone].waitV[z] === v) zones[e.zone].waitV[z] = null;
    vehicles[i] = vehicles[vehicles.length - 1];
    vehicles.pop();
  }

  // ------------------------------------------------ initial placement
  function initialFill() {
    const spacing = Math.max(9, mapLen / Math.max(1, target));
    const placed = [];
    for (const g of segs) {
      if (g.conn) continue;
      let s = g.len - 4 - rand() * spacing;
      let lastRear = Infinity;
      while (s > 4) {
        const route = makeRoute(g.idx);
        if (!route.inMap || route.end < s + 10) {
          s -= 3;
          continue;
        }
        const v = newVehicle(route, s);
        const front = s + v.len / 2;
        const rear = s - v.len / 2;
        if (rear < 1 || front > lastRear - 4) {
          nextId--;
          s -= 3;
          continue;
        }
        // keep clear of conflict zones and signal stop lines at start
        let clash = false;
        for (const e of v._enc) {
          if (!e.bz && e.enter < front + 3 && e.exit > rear - 3) clash = true;
        }
        for (const st of g.stops) if (Math.abs(st.s - s) < v.len) clash = true;
        if (clash) {
          nextId--;
          s -= 3;
          continue;
        }
        const vd = desiredSpeed(v);
        const gap = lastRear - front;
        v.v = Math.max(0, Math.min(vd * 0.85, (gap - 2) / v._T));
        v._fadeIn = false;
        pose(v);
        if (touchesAnyAtSpawn(v)) {
          nextId--;
          s -= 3;
          continue;
        }
        savePrev(v);
        vehicles.push(v);
        placed.push(v);
        lastRear = rear;
        s -= v.len + spacing * (0.5 + rand());
      }
    }
    return placed.length;
  }

  // a group has demand when a vehicle's front is within DEMAND_D before one of its stop lines
  function signalDemand(c, g) {
    for (const st of c.stops[g]) {
      const L = occ[st.seg];
      for (let i = 0; i < L.length; i++) {
        const f = L[i].s + L[i].v.len / 2;
        if (f <= st.s + 0.01 && f > st.s - DEMAND_D) return true;
      }
    }
    return false;
  }

  // ------------------------------------------------ step
  let visible = 0;
  function step(dt = 1 / 30) {
    if (!(dt > 0)) return;
    if (dt > DT_MAX) dt = DT_MAX;
    simT += dt;
    stepNo++;
    stats.steps++;
    updateSignals(sig, simT, signalDemand);
    for (const p of pubSignals) p.state = sig.ctrls[p._ctrl].state[p.group];

    for (const v of vehicles) savePrev(v);
    buildOcc();

    // releases
    for (const v of vehicles) {
      const rear = v._r - v.len / 2;
      const enc = v._enc;
      for (let i = v._ei; i < enc.length; i++) {
        const e = enc[i];
        if (e.enter > v._r + v.len / 2 + 200) break;
        if (e.held && rear > e.exit) release(v, e);
      }
      while (v._ei < enc.length && !enc[v._ei].held && enc[v._ei].exit < rear) v._ei++;
    }

    buildParticipants();
    for (const v of vehicles) decide(v);

    // integrate (sequential, with a footprint guard: a move that would make this vehicle's
    // box touch any other vehicle's current box is shortened or cancelled, so the no-overlap
    // invariant holds by construction even where the lane geometry is rough)
    buildGrid();
    for (let i = vehicles.length - 1; i >= 0; i--) {
      const v = vehicles[i];
      let vn = v.v + v._acc * dt;
      if (vn < 0) vn = 0;
      let dr = 0.5 * (v.v + vn) * dt;
      const front = v._r + v.len / 2;
      let clamped = false;
      if (front + dr > v._maxFront) {
        dr = Math.max(0, v._maxFront - front);
        clamped = true;
        if (vn > dr / dt) vn = dr / dt;
      }
      if (dr > 0) {
        let tries = 0;
        while (dr > 0 && touchesAny(v, v._r + dr)) {
          dr = tries < 2 ? dr * 0.4 : 0;
          tries++;
          clamped = true;
        }
        if (dr === 0) {
          vn = 0;
          v._guard = (v._guard || 0) + 1;
          stats.guardStops++;
        }
        if (vn > dr / dt) vn = dr / dt;
      }
      v.braking = v._acc < -0.6 || (clamped && v.v > 0.3);
      v.v = vn;
      v._r += dr;
      const R = v._route;
      while (v._ri < R.n - 1 && v._r >= R.start[v._ri + 1]) v._ri++;
      if (v._r >= R.end) {
        v._dead = true;
        removeAt(i);
        stats.despawned++;
        continue;
      }
      pose(v);
      if (vn < 0.1) {
        v._stuck += dt;
        if (!v._atRed) v._nw += dt;
        if ((v._why === 'zone' || v._why === 'merge' || v._why === 'escape') && !waitsOnQueue(v)) v._lw += dt;
        if (v._why === 'zone' && v._zr === 'dbb') v._dbbT += dt;
      } else if (vn > 0.5) {
        v._stuck = 0;
        v._nw = 0;
        v._lw = 0;
        v._dbbT = 0;
        v._esc = false;
      }
      // last resort for a vehicle that cannot move for minutes; on screen it gets twice as long
      if (v._nw > (v._scr ? 2 * STUCK_LIMIT : STUCK_LIMIT) && !v._atRed) {
        if (forcedLog.length < 50) forcedLog.push({ t: simT, id: v.id, scr: v._scr, seg: segs[v._route.seg[v._ri]].id, why: v._why, zr: v._zr, zb: v._zb, ov: v._ovid, x: v.x, y: v.y });
        v._dead = true;
        removeAt(i);
        stats.forcedRemovals++;
      }
    }

    visible = 0;
    for (const v of vehicles) if (v.vis) visible++;
    buildOcc();
    spawnStep(visible);
    api.time += dt;
  }

  // public signal entries get a back-reference to their controller
  for (const g of segs) for (const st of g.stops) pubSignals[st.pub]._ctrl = st.ctrl;
  for (const p of pubSignals) Object.defineProperty(p, '_ctrl', { enumerable: false, value: p._ctrl, writable: false });

  const api = {
    time: 0,
    vehicles,
    signals: pubSignals,
    stats,
    step,
    get visibleCount() {
      return visible;
    },
    debug() {
      return {
        lanes: segs.map((g) => ({
          id: g.id,
          lane: g.lane,
          conn: g.conn,
          len: g.len,
          source: g.isSource,
          sink: g.isSink,
          next: g.next.map((nx) => ({ id: segs[nx.seg].id, exit: nx.exit, entry: nx.entry })),
          prev: g.prev.map((p) => segs[p].id),
        })),
        skipped: G.skipped,
        conflicts: zones.map((z) => ({ id: z.id, type: z.order ? 'order' : 'lock', a: segs[z.seg[0]].id, b: segs[z.seg[1]].id, ia: z.iv[0], ib: z.iv[1], angle: z.angle, holders: [z.holders[0].map((v) => v.id), z.holders[1].map((v) => v.id)] })),
        junctions: sig.ctrls.map((c) => ({ name: c.name, x: c.x, y: c.y, groups: c.groups, control: `actuated: min ${MIN_GREEN} s, max ${MAX_GREEN} s green, ${YELLOW} s yellow, ${ALL_RED} s all-red`, state: c.state.slice() })),
        stats: { ...stats, alive: vehicles.length, visible },
        spawnFail: { ..._fail },
        forcedLog,
        sources: sources.map((g, i) => ({ id: g.id, ...srcStat[i] })),
        connectors: segs.filter((g) => g.conn).map((g) => ({ id: g.id, pts: Array.from(g.X, (x, i) => [x, g.Y[i], g.Z[i]]) })),
      };
    },
  };

  // initial state: populated road + short warm-up
  initialFill();
  const warm = opts.warmup ?? 20;
  for (let t = 0; t < warm; t += 1 / 30) step(1 / 30);
  api.time = 0;
  for (const v of vehicles) savePrev(v);
  return api;
}

export function _buildForDebug(scene) {
  const G = buildGraph(scene);
  buildSpeedCaps(G.segs);
  const zones = buildZones(G.segs);
  return { ...G, zones };
}
