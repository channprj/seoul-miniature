// 세워 둔 차(움직이지 않는다). 도시 지도(여의도)용. DOM 없음.
// 자리 고르기(classes.png·깊이로만, 좌표를 손으로 찍지 않는다):
//   - 차도(2) 가장자리에서 1.5~4.5 m 들어간 포장(11)·맨땅(1) 칸. 건물 벽·지붕(6·7)·나무(10)·물(4)·잔디(3)는 차체 어디에도 닿지 않는다
//     → 그림에서 건물·나무에 가려지는 자리에는 두지 않는다. 땅 높이도 평평해야 한다(|높이| < 0.5 m: 깊이 그림이 땅과 같다 = 위에 아무것도 없다).
//   - 머리를 차도 쪽으로(직각 주차). 이웃 차와 2.7 m 간격, 차 둘레 1.2 m 안에 걷는 길(walk_paths·강변 띠)이 지나가면 두지 않는다.
//   - 시드 해시로 일부 칸을 비운다(만차가 아니게). 광장·공원 랜드마크 둘레는 비운다.
// 결과: [{ kind, color, len, wid, x, y, z, th, px, py, pz, pth, parked: true }] — movers.emitVehicles 가 그대로 그린다(불 없이).
import { hash01 } from '../geom.js';

export function createParking(scene, grid, { proj, heightAt = () => 0, seed = 3, max = 900, avoid = [], keepOut = [] } = {}) {
  const { w, h, cls } = grid, m = proj.m, ex = proj.ex, ey = proj.ey;
  const det = ex[0] * ey[1] - ex[1] * ey[0];
  const S = [0, 0, 0];
  const toWorld = (px, py) => { const a = (px - proj.W / 2) * m + proj.cx, b = (proj.H / 2 - py) * m + proj.cy; return [(a * ey[1] - b * ex[1]) / det, (b * ex[0] - a * ey[0]) / det]; };
  const pix = (x, y) => { proj.project(x, y, 0, S); const px = Math.floor(S[0]), py = Math.floor(S[1]); return px < 0 || py < 0 || px >= w || py >= h ? -1 : py * w + px; };
  const clsAt = (x, y) => { const o = pix(x, y); return o < 0 ? 0 : cls[o]; };
  const flatAt = (x, y) => { proj.project(x, y, 0, S); const px = Math.floor(S[0]), py = Math.floor(S[1]); return px >= 0 && py >= 0 && px < w && py < h && Math.abs(heightAt(px, py)) < 0.5; };
  // 걷는 길 둘레(2 m 칸)
  const walkCells = new Set(), WK = (x, y) => (Math.floor(x / 2) + 32768) * 65536 + Math.floor(y / 2) + 32768;
  for (const pts of avoid) for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1], b = pts[i], n = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 1));
    for (let k = 0; k <= n; k++) { const x = a[0] + (b[0] - a[0]) * k / n, y = a[1] + (b[1] - a[1]) * k / n; for (let j = -1; j <= 1; j++) for (let i2 = -1; i2 <= 1; i2++) walkCells.add(WK(x + i2 * 1.2, y + j * 1.2)); }
  }
  const nearWalk = (x, y) => walkCells.has(WK(x, y));
  // 고속화도로(trunk·motorway, 진출입로 포함) 둘레 20 m: 도로 사이 녹지·갓길에는 세우지 않는다
  const fast = new Set(), FK = (x, y) => (Math.floor(x / 5) + 32768) * 65536 + Math.floor(y / 5) + 32768;
  for (const ln of scene.lanes) {
    if (!/^(trunk|motorway)/.test(String(ln.highway || ''))) continue;
    for (let i = 1; i < ln.pts.length; i++) {
      const a = ln.pts[i - 1], b = ln.pts[i], n = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 4));
      for (let k = 0; k <= n; k++) { const x = a[0] + (b[0] - a[0]) * k / n, y = a[1] + (b[1] - a[1]) * k / n; for (let j = -4; j <= 4; j++) for (let i2 = -4; i2 <= 4; i2++) if (i2 * i2 + j * j <= 16) fast.add(FK(x + i2 * 5, y + j * 5)); }
    }
  }
  const combos = [...new Set(scene.vehicle_atlas.frames.map((f) => f.kind + '|' + f.color))].filter((c) => /^(sedan|suv|van)\|/.test(c));
  const out = [], occ = new Map(), OK = (x, y) => (Math.floor(x / 2.5) + 32768) * 65536 + Math.floor(y / 2.5) + 32768;
  const free = (x, y) => {
    const k0 = Math.floor(x / 2.5), k1 = Math.floor(y / 2.5);
    for (let j = -2; j <= 2; j++) for (let i = -2; i <= 2; i++) { const l = occ.get((k0 + i + 32768) * 65536 + k1 + j + 32768); if (l) for (const c of l) if (Math.hypot(c.x - x, c.y - y) < 2.65) return false; }
    return true;
  };
  const GOOD = new Set([1, 11]);
  // 차도 가장자리 찾기: 지도 px 를 3 px 간격으로 훑어 차도(2, 지면) 옆 포장 칸을 고른다
  const cand = [];
  for (let py = 4; py < h - 4; py += 3) for (let px = 4; px < w - 4; px += 3) {
    const c0 = cls[py * w + px];
    if (!GOOD.has(c0)) continue;
    const p = toWorld(px + 0.5, py + 0.5);
    if (fast.has(FK(p[0], p[1]))) continue;
    // 8 방향 4.5 m 안의 지면 차도
    let rx = 0, ry = 0, hit = 0, dmin = 9;
    for (let k = 0; k < 16; k++) {
      const a = k * Math.PI / 8, cx = Math.cos(a), cy = Math.sin(a);
      for (let d = 1.5; d <= 4.5; d += 0.5) {
        const x = p[0] + cx * d, y = p[1] + cy * d, cc = clsAt(x, y);
        if (cc === 2 && flatAt(x, y)) { rx += cx; ry += cy; hit++; dmin = Math.min(dmin, d); break; }
        if (!GOOD.has(cc)) break;
      }
    }
    if (!hit || hit > 6 || dmin < 2.2) continue;   // 차도에 둘러싸인 섬(교통섬)은 빼고, 차도에 너무 붙은 칸도 뺀다
    const l = Math.hypot(rx, ry);
    if (l < 0.5) continue;
    cand.push({ x: p[0], y: p[1], th: Math.atan2(ry / l, rx / l), d: dmin, k: hash01(px * 7919 + py * 104729 + seed) });
  }
  cand.sort((a, b) => a.k - b.k);
  const okBody = (x, y, th, len, wid) => {
    const c = Math.cos(th), s = Math.sin(th);
    for (let u = -0.5; u <= 0.5; u += 0.25) for (let v = -0.5; v <= 0.5; v += 0.5) {
      const qx = x + c * u * (len + 0.6) - s * v * (wid + 0.4), qy = y + s * u * (len + 0.6) + c * v * (wid + 0.4);
      if (!GOOD.has(clsAt(qx, qy)) || !flatAt(qx, qy) || nearWalk(qx, qy)) return false;
    }
    return true;
  };
  for (const cd of cand) {
    if (out.length >= max) break;
    if (cd.k > 0.62) break;   // 자리의 38 % 는 비운다
    if (keepOut.some((q) => Math.hypot(cd.x - q[0], cd.y - q[1]) < q[2])) continue;
    const combo = combos[Math.floor(hash01(out.length * 31 + seed * 7) * combos.length)];
    const [kind, color] = combo.split('|'), sp = scene.vehicle_specs[kind];
    // 머리를 차도 쪽으로, 앞 범퍼가 차도 가장자리 0.6 m 앞에 오게
    const cx = cd.x + Math.cos(cd.th) * (cd.d - 0.6 - sp[0] / 2), cy = cd.y + Math.sin(cd.th) * (cd.d - 0.6 - sp[0] / 2);
    if (!free(cx, cy) || !okBody(cx, cy, cd.th, sp[0], sp[1])) continue;
    const v = { id: out.length, kind, color, len: sp[0], wid: sp[1], h: sp[2], x: cx, y: cy, z: 0, th: cd.th, px: cx, py: cy, pz: 0, pth: cd.th, braking: false, parked: true };
    out.push(v);
    const k = OK(cx, cy); let l = occ.get(k); if (!l) occ.set(k, l = []); l.push(v);
  }
  return out;
}
