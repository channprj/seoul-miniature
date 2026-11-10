// 새: 광장·궁궐 마당의 비둘기 무리(앉아 있다가 포인터가 다가오거나 가끔 저절로 날아올라 한 바퀴 돌고 제자리에 내려앉음),
// 물가·숲 위를 천천히 도는 백로·까치. 그림 위치를 손으로 찍지 않고 classes.png 만 보고 고정 시드로 배치한다(그림을 다시 그려도 동작).
// 로직(배치·상태)은 DOM 없이 돈다 → node --test(test/birds.test.js). 그리기는 emitBirds.
import { hash01 } from './geom.js';

const TAU = Math.PI * 2;
export const CLS = { WATER: 4, COURT: 5, TREE: 10, PLAZA: 11 };
export const isGround = (c) => c === CLS.COURT || c === CLS.PLAZA;   // 비둘기가 앉는 곳: 궁궐 마당·보행 광장
const sm = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

// mulberry32. 상태를 객체에 들고 있어야 무리마다 독립적이고 스냅숏 비교가 된다.
export function nextRand(o) {
  o.rs = (o.rs + 0x6d2b79f5) | 0;
  let t = Math.imul(o.rs ^ (o.rs >>> 15), 1 | o.rs);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}

// grid = { w, h, cls: Uint8Array(w*h) } (지도 px, 0.5 m)
export function planBirds(grid, { seed = 11, flocks = 12, loners = 3, minGap = 110 } = {}) {
  const { w, h, cls } = grid;
  const R = { rs: seed | 0 }, rnd = () => nextRand(R);
  const at = (x, y) => (x < 0 || y < 0 || x >= w || y >= h ? 0 : cls[y * w + x]);
  const allIn = (x, y, r, f) => { for (let dy = -r; dy <= r; dy++) for (let dx = -r; dx <= r; dx++) if (!f(at(x + dx, y + dy))) return false; return true; };
  const frac = (x, y, r, f) => {
    let n = 0, k = 0;
    for (let dy = -r; dy <= r; dy += 2) for (let dx = -r; dx <= r; dx += 2) { k++; if (f(at(x + dx, y + dy))) n++; }
    return n / k;
  };
  const far = (list, x, y, gap) => list.every((s) => Math.hypot((s.cx ?? s.x) - x, (s.cy ?? s.y) - y) >= gap);

  // ── 비둘기 무리: 넓은 마당·광장 한가운데(가장자리·도로 옆 피함)
  const out = { flocks: [], loners: [] };
  for (let t = 0; t < 8000 && out.flocks.length < flocks; t++) {
    const x = Math.floor(rnd() * w), y = Math.floor(rnd() * h);
    if (!isGround(at(x, y)) || !allIn(x, y, 4, isGround) || frac(x, y, 12, isGround) < 0.85 || !far(out.flocks, x, y, minGap)) continue;
    const n = 5 + Math.floor(rnd() * 8);
    const birds = [];
    for (let b = 0, tries = 0; b < n && tries < 200; tries++) {
      const ang = rnd() * TAU, rad = 1.5 + rnd() * 8;
      const hx = Math.round((x + Math.cos(ang) * rad) * 2) / 2, hy = Math.round((y + Math.sin(ang) * rad * 0.6) * 2) / 2;
      // 앉는 자리 주변 5×5 가 모두 땅이어야 한다(제자리 종종걸음 ±1 그림 px 도 땅 위)
      if (!allIn(Math.floor(hx), Math.floor(hy), 2, isGround)) continue;
      if (birds.some((o) => Math.abs(o.hx - hx) < 1 && o.hy === hy)) continue;
      const fa = rnd() * TAU, fr = 2 + rnd() * 7;
      birds.push({ hx, hy, face: rnd() < 0.5 ? -1 : 1, vis: rnd(), lag: rnd() * 0.6, ox: Math.cos(fa) * fr, oy: Math.sin(fa) * fr, bob: rnd() * TAU, flap: rnd(), id: out.flocks.length * 64 + b });
      b++;
    }
    if (birds.length >= 3) out.flocks.push({ x, y, r: 10, birds });
  }

  // ── 외톨이 새: 백로는 물 위(물가 숲 근처), 까치는 숲 위를 천천히 돈다
  const want = [];
  for (let i = 0; i < loners; i++) want.push(i % 3 === 2 ? 'magpie' : 'egret');
  for (const type of want) {
    for (let t = 0; t < 20000; t++) {
      const x = Math.floor(rnd() * w), y = Math.floor(rnd() * h);
      const ok = type === 'egret'
        ? at(x, y) === CLS.WATER && frac(x, y, 16, (c) => c === CLS.WATER) > 0.3 && frac(x, y, 40, (c) => c === CLS.TREE) > 0.05
        : at(x, y) === CLS.TREE && frac(x, y, 20, (c) => c === CLS.TREE) > 0.45;
      if (!ok || !far(out.loners, x, y, 300)) continue;
      out.loners.push({ type, cx: x, cy: y, rx: 26 + rnd() * 26, alt: 7 + rnd() * 7, w: (TAU / (28 + rnd() * 16)) * (rnd() < 0.5 ? -1 : 1), ph: rnd() * TAU, flap: rnd(), vis: rnd() * 0.5 });
      break;
    }
  }
  return out;
}

