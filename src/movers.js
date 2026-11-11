// 보행자·차량 상태를 렌더러 스프라이트로 내보낸다. 장면 데이터(scene.json.gz)의 형식을 따른다.
import { cumLengths, pointAt, hash01, SPRITE_SCALE } from './geom.js';

const TAU = Math.PI * 2;

// 보행자 스프라이트는 실행 시 직접 찍는다(4×9 px, 0.25 m/px → 키 2.25 m 로 조금 과장). 팔레트는 scene.walker_palette 의 [셔츠, 바지, 머리].
export const PERSON = { w: 4, h: 9, cellW: 5, cellH: 10, perRow: 32 };
const SKIN = ['#f1c9a5', '#e8b98f', '#d9a57c', '#f6d6b8'];
const POSES = [
  ['.HH.', '.SS.', 'CCCC', 'CCCC', 'SCCS', '.PP.', '.PP.', 'P..P', 'P..P'],
  ['.HH.', '.SS.', '.CC.', 'CCCC', '.CCS', '.PP.', '.PP.', '.PP.', '.PP.'],
  ['.HH.', '.SS.', 'CCCC', 'CCCC', 'SCCS', '.PP.', '.PP.', 'P..P', '.P.P'],
  ['.HH.', '.SS.', '.CC.', 'CCCC', 'SCC.', '.PP.', '.PP.', '.PP.', '.PP.'],
];
export function buildPeopleAtlas(palette) {
  const rows = Math.ceil(palette.length / PERSON.perRow);
  const W = PERSON.perRow * PERSON.cellW * 4, H = rows * PERSON.cellH;
  const img = new ImageData(W, H);
  const rgb = (hex) => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
  palette.forEach((pal, i) => {
    const col = { C: rgb(pal[0]), P: rgb(pal[1]), H: rgb(pal[2]), S: rgb(SKIN[i % SKIN.length]) };
    const ox = (i % PERSON.perRow) * PERSON.cellW * 4, oy = Math.floor(i / PERSON.perRow) * PERSON.cellH;
    POSES.forEach((pose, pi) => pose.forEach((line, y) => [...line].forEach((ch, x) => {
      if (ch === '.') return;
      const o = ((oy + y) * W + ox + pi * PERSON.cellW + x) * 4;
      const c = col[ch];
      img.data[o] = c[0]; img.data[o + 1] = c[1]; img.data[o + 2] = c[2]; img.data[o + 3] = 255;
    })));
  });
  return img;
}

