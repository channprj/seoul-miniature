// 차량 스프라이트를 실행 시점에 직접 그린다(외부 그림 파일 없음).
// 상자 몇 개로 된 차 모형을 지도와 같은 카메라(정사투영, 0.25 m/px)로 32방향 래스터화한다.
// 배경과 픽셀 크기가 같아야 픽셀아트로 읽히므로 안티에일리어싱 없이 픽셀 중심 판정으로 채운다.
import { SPRITE_SCALE as SS } from './geom.js';

// 칸 크기와 기준점은 아틀라스 px(0.25 m). 프레임 정보는 지도 px 로 내보낸다.
const CELL_W = 80, CELL_H = 64, AX = 40, AY = 42, HEADINGS = 32;
const GLASS = [58, 78, 98], TYRE = [30, 30, 34];

const rgb = (hex) => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
const mul = (c, k) => [Math.min(255, c[0] * k), Math.min(255, c[1] * k), Math.min(255, c[2] * k)];

// 차종별 상자 목록: [x0, x1, y0, y1, z0, z1, 윗면색, 옆면색]. x 앞, y 왼쪽, z 위 (m), 차 중심 기준.
function parts(kind, color, L, Wd, Hh) {
  const c = rgb(color), hl = L / 2, hw = Wd / 2;
  const roof = mul(c, 1.12);
  const out = [[-hl + 0.3, hl - 0.3, -hw, hw, 0, 0.4, TYRE, TYRE]];
  if (kind === 'bus') {
    out.push([-hl, hl, -hw, hw, 0.35, 1.45, c, c]);
    out.push([-hl, hl, -hw, hw, 1.45, 2.45, GLASS, GLASS]);
    out.push([-hl, hl, -hw, hw, 2.45, Hh, roof, c]);
    out.push([-hl * 0.5, hl * 0.2, -hw * 0.5, hw * 0.5, Hh, Hh + 0.25, [214, 216, 214], [150, 152, 150]]);
    return out;
  }
  const hb = kind === 'van' ? Hh * 0.5 : kind === 'suv' ? Hh * 0.55 : Hh * 0.58;
  out.push([-hl, hl, -hw, hw, 0.3, hb, c, c]);
  const cab = kind === 'van' ? [-hl + 0.1, hl * 0.55] : kind === 'suv' ? [-hl + 0.25, hl * 0.35] : [-hl * 0.55, hl * 0.3];
  out.push([cab[0], cab[1], -hw + 0.12, hw - 0.12, hb, Hh, roof, GLASS]);
  if (kind === 'taxi') out.push([-0.25, 0.25, -0.35, 0.35, Hh, Hh + 0.3, [250, 232, 120], [200, 180, 80]]);
  return out;
}