// opts.depthAt(x, y): 지도 px 의 배경 깊이(m). 테스트에서는 생략.
export function createBirds(grid, opts = {}) {
  const seed = opts.seed ?? 11;
  const plan = planBirds(grid, opts);
  const depthAt = opts.depthAt || (() => 2500);
  const flocks = plan.flocks.map((f, i) => {
    const fl = { ...f, i, state: 'ground', u: 0, T: 0, path: null, cool: 0, rs: (seed * 7919 + i * 104729) | 0, d: depthAt(f.x, f.y) };
    fl.next = 25 + nextRand(fl) * 130;
    for (const b of fl.birds) b.d = depthAt(Math.floor(b.hx), Math.floor(b.hy));
    return fl;
  });
  const loners = plan.loners.map((l) => ({ ...l, d: depthAt(l.cx, l.cy) }));
  const MAX_LAG = 0.6;

  function launch(f) {
    if (f.state !== 'ground') return false;
    const r = () => nextRand(f);
    f.state = 'flying'; f.u = 0; f.T = 8 + r() * 6;
    f.path = { rx: 30 + r() * 45, dir: r() < 0.5 ? -1 : 1, a0: r() * TAU, alt: 12 + r() * 12, wob: r() * TAU };
    return true;
  }
  function land(f) {
    f.state = 'ground'; f.u = 0; f.path = null; f.cool = 2; f.next = 40 + nextRand(f) * 120;
  }

  const sys = {
    flocks, loners, time: 0,
    step(dt) {
      sys.time += dt;
      for (const f of flocks) {
        if (f.state === 'ground') {
          f.cool = Math.max(0, f.cool - dt); f.next -= dt;
          if (f.next <= 0) launch(f);
        } else {
          f.u += dt;
          if (f.u >= f.T + MAX_LAG) land(f);
        }
      }
    },
    // 포인터·탭이 무리 근처(r 지도 px)에 오면 날아오른다. 내려앉은 직후 2초는 무시(앉는 모습이 보이게).
    scare(x, y, r = 12) {
      let n = 0;
      for (const f of flocks) if (f.state === 'ground' && f.cool <= 0 && Math.hypot(f.x - x, f.y - y) < r + f.r && launch(f)) n++;
      return n;
    },
    launch(i) { return launch(flocks[i]); },
    // 새 한 마리의 자세. out = { x, y (지면 위치, 지도 px), alt (m), flying, frame (0 날개 위, 1 아래, 2 활공, 3 쪼기) }
    pose(f, b, out = {}) {
      if (f.state === 'ground') {
        // 제자리 종종걸음·쪼기: 시간 칸(2.3초)마다 해시로 고른다 → 상태 없이 결정론적
        const k = Math.floor((sys.time + b.flap * 13) / 2.3);
        const hh = hash01(b.id * 977 + k);
        out.x = b.hx + (hh < 0.15 ? -0.5 : hh < 0.3 ? 0.5 : 0); out.y = b.hy; out.alt = 0; out.flying = false;
        out.frame = hash01(b.id * 31 + k * 7 + 3) < 0.3 ? 3 : 0;
        return out;
      }
      const p = f.path, T = f.T;
      const ub = Math.min(T, Math.max(0, f.u - b.lag));
      const blend = sm(0, 1.3, ub) * (1 - sm(T - 1.8, T, ub));
      const ang = p.a0 + p.dir * (TAU * 1.15 / T) * ub;
      // 지면 원은 35° 시점에서 세로로 눌린다(0.57). 흔들림 항으로 고르지 않은 고리.
      const tx = f.x + p.rx * (Math.cos(ang) - Math.cos(p.a0)) + 6 * Math.sin(ub * 0.9 + p.wob);
      const ty = f.y + p.rx * 0.57 * (Math.sin(ang) - Math.sin(p.a0));
      const sp = 0.7 + 0.3 * Math.sin(ub * 1.3 + b.bob);
      out.x = b.hx + (tx + b.ox * sp - b.hx) * blend;
      out.y = b.hy + (ty + b.oy * 0.6 * sp - b.hy) * blend;
      out.alt = (p.alt + 0.6 * Math.sin(ub * 2.1 + b.bob)) * blend;
      out.flying = blend > 0;
      const flapping = ub < 2.5 || ub > T - 2.5 || Math.sin(ub * 0.9 + b.bob) > -0.2;
      out.frame = !out.flying ? 0 : flapping ? (Math.floor(ub * 7 + b.flap * 2) & 1) : 2;
      return out;
    },
    lonerPose(l, out = {}) {
      const a = l.ph + l.w * sys.time;
      out.x = l.cx + l.rx * Math.cos(a) + 0.3 * l.rx * Math.sin(2 * a);
      out.y = l.cy + l.rx * 0.57 * Math.sin(a);
      out.alt = l.alt + 1.5 * Math.sin(0.7 * sys.time + l.ph);
      out.flying = true;
      // 백로는 느린 날갯짓, 까치는 날갯짓과 활공을 번갈아
      const slow = l.type === 'egret' ? 2.6 : 5;
      const glide = Math.sin(sys.time * 0.5 + l.ph) < (l.type === 'egret' ? -0.4 : 0);
      out.frame = glide ? 2 : Math.floor(sys.time * slow + l.flap * 2) & 1;
      return out;
    },
    snapshot() {
      const P = {};
      return { time: sys.time, flocks: flocks.map((f) => ({ state: f.state, u: f.u, next: f.next, rs: f.rs, birds: f.birds.map((b) => { sys.pose(f, b, P); return [P.x, P.y, P.alt, P.frame]; }) })) };
    },
  };
  return sys;
}

