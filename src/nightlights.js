// 룩 2 야간 정적 광원. classes.png(의미 클래스)와 가로등 목록에서 한 번 만든다.
// 반환: Float32Array [x, y(광원 바닥, 지도 px), 반경(지도 px), r, g, b, 높이(m)] × n → render.setStaticLights
// 클래스: 2 도로, 4 수면, 7 건물 벽, 9 궁궐 벽, 11 보행로
import { hash01 } from './geom.js';

// 광화문·근정전·경회루(tour.js PLACES 좌표): 가까운 궁궐 벽 밑동은 아래에서 위로 씻는 업라이트로 키운다
const LANDMARKS = [[850, 1225, 70], [1215, 985, 80], [1275, 800, 70]];

// palace: 궁궐 로컬 경계 [x0, y0, x1, y1](m). proj 로 지도 px → 지면(z=0) 로컬 좌표를 구해 골목등을 궁 안에서 뺀다.
export function buildStaticLights({ w, h, cls }, lamps, proj, palace) {
  const inPalace = (x, y) => {
    if (!proj || !palace) return false;
    const u = (x + 0.5 - proj.W / 2) * proj.m + proj.cx, v = (proj.H / 2 - y - 0.5) * proj.m + proj.cy;
    const t = -v * proj.ey[2] / proj.vd[2];
    const lx = u * proj.ex[0] + v * proj.ey[0] + t * proj.vd[0], ly = u * proj.ex[1] + v * proj.ey[1] + t * proj.vd[1];
    return lx > palace[0] && lx < palace[2] && ly > palace[1] && ly < palace[3];
  };
  const out = [];
  const put = (x, y, r, c, k, hgt) => out.push(x, y, r, c[0] * k, c[1] * k, c[2] * k, hgt);
  const AMBER = [1.0, 0.62, 0.28], LAMP = [0.98, 0.66, 0.32], WIN = [0.95, 0.80, 0.58];
  // 가로등: 차선 따라 이미 있는 것. 반경을 넉넉히, 높이 6 m
  for (let i = 0; i < lamps.length; i += 3) put(lamps[i], lamps[i + 1], lamps[i + 2] * 1.35, LAMP, 1.0, 6);
  const at = (x, y) => (x < 0 || y < 0 || x >= w || y >= h ? 0 : cls[y * w + x]);
  const seen = new Set();
  // 벽 밑동(벽 픽셀 바로 아래가 벽·지붕이 아닌 곳)을 열 간격으로 훑는다
  for (let x = 2; x < w - 2; x += 3) {
    for (let y = 1; y < h - 2; y++) {
      const k = at(x, y);
      if (k !== 9 && k !== 7) continue;
      const below = at(x, y + 1);
      if (below === k || below === 6 || below === 7 || below === 8 || below === 9) continue;
      if (k === 9) {
        // 궁궐 회랑·전각 처마 밑 호박색 간접 조명(높이 2.5 m → 지붕 위로는 안 오른다)
        const cell = `9:${(x / 7) | 0}:${(y / 5) | 0}`;
        if (seen.has(cell)) continue;
        seen.add(cell);
        let lm = 0;
        for (const [lx, ly, lr] of LANDMARKS) if ((x - lx) ** 2 + (y - ly) ** 2 < lr * lr) lm = 1;
        if (lm) put(x, y + 2, 24, AMBER, 0.5, 1.0);       // 업라이트: 바닥에서 벽을 씻는다
        else put(x, y + 2, 15, AMBER, 0.4, 2.5);
      } else if (below === 2 || below === 11 || below === 1) {
        // 도심 건물 창 불빛이 앞 보도·도로에 떨어지는 옅은 빛(듬성듬성)
        const cell = `7:${(x / 12) | 0}:${(y / 8) | 0}`;
        if (seen.has(cell) || hash01(x * 7919 + y) < 0.45) continue;
        seen.add(cell);
        put(x, y + 3, 14, WIN, 0.22, 3);
      }
    }
  }
  // 골목 보안등: 가로등이 없는 좁은 길·보행로(서촌·북촌 골목)에 듬성듬성. 궁궐 마당 근처는 뺀다.
  const CW = 26, CH = 16, gw = Math.ceil(w / CW), gh = Math.ceil(h / CH);
  const lit = new Uint8Array(gw * gh);
  for (let i = 0; i < lamps.length; i += 3) {
    const cx = (lamps[i] / CW) | 0, cy = (lamps[i + 1] / CH) | 0;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const x = cx + dx, y = cy + dy;
      if (x >= 0 && y >= 0 && x < gw && y < gh) lit[y * gw + x] = 1;
    }
  }
  for (let cy = 0; cy < gh; cy++) for (let cx = 0; cx < gw; cx++) {
    if (lit[cy * gw + cx] || hash01(cy * 4099 + cx) < 0.35) continue;
    const x0 = cx * CW, y0 = cy * CH;
    if (at(x0, y0) === 5 || at(x0 + CW - 1, y0 + CH - 1) === 5 || at(x0 + CW - 1, y0) === 5 || at(x0, y0 + CH - 1) === 5) continue;
    let hit = -1;
    for (let k = 0; k < 12 && hit < 0; k++) {
      const x = x0 + ((hash01(cx * 31 + cy * 977 + k) * CW) | 0), y = y0 + ((hash01(cx * 131 + cy * 17 + k * 7) * CH) | 0);
      const c = at(x, y);
      if (c !== 2 && c !== 11) continue;
      // 좁은 길만(양옆 가까이에 건물): 광장·넓은 마당엔 안 둔다
      const near = (dx, dy) => { const k = at(x + dx, y + dy); return k === 6 || k === 7 || k === 8; };
      if ((near(-7, 0) || near(-4, -3)) && (near(7, 0) || near(4, 3) || near(0, 5))) hit = y * w + x;
    }
    if (hit >= 0 && !inPalace(hit % w, (hit / w) | 0)) put(hit % w, (hit / w) | 0, 17, [1.0, 0.72, 0.42], 0.6, 4);
  }
  return new Float32Array(out);
}