export function createMovers(scene, proj) {
  const P = [0, 0, 0], Q = [0, 0, 0], S = [0, 0, 0];
  const ex = proj.ex;

  // ── 차량 아틀라스 조회표: kind|color → 32방향 프레임
  const vehFrames = new Map();
  for (const f of scene.vehicle_atlas.frames) {
    const key = f.kind + '|' + f.color;
    if (!vehFrames.has(key)) vehFrames.set(key, new Array(32));
    vehFrames.get(key)[f.h] = f;
  }

  // ── 보행자: 경로를 왕복(끝에서 돌아옴). 16초 한 번이 아니라 계속 걷는다.
  const walkers = scene.walkers.map((w, i) => {
    const cum = cumLengths(w.pts);
    const L = cum[cum.length - 1];
    return { pts: w.pts, cum, L, speed: w.speed_mps * (0.85 + 0.3 * hash01(i * 7 + 1)), phase: hash01(i * 13 + 5) * 2 * L, pal: scene.walker_pal_idx[i], night: hash01(i * 3 + 11) };
  }).filter((w) => w.L > 1);
  const standing = scene.standing.map((s, i) => ({ ...s, night: hash01(i * 5 + 3), sway: hash01(i * 17) * 40 }));

  // ── 가로등: 바깥 차선(lane_k 0)을 따라 일정 간격. 화면 좌표로 미리 계산.
  const lamps = [];
  for (const ln of scene.lanes) {
    if (ln.lane_k !== 0 || ln.length < 20) continue;
    const cum = cumLengths(ln.pts);
    const L = cum[cum.length - 1];
    const gap = ln.highway.startsWith('primary') ? 34 : 42;
    for (let d = gap * 0.5; d < L; d += gap) {
      pointAt(ln.pts, cum, d, P); proj.project(P[0], P[1], P[2], S);
      lamps.push(S[0], S[1], ln.highway.startsWith('primary') ? 30 : 22);
    }
  }

  function emitPeople(R, t, nightAmt) {
    // PSC: 1 m/px 지도에서는 사람을 지도 px 로 절반 크기로 그린다(키 2.25 m 는 같다). 아틀라스 배율은 렌더러가 맞춘다.
    const PSC = proj.ps || 1;
    const SS = SPRITE_SCALE, fw = PERSON.w / SS * PSC, fh = PERSON.h / SS * PSC, foot = (PERSON.h - 1) / SS * PSC;
    const keep = 1 - nightAmt * 0.72;          // 밤에는 사람이 줄어든다
    // 깊은 단계(R.hi: 0.125·0.0625 m 아틀라스)면 그 해상도로 그린 사람을 쓰고 위치도 그 격자에 맞춘다(크기·발 위치는 같다)
    const hi = R.hi, q = hi ? hi.SS : SS;
    const put = (x, y, z, pal, pose) => {
      proj.project(x, y, z, S);
      const dx = Math.round(S[0] * q) / q - fw / 2, dy = Math.round(S[1] * q) / q - foot;
      const c = hi && hi.people[pal] && hi.people[pal][pose];   // 깊은 판이 없는 팔레트·자세는 기본 아틀라스로(kind 1)
      if (c) R.sprite(dx, dy, fw, fh, c[0], c[1], S[2], 10, foot);
      else R.sprite(dx, dy, fw, fh, (pal % PERSON.perRow) * PERSON.cellW * 4 + pose * PERSON.cellW, Math.floor(pal / PERSON.perRow) * PERSON.cellH, S[2], 1, foot);
      R.shadow(dx, dy + foot, fw + 0.5 * PSC, 0.5 * PSC, 0, 0, S[2], 3);
    };
    for (let i = 0; i < walkers.length; i++) {
      const w = walkers[i];
      if (w.night > keep) continue;
      let d = (w.phase + t * w.speed) % (2 * w.L);
      if (d > w.L) d = 2 * w.L - d;
      pointAt(w.pts, w.cum, d, P);
      put(P[0], P[1], P[2], w.pal, Math.floor((w.phase + t * w.speed) / 0.45) & 3);
    }
    for (let i = 0; i < standing.length; i++) {
      const s = standing[i];
      if (s.night > keep) continue;
      put(s.x, s.y, s.z, s.pal, 0);
    }
  }

  function emitVehicles(R, vehicles, alpha, nightAmt) {
    const lightsOn = nightAmt > 0.35;
    const hi = R.hi, q = hi ? hi.SS : 1;
    // 깊은 단계: 전조등·미등 점을 지도 1 px(0.5 m) 대신 0.2 m 점으로
    const dot = (x, y, d, red) => (hi ? R.sprite(Math.round(x * q) / q - 0.2, Math.round(y * q) / q - 0.2, 0.4, 0.4, 0, 0, d, 4, red) : R.sprite(Math.round(x), Math.round(y), 1, 1, 0, 0, d, 4, red));
    for (let i = 0; i < vehicles.length; i++) {
      const v = vehicles[i];
      const x = v.px + (v.x - v.px) * alpha, y = v.py + (v.y - v.py) * alpha, z = v.pz + (v.z - v.pz) * alpha;
      let dth = v.th - v.pth; if (dth > Math.PI) dth -= TAU; else if (dth < -Math.PI) dth += TAU;
      const th = v.pth + dth * alpha;
      const h = ((Math.round(th / (TAU / 32)) % 32) + 32) % 32;
      const fr = vehFrames.get(v.kind + '|' + v.color)?.[h];
      if (!fr) continue;
      proj.project(x, y, z, S);
      const dep = S[2];
      if (hi && hi.vehFrames[v.kind]) {
        // 깊은 단계: 그 해상도로 래스터화한 차종 모형(색은 셰이더가 칠한다)
        const hf = hi.vehFrames[v.kind][h], px = Math.round(S[0] * q) / q, py = Math.round(S[1] * q) / q;
        R.sprite(px - hf.ax, py - hf.ay, hf.w, hf.h, hf.src[0], hf.src[1], dep, 7, hi.colorIx.get(v.color) || 0);
        R.shadow(px - hf.ax, py - hf.ay, hf.w, hf.h, hf.src[0], hf.src[1], dep, 8);
      } else {
        const px = Math.round(S[0] * SPRITE_SCALE) / SPRITE_SCALE, py = Math.round(S[1] * SPRITE_SCALE) / SPRITE_SCALE;
        const f = fr.frame, sf = fr.sframe;
        R.sprite(px - fr.ax, py - fr.ay, f[2], f[3], f[0], f[1], dep, 0);
        R.shadow(px - fr.sax, py - fr.say, sf[2], sf[3], sf[0], sf[1], dep, 2);
      }
      if (lightsOn) {
        const c = Math.cos(th), s = Math.sin(th);
        const hl = v.len * 0.5, hw = v.wid * 0.32, zl = 0.7;
        if (R.look === 2) {
          // 룩 2: 전조등 원뿔(앞으로 갈수록 넓고 옅은 원 셋), 미등 붉은 번짐
          for (const [dd, rr, k] of [[3, 7, 0.9], [8, 12, 0.75], [14, 16, 0.5]]) {
            proj.project(x + c * (hl + dd), y + s * (hl + dd), z, P);
            R.light(P[0], P[1], rr, 0.70 * k, 0.66 * k, 0.52 * k);
          }
          proj.project(x - c * (hl + 1), y - s * (hl + 1), z, P);
          R.light(P[0], P[1], 5, 0.5, 0.06, 0.04);
        } else {
          // 전조등 빛 웅덩이(차 앞 9 m)
          proj.project(x + c * (hl + 8), y + s * (hl + 8), z, P);
          R.light(P[0], P[1], 20, 0.62, 0.58, 0.42);
        }
        // 전조등·미등 점(차체 깊이보다 살짝 앞에 둬서 차체 위에 찍힌다)
        for (let side = -1; side <= 1; side += 2) {
          proj.project(x + c * hl - s * hw * side, y + s * hl + c * hw * side, z + zl, P);
          dot(P[0], P[1], P[2] - 0.8, 0);
          proj.project(x - c * hl - s * hw * side, y - s * hl + c * hw * side, z + zl, P);
          dot(P[0], P[1], P[2] - 0.8, 1);
        }
        if (v.braking) { proj.project(x - c * (hl + 1.5), y - s * (hl + 1.5), z, P); R.light(P[0], P[1], 9, 0.9, 0.12, 0.06); }
      }
    }
  }

  // noLamps: 룩 2 는 가로등을 정적 빛 맵에 한 번 구워 두므로 신호등 빛만 낸다
  function emitLamps(R, signals, noLamps = false) {
    if (!noLamps) for (let i = 0; i < lamps.length; i += 3) R.light(lamps[i], lamps[i + 1], lamps[i + 2], 0.70, 0.48, 0.22);
    if (signals) for (const sg of signals) {
      proj.project(sg.x, sg.y, sg.z || 0, S);
      const c = sg.state === 'g' ? [0.1, 0.8, 0.45] : sg.state === 'y' ? [0.9, 0.7, 0.1] : [0.95, 0.12, 0.08];
      R.light(S[0], S[1], 10, c[0], c[1], c[2]);
    }
  }

  function emitSignals(R, signals) {
    // 신호등: 정지선 옆 2px 점(항상 발광)
    if (!signals) return;
    const q = R.hi ? R.hi.SS : 0;
    for (const sg of signals) {
      proj.project(sg.x, sg.y, (sg.z || 0) + 4.5, S);
      const st = sg.state === 'g' ? 0 : sg.state === 'y' ? 1 : 2;
      // 깊은 단계: 2 px(1 m) 네모 대신 0.4 m 등
      if (q) R.sprite(Math.round(S[0] * q) / q + 0.1, Math.round(S[1] * q) / q + 0.1, 0.8, 0.8, 0, 0, S[2] - 1, 5, st);
      else R.sprite(Math.round(S[0]), Math.round(S[1]), 2, 2, 0, 0, S[2] - 1, 5, st);
    }
  }

  return { emitPeople, emitVehicles, emitLamps, emitSignals, lamps, counts: { walkers: walkers.length, standing: standing.length, lamps: lamps.length / 3 } };
}