// ── 그리기. 팔레트 번호는 render.js 의 kind 6 와 같은 순서.
export const BIRD_COLORS = ['pigeon', 'pigeonDark', 'pigeonLight', 'egret', 'magpie', 'magpieWhite'];
const C = { B: 0, D: 1, L: 2, W: 3, K: 4, M: 5 };
// 프레임: 0 날개 위, 1 날개 아래, 2 활공 (위 줄부터)
const SHAPES = {
  pigeon: [['B.B', '.D.'], ['.D.', 'B.B'], ['BDB']],   // 밝은 마당 위에서 보이게 날개도 중간 회색
  egret: [['W..W', '.WW.'], ['.WW.', 'W..W'], ['WWWW']],
  magpie: [['M..M', '.KK.'], ['.KK.', 'K..K'], ['MKKM']],
};
const P = {};

// o: { day, F(합성 배율), kH(고도 1 m 당 화면 px), kD(지도 px 한 줄 아래로 갈 때 지면 깊이 변화 m), vdz(시선의 z 성분) }
export function emitBirds(R, sys, o) {
  const keep = sm(0.15, 0.55, o.day);          // 밤에는 둥지로(안 보임)
  if (keep <= 0) return;
  const S = 0.5;                                 // 그림 1px = 지도 0.5 px
  const snap = (v) => Math.round(v * 2) / 2;
  // 실제 깊이: 기준 지면 깊이 + 화면 줄 차이만큼의 평지 깊이 차 + 고도(시선 방향 성분). 높이 나는 새는 자연히 지붕보다 앞.
  const depthOf = (d0, y0) => d0 + (P.y - y0) * o.kD + P.alt * o.vdz;
  const px = (x, y, dep, col) => R.sprite(x, y, S, S, 0, 0, dep - 0.3, 6, col);
  // 축소 화면(1배 합성)에서는 반 px 사각형이 래스터에서 빠질 수 있어 지도 1px 점 하나로 그린다
  const dot = (x, y, dep, col) => R.sprite(Math.round(x), Math.round(y) - 1, 1, 1, 0, 0, dep - 0.3, 6, col);
  // 깊은 단계(R.hi): 그 해상도로 그린 새 한 장(kind 9). 자리·크기는 그림 px 판과 같다.
  const hi = o.F >= 4 ? R.hi : null, q = hi ? hi.SS : 2;
  const sn = (v) => Math.round(v * q) / q;
  const flyer = (shape, col, dep, type = 'pigeon') => {
    const sy = P.y - P.alt * o.kH;
    if (o.F === 1) { dot(P.x, sy, dep, col); return; }
    if (hi) {
      const f = hi.birds[type][P.frame];
      R.sprite(snap(P.x) - Math.floor(f.bw / 2) * S, snap(sy) - 2 * S, f.w, f.h, f.src[0], f.src[1], dep - 0.3, 9);
      R.shadow(sn(P.x) + 0.05, sn(P.y) + 0.1, 0.4, 0.25, 0, 0, dep, 3);
      return;
    }
    const wd = shape[0].length, bx = snap(P.x) - Math.floor(wd / 2) * S, by = snap(sy) - shape.length * S;
    shape.forEach((row, r) => { for (let i = 0; i < wd; i++) if (row[i] !== '.') px(bx + i * S, by + r * S, dep, C[row[i]]); });
    R.shadow(snap(P.x), snap(P.y), S, S, 0, 0, dep, 3);   // 새보다 먼 면에만 그림자가 진다(지붕 위 포함)
  };
  for (const f of sys.flocks) for (const b of f.birds) {
    if (b.vis > keep) continue;
    sys.pose(f, b, P);
    if (P.flying) { flyer(SHAPES.pigeon[P.frame], C.B, depthOf(b.d, b.hy)); continue; }
    // 앉은 비둘기: 몸 1px + 머리 1px(쪼는 중이면 머리 숨김), 발밑 그림자 1px
    const x = snap(P.x), y = snap(P.y);
    if (o.F === 1) { dot(x, y, b.d, C.D); continue; }
    if (hi) {
      const f = hi.birds.sit[(b.face > 0 ? 2 : 0) + (P.frame === 3 ? 1 : 0)];
      R.sprite(x - 0.25, y - 1, f.w, f.h, f.src[0], f.src[1], b.d - 0.3, 9);
      R.shadow(sn(P.x) - 0.1, sn(P.y), 0.5, 0.25, 0, 0, b.d, 3);
      continue;
    }
    px(x, y - S, b.d, C.B);
    if (P.frame !== 3) px(x + b.face * S, y - S, b.d, C.D);
    R.shadow(x, y, S, S, 0, 0, b.d, 3);
  }
  for (const l of sys.loners) {
    if (l.vis > keep) continue;
    sys.lonerPose(l, P);
    flyer(SHAPES[l.type][P.frame], l.type === 'egret' ? C.W : C.K, depthOf(l.d, l.cy), l.type);
  }
}