export function buildVehicleAtlas(scene, proj) {
  const combos = [...new Set(scene.vehicle_atlas.frames.map((f) => f.kind + '|' + f.color))];
  const W = CELL_W * HEADINGS, H = CELL_H * combos.length;
  const veh = new ImageData(W, H), dep = new ImageData(W, H), shd = new ImageData(W, H);
  const { ex, ey, vd, m } = proj;
  const frames = [];

  // 볼록 다각형(화면 px)을 칸 안에 채운다
  const fill = (img, ox, oy, poly, col) => {
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    for (const p of poly) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]); }
    // 1 px 보다 얇은 면도 한 줄은 찍히도록 살짝 부풀린다
    const n = poly.length;
    let area = 0;
    for (let i = 0; i < n; i++) { const a = poly[i], b = poly[(i + 1) % n]; area += a[0] * b[1] - b[0] * a[1]; }
    const sgn = area >= 0 ? 1 : -1;
    for (let y = Math.max(0, Math.floor(y0)); y <= Math.min(CELL_H - 1, Math.ceil(y1)); y++) {
      for (let x = Math.max(0, Math.floor(x0)); x <= Math.min(CELL_W - 1, Math.ceil(x1)); x++) {
        const cx = x + 0.5, cy = y + 0.5;
        let inside = true;
        for (let i = 0; i < n && inside; i++) {
          const a = poly[i], b = poly[(i + 1) % n];
          if (sgn * ((b[0] - a[0]) * (cy - a[1]) - (b[1] - a[1]) * (cx - a[0])) < -0.35) inside = false;
        }
        if (!inside) continue;
        const o = ((oy + y) * W + ox + x) * 4;
        img.data[o] = col[0]; img.data[o + 1] = col[1]; img.data[o + 2] = col[2]; img.data[o + 3] = 255;
      }
    }
  };

  combos.forEach((key, row) => {
    const [kind, color] = key.split('|');
    const [L, Wd, Hh] = scene.vehicle_specs[kind];
    const boxes = parts(kind, color, L, Wd, Hh);
    for (let h = 0; h < HEADINGS; h++) {
      const th = (2 * Math.PI * h) / HEADINGS, c = Math.cos(th), s = Math.sin(th);
      const ox = h * CELL_W, oy = row * CELL_H;
      // 차 좌표 (x 앞, y 왼쪽, z) → 칸 안의 화면 px
      const scr = (x, y, z) => {
        const wx = c * x - s * y, wy = s * x + c * y;
        return [AX + (wx * ex[0] + wy * ex[1] + z * ex[2]) / m * SS, AY - (wx * ey[0] + wy * ey[1] + z * ey[2]) / m * SS];
      };
      // 그림자: 바닥 윤곽을 오른쪽 아래로 조금 민 것
      const hl = L / 2, hw = Wd / 2;
      const foot = [scr(-hl, -hw, 0), scr(hl, -hw, 0), scr(hl, hw, 0), scr(-hl, hw, 0)];
      fill(shd, ox, oy, foot.map((p) => [p[0] + 1.2 * SS, p[1] + 1.0 * SS]), [255, 255, 255]);
      fill(shd, ox, oy, foot, [255, 255, 255]);
      for (const [x0, x1, y0, y1, z0, z1, top, side] of boxes) {
        // 옆면 4개: 법선이 카메라를 향하는 것만
        const faces = [
          [[1, 0], [[x1, y0], [x1, y1]]], [[-1, 0], [[x0, y1], [x0, y0]]],
          [[0, 1], [[x1, y1], [x0, y1]]], [[0, -1], [[x0, y0], [x1, y0]]],
        ];
        for (const [nrm, [a, b]] of faces) {
          const nx = c * nrm[0] - s * nrm[1], ny = s * nrm[0] + c * nrm[1];
          if (nx * vd[0] + ny * vd[1] >= 0) continue;
          const lit = nx * ex[0] + ny * ex[1] < 0 ? 0.84 : 0.62;
          fill(veh, ox, oy, [scr(a[0], a[1], z0), scr(b[0], b[1], z0), scr(b[0], b[1], z1), scr(a[0], a[1], z1)], mul(side, lit));
        }
        fill(veh, ox, oy, [scr(x0, y0, z1), scr(x1, y0, z1), scr(x1, y1, z1), scr(x0, y1, z1)], top);
      }
      // 깊이 코드(128 = 기준 깊이)와 프레임 정보
      for (let y = 0; y < CELL_H; y++) for (let x = 0; x < CELL_W; x++) {
        const o = ((oy + y) * W + ox + x) * 4;
        if (veh.data[o + 3]) { dep.data[o] = 128; dep.data[o + 3] = 255; }
      }
      frames.push({ kind, color, h, frame: [ox, oy, CELL_W / SS, CELL_H / SS], ax: AX / SS, ay: AY / SS, sframe: [ox, oy, CELL_W / SS, CELL_H / SS], sax: AX / SS, say: AY / SS });
    }
  });
  return { veh, vehDepth: dep, vehShadow: shd, frames };
}
