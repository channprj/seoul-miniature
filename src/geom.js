// 카메라 투영(정사투영 NW45/35°, 0.5 m/px). 식의 정의는 장면 데이터의 camera 항목에 있다.
// occ = 장면의 occlusion 항목(D0_m, step_m): 지도마다 깊이 맵의 기준값·단위가 다르다(경복궁 2060 + v×0.02).
// ps = 픽셀 크기로 그린 것(사람·새 스프라이트, 빛 반경)의 배율. 0.5 m/px 지도가 기준 1, 1 m/px 지도는 0.5.
export function makeProjection(cam, occ = {}) {
  const [W, H] = cam.res;
  const m = cam.m_per_px_screen;
  const D0 = Number.isFinite(occ.D0_m) ? occ.D0_m : 2060, dstep = Number.isFinite(occ.step_m) ? occ.step_m : 0.02;
  const ex = cam.screen_x_axis, ey = cam.screen_y_axis, vd = cam.view_dir, cl = cam.cam_location;
  const camDotVd = cl[0] * vd[0] + cl[1] * vd[1] + cl[2] * vd[2];
  return {
    W, H, m, ex, ey, vd, cx: cam.cx, cy: cam.cy, camDotVd, D0, dstep, ps: 0.5 / m,
    decodeDepth: (r, g) => decodeDepth(r, g, D0, dstep),
    // 로컬 (x,y,z) m → out[0]=px, out[1]=py (연속 좌표), out[2]=깊이 m
    project(x, y, z, out) {
      out[0] = (x * ex[0] + y * ex[1] + z * ex[2] - cam.cx) / m + W / 2;
      out[1] = H / 2 - (x * ey[0] + y * ey[1] + z * ey[2] - cam.cy) / m;
      out[2] = x * vd[0] + y * vd[1] + z * vd[2] - camDotVd;
      return out;
    },
  };
}

// 배경 깊이 디코드: v = R*256+G, depth = D0 + v*step, v=65535 → 지오메트리 없음(Infinity)
export function decodeDepth(r, g, D0 = 2060, step = 0.02) {
  const v = r * 256 + g;
  return v === 65535 ? Infinity : D0 + v * step;
}

// 폴리라인 누적 길이
export function cumLengths(pts) {
  const c = new Float32Array(pts.length);
  for (let i = 1; i < pts.length; i++) {
    c[i] = c[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  }
  return c;
}

// 거리 d 에서의 점(선형 보간). out=[x,y,z]
export function pointAt(pts, cum, d, out) {
  const L = cum[cum.length - 1];
  if (d <= 0) { out[0] = pts[0][0]; out[1] = pts[0][1]; out[2] = pts[0][2] || 0; return out; }
  if (d >= L) { const p = pts[pts.length - 1]; out[0] = p[0]; out[1] = p[1]; out[2] = p[2] || 0; return out; }
  let lo = 0, hi = cum.length - 1;
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (cum[mid] <= d) lo = mid; else hi = mid; }
  const t = (d - cum[lo]) / (cum[hi] - cum[lo] || 1);
  const a = pts[lo], b = pts[hi];
  out[0] = a[0] + (b[0] - a[0]) * t; out[1] = a[1] + (b[1] - a[1]) * t; out[2] = (a[2] || 0) + ((b[2] || 0) - (a[2] || 0)) * t;
  return out;
}

export function hash01(n) {
  let t = (n + 0x6d2b79f5) | 0;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}

// 스프라이트 아틀라스는 지도 px(0.5 m)의 2배 해상도(0.25 m/px)로 그린다. 배경 그림의 픽셀 크기와 같다.
export const SPRITE_SCALE = 2;
