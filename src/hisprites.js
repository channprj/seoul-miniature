// 깊은 확대 단계(z4 0.125 m, z8 0.0625 m)용 스프라이트 아틀라스. 실행 시점에 그 단계 해상도로 다시 래스터화한다.
//   차량: 차종(5) × 32 방향. 색은 굽지 않는다 — r = 재질·면 코드 + 1, g = 그림자(render.js vehMat, kind 7·8). 차체 색은 uVehPal.
//   사람: 팔레트(scene.walker_palette) × 자세 4. 4×9(z2 px) 픽셀 사람과 같은 자리·크기의 벡터 모양을 래스터화 + 1 텍셀 윤곽.
//   새: 비둘기·백로·까치 나는 자세 3 + 앉은 비둘기(좌우·쪼기). 색 그대로(kind 9).
// 한 장(RGBA8, 폭 2048)에 선반 방식으로 채운다. SS = 지도 px(0.5 m) 당 아틀라스 px.
const ATW = 2048, HEADINGS = 32;

// 차 상자: [x0, x1, y0, y1, z0, z1, 윗면 재질, 옆면 재질]. 재질: 0 타이어, 1 차체, 2 지붕(차체×1.12), 3 유리, 4·5 택시 표시등 위·옆, 6·7 버스 지붕 장치 위·옆
// vehicles.js parts() 와 같은 치수(색 대신 재질 번호)
function partsHi(kind, L, Wd, Hh) {
  const hl = L / 2, hw = Wd / 2;
  const out = [[-hl + 0.3, hl - 0.3, -hw, hw, 0, 0.4, 0, 0]];
  if (kind === 'bus') {
    out.push([-hl, hl, -hw, hw, 0.35, 1.45, 1, 1]);
    out.push([-hl, hl, -hw, hw, 1.45, 2.45, 3, 3]);
    out.push([-hl, hl, -hw, hw, 2.45, Hh, 2, 1]);
    out.push([-hl * 0.5, hl * 0.2, -hw * 0.5, hw * 0.5, Hh, Hh + 0.25, 6, 7]);
    return out;
  }
  if (kind === 'truck') {   // vehicles.js 와 같은 치수. 짐칸 상자는 밝은 회색(재질 6)
    out.push([hl - 1.7, hl, -hw, hw, 0.3, 1.45, 1, 1]);
    out.push([hl - 1.55, hl - 0.1, -hw + 0.12, hw - 0.12, 1.45, 2.15, 2, 3]);
    out.push([-hl, hl - 1.8, -hw, hw, 0.75, Hh, 6, 6]);
    return out;
  }
  const hb = kind === 'van' ? Hh * 0.5 : kind === 'suv' ? Hh * 0.55 : Hh * 0.58;
  out.push([-hl, hl, -hw, hw, 0.3, hb, 1, 1]);
  const cab = kind === 'van' ? [-hl + 0.1, hl * 0.55] : kind === 'suv' ? [-hl + 0.25, hl * 0.35] : [-hl * 0.55, hl * 0.3];
  out.push([cab[0], cab[1], -hw + 0.12, hw - 0.12, hb, Hh, 2, 3]);
  if (kind === 'taxi') out.push([-0.25, 0.25, -0.35, 0.35, Hh, Hh + 0.3, 4, 5]);
  return out;
}