// 교통 모듈이 아직 없을 때 쓰는 단순 대체(등속, 차간거리 유지 없음). 디버그용.
export function createFallbackTraffic(scene) {
  const combos = [...new Set(scene.vehicle_atlas.frames.map((f) => f.kind + '|' + f.color))];
  const vehicles = [];
  const P = [0, 0, 0], Q = [0, 0, 0];
  scene.lanes.forEach((ln, li) => {
    if (ln.length < 30) return;
    const cum = cumLengths(ln.pts);
    for (let s = 10 + hash01(li) * 20; s < ln.length - 5; s += 28 + hash01(li * 31 + s) * 30) {
      const [kind, color] = combos[Math.floor(hash01(li * 97 + s) * combos.length)].split('|');
      const sp = scene.vehicle_specs[kind];
      vehicles.push({ id: vehicles.length, kind, color, len: sp[0], wid: sp[1], h: sp[2], lane: li, s, v: 8, cum, x: 0, y: 0, z: 0, th: 0, px: 0, py: 0, pz: 0, pth: 0, braking: false });
    }
  });
  const place = (v) => {
    const ln = scene.lanes[v.lane];
    pointAt(ln.pts, v.cum, v.s, P); pointAt(ln.pts, v.cum, Math.min(ln.length, v.s + 1.5), Q);
    v.x = P[0]; v.y = P[1]; v.z = P[2];
    if (Q[0] !== P[0] || Q[1] !== P[1]) v.th = Math.atan2(Q[1] - P[1], Q[0] - P[0]);
  };
  for (const v of vehicles) { place(v); v.px = v.x; v.py = v.y; v.pz = v.z; v.pth = v.th; }
  return {
    time: 0, vehicles, signals: [],
    step(dt) {
      this.time += dt;
      for (const v of vehicles) {
        v.px = v.x; v.py = v.y; v.pz = v.z; v.pth = v.th;
        v.s += v.v * dt;
        if (v.s > scene.lanes[v.lane].length) { v.s = 0; place(v); v.px = v.x; v.py = v.y; v.pth = v.th; } else place(v);
      }
    },
  };
}