// 한 번에 만든다(테스트·오프라인). 앱은 hiSpritesSteps 를 프레임마다 조금씩 돌린다(저사양 휴대폰에서 ×8 은 수백 ms).
export function buildHiSprites(scene, proj, SS) {
  const t0 = performance.now();
  const g = hiSpritesSteps(scene, proj, SS);
  let r;
  do r = g.next(); while (!r.done);
  return Object.assign(r.value, { ms: performance.now() - t0 });
}
// 칸 하나(차 한 방향, 사람 한 자세, 새 한 장)를 그릴 때마다 yield 한다. 끝나면 아틀라스를 돌려준다.
export function* hiSpritesSteps(scene, proj, SS) {
  const { ex, ey, vd, m } = proj;
  const kinds = Object.keys(scene.vehicle_specs);
  // ── 칸 크기 계산(차종마다 32 방향 전체를 담는 상자)
  const cells = [];   // {w, h, draw(img, ox, oy)}
  const shelf = { x: 0, y: 0, h: 0 };
  const place = (w, h) => {
    if (shelf.x + w > ATW) { shelf.x = 0; shelf.y += shelf.h; shelf.h = 0; }
    const o = [shelf.x, shelf.y];
    shelf.x += w; shelf.h = Math.max(shelf.h, h);
    return o;
  };
  const vehFrames = {};
  const vehJobs = [];
  for (const kind of kinds) {
    const [L, Wd, Hh] = scene.vehicle_specs[kind];
    const boxes = partsHi(kind, L, Wd, Hh);
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    for (let h = 0; h < HEADINGS; h++) {
      const th = (2 * Math.PI * h) / HEADINGS, c = Math.cos(th), s = Math.sin(th);
      for (const b of boxes) for (const x of [b[0], b[1]]) for (const y of [b[2], b[3]]) for (const z of [b[4], b[5]]) {
        const wx = c * x - s * y, wy = s * x + c * y;
        const sx = (wx * ex[0] + wy * ex[1] + z * ex[2]) / m * SS, sy = -(wx * ey[0] + wy * ey[1] + z * ey[2]) / m * SS;
        x0 = Math.min(x0, sx); x1 = Math.max(x1, sx + 1.2 * SS); y0 = Math.min(y0, sy); y1 = Math.max(y1, sy + 1.0 * SS);
      }
    }
    const AX = Math.ceil(-x0) + 2, AY = Math.ceil(-y0) + 2, CW = Math.ceil(x1) + AX + 2, CH = Math.ceil(y1) + AY + 2;
    vehFrames[kind] = new Array(HEADINGS);
    for (let h = 0; h < HEADINGS; h++) {
      const [ox, oy] = place(CW, CH);
      vehFrames[kind][h] = { src: [ox, oy], w: CW / SS, h: CH / SS, ax: AX / SS, ay: AY / SS };
      vehJobs.push({ kind, h, ox, oy, CW, CH, AX, AY, boxes, L, Wd });
    }
  }
  // ── 사람(z2 px 4×9 → 4k × 9k)
  // 1 m/px 지도(proj.ps 0.5)에서는 사람·새를 절반 크기로: 같은 SS 에서 칸이 절반이다
  const k = Math.max(1, Math.round(SS / 2 * (proj.ps || 1)));
  const PW = 4 * k, PH = 9 * k;
  const pal = scene.walker_palette;
  const people = new Array(pal.length);
  const peopleJobs = [];
  for (let i = 0; i < pal.length; i++) {
    people[i] = [];
    for (let pose = 0; pose < 4; pose++) { const [ox, oy] = place(PW, PH); people[i].push([ox, oy]); peopleJobs.push({ i, pose, ox, oy }); }
  }
  // ── 새: 나는 자세는 z2 px 로 폭 3(비둘기)·4(백로·까치) × 높이 2, 앉은 비둘기 2×2
  const birds = {};
  const birdJobs = [];
  for (const type of ['pigeon', 'egret', 'magpie']) {
    const bw = type === 'pigeon' ? 3 : 4;
    birds[type] = [0, 1, 2].map((f) => { const [ox, oy] = place(bw * k, 2 * k); birdJobs.push({ type, f, ox, oy, bw }); return { src: [ox, oy], w: bw / 2, h: 1, bw }; });
  }
  birds.sit = [];
  for (const face of [-1, 1]) for (const peck of [0, 1]) { const [ox, oy] = place(2 * k, 2 * k); birdJobs.push({ type: 'sit', face, peck, ox, oy }); birds.sit.push({ src: [ox, oy], w: 1, h: 1, face, peck }); }

  const H = shelf.y + shelf.h;
  const img = new ImageData(ATW, H);
  const D = img.data;
  const put = (x, y, r, g, b, a = 255) => { const o = (y * ATW + x) * 4; D[o] = r; D[o + 1] = g; D[o + 2] = b; D[o + 3] = a; };

  // 차량 래스터화(vehicles.js 와 같은 판정: 텍셀 중심, 0.35 텍셀 부풀림)
  const fill = (ox, oy, CW, CH, poly, cb) => {
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    for (const p of poly) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]); }
    const n = poly.length;
    let area = 0;
    for (let i = 0; i < n; i++) { const a = poly[i], b = poly[(i + 1) % n]; area += a[0] * b[1] - b[0] * a[1]; }
    const sgn = area >= 0 ? 1 : -1;
    // 꼭짓점에 깊이(기준점 대비 m)가 있으면 면 위에서 선형이다 → 텍셀마다 깊이 코드(128 = 기준, 0.1 m 단위)를 함께 넘긴다
    let dA = 0, dB = 0, dC = 0;
    if (poly[0].length > 2) {
      const [p0, p1, p2] = poly, det = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1]);
      if (Math.abs(det) > 1e-9) {
        dA = ((p1[2] - p0[2]) * (p2[1] - p0[1]) - (p2[2] - p0[2]) * (p1[1] - p0[1])) / det;
        dB = ((p2[2] - p0[2]) * (p1[0] - p0[0]) - (p1[2] - p0[2]) * (p2[0] - p0[0])) / det;
      }
      dC = p0[2] - dA * p0[0] - dB * p0[1];
    }
    for (let y = Math.max(0, Math.floor(y0)); y <= Math.min(CH - 1, Math.ceil(y1)); y++) {
      for (let x = Math.max(0, Math.floor(x0)); x <= Math.min(CW - 1, Math.ceil(x1)); x++) {
        const cx = x + 0.5, cy = y + 0.5;
        let inside = true;
        for (let i = 0; i < n && inside; i++) {
          const a = poly[i], b = poly[(i + 1) % n];
          if (sgn * ((b[0] - a[0]) * (cy - a[1]) - (b[1] - a[1]) * (cx - a[0])) < -0.35) inside = false;
        }
        if (inside) cb((oy + y) * ATW + ox + x, Math.max(1, Math.min(255, Math.round(128 + (dA * cx + dB * cy + dC) * 10))));
      }
    }
  };
  for (const { h, ox, oy, CW, CH, AX, AY, boxes, L, Wd } of vehJobs) {
    yield;
    const th = (2 * Math.PI * h) / HEADINGS, c = Math.cos(th), s = Math.sin(th);
    const scr = (x, y, z) => {
      const wx = c * x - s * y, wy = s * x + c * y;
      return [AX + (wx * ex[0] + wy * ex[1] + z * ex[2]) / m * SS, AY - (wx * ey[0] + wy * ey[1] + z * ey[2]) / m * SS, wx * vd[0] + wy * vd[1] + z * vd[2]];
    };
    const hl = L / 2, hw = Wd / 2;
    const foot = [scr(-hl, -hw, 0), scr(hl, -hw, 0), scr(hl, hw, 0), scr(-hl, hw, 0)];
    // 채널: r = 재질·면 코드, g = 그림자, b = 차체 면의 깊이 코드, a = 그림자(지면)의 깊이 코드. 깊이는 차 중심 대비(긴 버스는 앞뒤로 ±5 m 쯤 차이 난다).
    const shadow = (i, dc) => { D[i * 4 + 1] = 255; D[i * 4 + 3] = dc; };
    const kRow = m * ey[2] / vd[2] / SS;   // 화면 한 텍셀 아래로 갈 때 지면 깊이 변화
    fill(ox, oy, CW, CH, foot.map((p) => [p[0] + 1.2 * SS, p[1] + 1.0 * SS, p[2] + kRow * 1.0 * SS]), shadow);
    fill(ox, oy, CW, CH, foot, shadow);
    for (const [x0, x1, y0, y1, z0, z1, top, side] of boxes) {
      const faces = [
        [[1, 0], [[x1, y0], [x1, y1]]], [[-1, 0], [[x0, y1], [x0, y0]]],
        [[0, 1], [[x1, y1], [x0, y1]]], [[0, -1], [[x0, y0], [x1, y0]]],
      ];
      for (const [nrm, [a, b]] of faces) {
        const nx = c * nrm[0] - s * nrm[1], ny = s * nrm[0] + c * nrm[1];
        if (nx * vd[0] + ny * vd[1] >= 0) continue;
        const code = side * 3 + (nx * ex[0] + ny * ex[1] < 0 ? 1 : 2) + 1;
        fill(ox, oy, CW, CH, [scr(a[0], a[1], z0), scr(b[0], b[1], z0), scr(b[0], b[1], z1), scr(a[0], a[1], z1)], (i, dc) => { D[i * 4] = code; D[i * 4 + 2] = dc; if (!D[i * 4 + 3]) D[i * 4 + 3] = 255; });
      }
      const code = top * 3 + 1;
      fill(ox, oy, CW, CH, [scr(x0, y0, z1), scr(x1, y0, z1), scr(x1, y1, z1), scr(x0, y1, z1)], (i, dc) => { D[i * 4] = code; D[i * 4 + 2] = dc; if (!D[i * 4 + 3]) D[i * 4 + 3] = 255; });
    }
  }

  // 사람: z2 px 좌표(u 0..4, v 0..9)의 모양 → 텍셀 중심에서 판정
  const rgb = (hex) => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
  const SKIN = ['#f1c9a5', '#e8b98f', '#d9a57c', '#f6d6b8'].map(rgb);
  const ell = (u, v, cx, cy, rx, ry) => ((u - cx) / rx) ** 2 + ((v - cy) / ry) ** 2 <= 1;
  const seg = (u, v, ax, ay, bx, by, r) => {   // 굵기 2r 선분
    const dx = bx - ax, dy = by - ay, t = Math.max(0, Math.min(1, ((u - ax) * dx + (v - ay) * dy) / (dx * dx + dy * dy)));
    return Math.hypot(u - ax - dx * t, v - ay - dy * t) <= r;
  };
  // 자세: 0·2 다리 벌림(2 는 반대), 1·3 모음. 팔은 다리와 반대로 흔든다.
  const part = (u, v, pose) => {
    const apart = pose === 0 || pose === 2, sw = pose === 0 ? 1 : pose === 2 ? -1 : 0;
    if (ell(u, v, 2, 0.95, 0.82, 0.78) && v < 1.05) return 'H';
    if (ell(u, v, 2, 1.25, 0.74, 0.92)) return v < 1.3 && Math.abs(u - 2) > 0.55 ? 'H' : 'S';
    if (Math.abs(u - 2) < 0.32 && v >= 2.0 && v < 2.4) return 'S';
    // 팔(소매 → 손)
    for (const [side, d] of [[-1, sw], [1, -sw]]) {
      const ax = 2 + side * 1.12, end = 4.35 - 0.3 * d;
      if (seg(u, v, ax, 2.55, ax + side * 0.12, end, 0.3)) return v > end - 0.55 ? 'S' : 'c';
    }
    if (v >= 2.25 && v < 5.25) {
      const hw = v < 2.7 ? 1.25 - (2.7 - v) * 0.9 : 1.25 - (v - 2.7) * 0.06;
      if (Math.abs(u - 2) <= hw) return 'C';
    }
    if (v >= 5.1 && v < 5.8 && Math.abs(u - 2) <= 1.05) return 'P';
    const legs = apart ? [[1.5, 0.95 + 0.15 * sw], [2.5, 3.05 + 0.15 * sw]] : [[1.55, 1.5], [2.45, 2.5]];
    for (const [hx, fx] of legs) {
      if (seg(u, v, hx, 5.4, fx, 8.35, 0.4)) return 'P';
      if (v >= 8.2 && v < 9 && ell(u, v, fx + (fx < 2 ? -0.1 : 0.1), 8.62, 0.5, 0.38)) return 'F';
    }
    return null;
  };
  for (const { i, pose, ox, oy } of peopleJobs) {
    if ((pose & 3) === 0) yield;
    const C = rgb(pal[i][0]), P = rgb(pal[i][1]), Hc = rgb(pal[i][2]), S = SKIN[i % SKIN.length];
    const col = { C, P, H: Hc, S, c: C.map((v) => v * 0.86), F: [44, 40, 46] };
    const g = new Array(PW * PH).fill(null);
    for (let y = 0; y < PH; y++) for (let x = 0; x < PW; x++) {
      const ch = part((x + 0.5) / k, (y + 0.5) / k, pose);
      if (!ch) continue;
      let c = col[ch];
      // 빛: 화면 오른쪽 1/3 은 조금 어둡게(해는 장면 고정 방위)
      if (x >= PW * 0.62 && ch !== 'F') c = c.map((v) => v * 0.86);
      g[y * PW + x] = c;
    }
    for (let y = 0; y < PH; y++) for (let x = 0; x < PW; x++) {
      let c = g[y * PW + x];
      if (!c) {
        // 1 텍셀 윤곽: 옆 텍셀이 몸이면 그 색을 어둡게
        const nb = [[1, 0], [-1, 0], [0, 1], [0, -1]].map(([dx, dy]) => (x + dx >= 0 && x + dx < PW && y + dy >= 0 && y + dy < PH ? g[(y + dy) * PW + x + dx] : null)).find(Boolean);
        if (!nb || k < 2) continue;
        c = nb.map((v) => v * 0.42);
      }
      put(ox + x, oy + y, c[0] | 0, c[1] | 0, c[2] | 0);
    }
  }

  // 새(birds.js BIRD_COLORS 와 같은 색)
  const BC = { B: [128, 135, 153], D: [69, 74, 92], L: [189, 191, 204], W: [245, 245, 237], K: [18, 20, 28], M: [230, 235, 242] };
  const birdPart = (type, f, u, v, bw) => {
    const cx = bw / 2;
    const body = ell(u, v, cx, 1.35, bw * 0.17, 0.32);
    const wing = (tipY) => seg(u, v, cx - 0.2, 1.25, 0.15, tipY, 0.22) || seg(u, v, cx + 0.2, 1.25, bw - 0.15, tipY, 0.22);
    const wings = f === 0 ? wing(0.35) : f === 1 ? wing(1.85) : (v > 1.05 && v < 1.4 && u > 0.1 && u < bw - 0.1);
    if (type === 'pigeon') return body ? 'D' : wings ? 'B' : null;
    if (type === 'egret') return body || wings ? 'W' : null;
    if (body) return 'K';
    if (wings) return Math.abs(u - cx) > bw * 0.3 ? 'M' : 'K';
    return null;
  };
  for (const j of birdJobs) {
    const w = j.type === 'sit' ? 2 * k : j.bw * k, h = 2 * k;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const u = (x + 0.5) / k, v = (y + 0.5) / k;
      let ch = null;
      if (j.type === 'sit') {
        if (ell(u, v, 1, 1.5, 0.72, 0.42)) ch = 'B';
        else if (!j.peck && ell(u, v, 1 + 0.55 * j.face, 0.95, 0.28, 0.3)) ch = 'D';
        else if (j.peck && ell(u, v, 1 + 0.75 * j.face, 1.6, 0.25, 0.22)) ch = 'D';
      } else ch = birdPart(j.type, j.f, u, v, j.bw);
      if (ch) { const c = BC[ch]; put(j.ox + x, j.oy + y, c[0], c[1], c[2]); }
    }
  }
  return { SS, img, vehFrames, people, birds, colors: [...new Set(scene.vehicle_atlas.frames.map((f) => f.color))], bytes: ATW * H * 4 };
}
