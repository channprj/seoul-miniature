// 사람·소품·말풍선 그리기. 행동 로직은 src/sim/people.js(DOM 없음), 여기는 모형(해상도 무관) → 아틀라스 칸 → 스프라이트 내보내기.
//
// 모형 좌표(「몸 좌표」): x = 몸 가운데 0, y = 어른 머리 꼭대기 0 → 발끝 9. 단위는 0.25 m(기본 아틀라스 1 px). 기존 4×9 사람과 같은 자리·크기.
//   칸(cell) = { box:[x0,y0,x1,y1](몸 좌표 정수), part(x, y) → 부위 글자 | null, col:{글자:[r,g,b]}, flat(윤곽·음영 없음, 색 그대로) }
//   같은 모형을 k = 1(기본 0.25 m)·2·4(깊은 확대 단계)로 래스터화한다 → 확대해도 계단 없이 또렷하다.
// 아틀라스: 기본은 buildPeopleAtlas 그림 아래에 덧붙이고(extendPeopleAtlas), 깊은 단계는 hisprites 그림 아래에 덧붙인다(withCastHi).
// 셰이더(render.js): kind 1 = 기본 아틀라스 사람(줄별 깊이 + 룩 2 채도), kind 10 = 깊은 단계 아틀라스 사람, kind 9 = 깊은 단계 색 그대로(말풍선·돗자리·연),
//   kind 3(그림자), kind 4(플래시), kind 6(흰 점). 기본 단계의 「색 그대로」는 R.flatKind 가 있으면 그것, 없으면 kind 1.
import { PERSON } from './movers.js';
import { addCast, BUB, SIM_DT } from './sim/people.js';

const TAU = Math.PI * 2;
const rgb = (hex) => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
const mul = (c, f) => c.map((v) => Math.min(255, v * f));
// 룩 2 는 사람 색의 채도를 0.6 배로 낮춘다. 한복은 색이 살아야 읽히므로 미리 채도를 올려 둔다.
const vivid = (c, f = 1.45) => { const l = 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]; return c.map((v) => Math.max(0, Math.min(255, l + (v - l) * f))); };
const ell = (x, y, cx, cy, rx, ry) => ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1;
const seg = (x, y, ax, ay, bx, by, r) => {
  const dx = bx - ax, dy = by - ay, t = Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy || 1)));
  return Math.hypot(x - ax - dx * t, y - ay - dy * t) <= r;
};
const SKIN = ['#f1c9a5', '#e8b98f', '#d9a57c', '#f6d6b8'].map(rgb);          // movers.js 와 같은 순서(기본 사람 위에 손을 덧그릴 때 맞춘다)
const SKIN2 = ['#f6d6b8', '#f1c9a5', '#e8b98f', '#d9a57c', '#b98560', '#8a5a3c'].map(rgb);   // 직접 그리는 유형용(더 넓은 피부색)
const HAIR2 = ['#141210', '#1e1a18', '#2b2320', '#3b2f2a', '#5a4030', '#8a6a3c'].map(rgb);
const DARK = [44, 40, 46], WHITE = [246, 244, 238];

// ── 부위 모형 ──────────────────────────────────────────────────────────────
const head = (x, y) => {
  if (ell(x, y, 0, 0.95, 0.82, 0.78) && y < 1.05) return 'H';
  if (ell(x, y, 0, 1.25, 0.74, 0.92)) return y < 1.3 && Math.abs(x) > 0.55 ? 'H' : 'S';
  if (Math.abs(x) < 0.32 && y >= 2.0 && y < 2.4) return 'S';
  return null;
};
// 걷는 사람(hisprites.js part 와 같은 치수). pose 0·2 다리 벌림, 1·3 모음. up = 두 팔 들기.
function person(x, y, pose, up) {
  const apart = pose === 0 || pose === 2, sw = pose === 0 ? 1 : pose === 2 ? -1 : 0;
  const h = head(x, y);
  if (h) return h;
  for (let side = -1; side <= 1; side += 2) {
    const ax = side * 1.12, d = side < 0 ? sw : -sw;
    if (up) { if (seg(x, y, ax, 2.6, ax + side * 0.55, 0.85, 0.3)) return y < 1.4 ? 'S' : 'c'; }
    else { const end = 4.35 - 0.3 * d; if (seg(x, y, ax, 2.55, ax + side * 0.12, end, 0.3)) return y > end - 0.55 ? 'S' : 'c'; }
  }
  if (y >= 2.25 && y < 5.25 && Math.abs(x) <= (y < 2.7 ? 1.25 - (2.7 - y) * 0.9 : 1.25 - (y - 2.7) * 0.06)) return 'C';
  if (y >= 5.1 && y < 5.8 && Math.abs(x) <= 1.05) return 'P';
  for (let side = -1; side <= 1; side += 2) {
    const hx = side * (apart ? 0.5 : 0.45), fx = apart ? side * 1.05 + 0.15 * sw : side * 0.5;
    if (seg(x, y, hx, 5.4, fx, 8.35, 0.4)) return 'P';
    if (y >= 8.2 && y < 9 && ell(x, y, fx + side * 0.1, 8.62, 0.5, 0.38)) return 'F';
  }
  return null;
}
const kid = (x, y, pose, up) => person(x / 0.74, 9 - (9 - y) / 0.74, pose, up);
// 앉은 사람(책상다리)
function sitting(x, y) {
  const y2 = y - 2.9, h = head(x, y2);
  if (h) return h;
  if (ell(x, y, -1.2, 7.55, 0.3, 0.3) || ell(x, y, 1.2, 7.55, 0.3, 0.3)) return 'S';
  if (seg(x, y, -1.15, 5.5, -1.2, 7.3, 0.3) || seg(x, y, 1.15, 5.5, 1.2, 7.3, 0.3)) return 'c';
  if (y2 >= 2.25 && y < 7.9 && Math.abs(x) <= 1.2) return 'C';
  if (ell(x, y, 0, 8.3, 1.75, 0.68)) return 'P';
  return null;
}
// 한쪽 무릎 꿇은 사람(오른쪽을 본다), 내민 손에 작은 상자
function kneeling(x, y) {
  const y2 = y - 1.7, h = head(x, y2);
  if (h) return h;
  if (ell(x, y, 2.05, 4.55, 0.3, 0.3)) return 'A';
  if (seg(x, y, 1.0, 4.4, 1.8, 4.75, 0.28)) return 'c';
  if (y2 >= 2.25 && y < 6.9 && Math.abs(x) <= 1.15) return 'C';
  if (seg(x, y, 0.2, 7.0, 1.2, 7.3, 0.45) || seg(x, y, 1.2, 7.3, 1.25, 8.4, 0.38) || seg(x, y, -0.3, 7.1, -0.5, 8.3, 0.45) || seg(x, y, -0.5, 8.4, -1.5, 8.5, 0.36)) return 'P';
  if (ell(x, y, 1.45, 8.65, 0.5, 0.34)) return 'F';
  return null;
}
// 치마저고리: 짧은 저고리 + 넓게 퍼지는 긴 치마. pose 0·1 걷기(치맛자락이 흔들림), 2 서기
function hanbokF(x, y, pose) {
  const s = pose === 0 ? 0.22 : pose === 1 ? -0.22 : 0, ax = Math.abs(x);
  if (ell(x, y, 0, 0.95, 0.86, 0.8) && y < 1.08) return ell(x, y, 0.5, 0.3, 0.22, 0.2) ? 'A' : 'H';
  const h = head(x, y);
  if (h) return h;
  if (ell(x, y, -1.5, 4.2, 0.27, 0.27) || ell(x, y, 1.5, 4.2, 0.27, 0.27)) return 'S';
  if (y >= 2.2 && y < 3.95 && ax <= 1.2 - Math.max(0, 2.55 - y) * 0.9) {
    if (y < 3.2 && Math.abs(ax - (3.2 - y) * 0.42) < 0.11) return 'W';       // 깃(동정)
    return seg(x, y, 0.12, 3.15, 0.42, 4.9, 0.13) ? 'A' : 'C';                 // 고름
  }
  if (seg(x, y, 0.12, 3.15, 0.45 + s * 0.5, 5.3, 0.13)) return 'A';
  if (seg(x, y, -1.15, 2.65, -1.5, 3.9, 0.42) || seg(x, y, 1.15, 2.65, 1.5, 3.9, 0.42)) return 'c';
  if (y >= 3.8 && y < 8.8) {
    const t = (y - 3.8) / 5, hw = 1.3 + 1.4 * Math.sqrt(t), xx = x - s * t;
    if (Math.abs(xx) <= hw) { const f = (xx / hw) * 2.5 + 2.5, fr = f - Math.floor(f); return t > 0.15 && Math.abs(fr - 0.5) < 0.07 ? 'p' : y > 8.4 ? 'q' : 'P'; }
  }
  if (pose !== 2 && ell(x, y, pose === 0 ? 0.8 : -0.8, 8.82, 0.45, 0.24)) return 'F';
  return null;
}
// 저고리 + 바지 + 쾌자(긴 조끼). gat = 검은 갓
function hanbokM(x, y, pose, gat) {
  const sw = pose === 0 ? 1 : pose === 1 ? -1 : 0, ax = Math.abs(x);
  if (gat) {
    if (ell(x, y, 0, 0.6, 1.95, 0.42)) return 'K';
    if (ax <= 0.62 && y >= -0.8 && y < 0.5) return y > 0.22 ? 'k' : 'K';
  }
  const h = head(x, y);
  if (h) return h;
  if (ell(x, y, -1.42, 4.4, 0.27, 0.27) || ell(x, y, 1.42, 4.4, 0.27, 0.27)) return 'S';
  if (seg(x, y, -1.15, 2.65, -1.4, 4.0, 0.4) || seg(x, y, 1.15, 2.65, 1.4, 4.0, 0.4)) return 'c';
  if (y >= 2.2 && y < 7.4 && ax <= Math.min(1.15 + (y - 2.2) * 0.07, 1.2 - Math.max(0, 2.55 - y) * 0.9 + (y > 2.55 ? (y - 2.55) * 0.07 : 0))) {
    if (y >= 4.25 && y < 4.62) return 'A';                                    // 띠
    if (y < 4.25) return ax < 0.24 ? 'C' : y < 3.1 && Math.abs(ax - 0.24 - (3.1 - y) * 0.3) < 0.1 ? 'W' : 'D';
    return ax < 0.12 + (y - 4.6) * 0.1 ? 'P' : 'D';
  }
  for (let side = -1; side <= 1; side += 2) {
    const fx = side * 0.62 + 0.22 * sw * side;
    if (seg(x, y, side * 0.55, 6.8, fx, 8.25, 0.5)) return y > 7.95 ? 'W' : 'P';
    if (y >= 8.2 && y < 9 && ell(x, y, fx + side * 0.1, 8.64, 0.5, 0.36)) return 'F';
  }
  return null;
}
// 수문장·수문군: 전립(붉은 상모) + 긴 겉옷 + 띠 + 목화(장화)
function guard(x, y, pose) {
  const sw = pose === 0 ? 1 : pose === 1 ? -1 : 0, ax = Math.abs(x);
  if (ell(x, y, 0.35, -0.4, 0.24, 0.48)) return 'A';
  if ((ell(x, y, 0, 0.2, 0.74, 0.62) && y < 0.62) || ell(x, y, 0, 0.62, 1.9, 0.42)) return 'K';
  const h = head(x, y);
  if (h) return h === 'H' ? 'K' : h;
  if (ell(x, y, -1.42, 4.45, 0.27, 0.27) || ell(x, y, 1.42, 4.45, 0.27, 0.27)) return 'S';
  if (seg(x, y, -1.15, 2.65, -1.4, 4.1, 0.42) || seg(x, y, 1.15, 2.65, 1.4, 4.1, 0.42)) return 'c';
  if (y >= 2.2 && y < 7.5 && ax <= (y < 2.55 ? 1.2 - (2.55 - y) * 0.9 : 1.2 + Math.max(0, y - 4.8) * 0.13)) return y >= 4.35 && y < 4.9 ? 'A' : y > 4.9 && ax < 0.1 ? 'c' : 'C';
  for (let side = -1; side <= 1; side += 2) {
    const fx = side * 0.6 + 0.2 * sw * side;
    if (seg(x, y, side * 0.55, 7.2, fx, 8.4, 0.42)) return 'F';
    if (y >= 8.2 && y < 9 && ell(x, y, fx + side * 0.1, 8.64, 0.5, 0.36)) return 'F';
  }
  return null;
}
// 개(오른쪽을 본다). pose 0·1 걷기, 2 앉기
function dog(x, y, pose) {
  if (pose === 2) {
    if (ell(x, y, 0.95, 6.75, 0.3, 0.24)) return 'c';
    if (ell(x, y, 0.2, 6.2, 0.2, 0.34)) return 'c';
    if (ell(x, y, 0.5, 6.8, 0.56, 0.5) || ell(x, y, -0.2, 8.05, 0.72, 0.9) || seg(x, y, 0.35, 8.0, 0.4, 8.85, 0.17) || seg(x, y, -0.8, 8.7, -1.4, 8.45, 0.16)) return 'C';
    return null;
  }
  const d = pose ? 0.2 : -0.1;
  if (ell(x, y, 1.9, 7.3, 0.3, 0.22) || ell(x, y, 1.15, 6.72, 0.22, 0.36)) return 'c';
  if (ell(x, y, 0, 7.75, 1.3, 0.56) || ell(x, y, 1.38, 7.15, 0.56, 0.5) || seg(x, y, -1.2, 7.5, -1.7, 6.8, 0.16)) return 'C';
  if (seg(x, y, -0.95 - d, 8.0, -0.95 - d * 2, 8.85, 0.17) || seg(x, y, -0.5 + d, 8.0, -0.5 + d * 2, 8.85, 0.17) || seg(x, y, 0.6 - d, 8.0, 0.6 - d * 2, 8.85, 0.17) || seg(x, y, 1.0 + d, 8.0, 1.0 + d * 2, 8.85, 0.17)) return 'C';
  return null;
}
function cat(x, y, pose) {
  if (pose === 2) {
    if (ell(x, y, 0.1, 7.0, 0.16, 0.3) || ell(x, y, 0.7, 7.0, 0.16, 0.3)) return 'C';
    if (ell(x, y, 0.4, 7.5, 0.46, 0.42) || ell(x, y, 0, 8.4, 0.58, 0.62) || seg(x, y, -0.4, 8.85, -1.1, 8.7, 0.13)) return 'C';
    return null;
  }
  const d = pose ? 0.16 : -0.08;
  if (ell(x, y, 0.75, 7.55, 0.15, 0.28) || ell(x, y, 1.25, 7.55, 0.15, 0.28)) return 'C';
  if (ell(x, y, 0, 8.25, 0.95, 0.4) || ell(x, y, 1.0, 7.95, 0.42, 0.38) || seg(x, y, -0.9, 8.15, -1.35, 7.3, 0.13)) return 'C';
  if (seg(x, y, -0.6 - d, 8.4, -0.6 - d * 2, 8.9, 0.13) || seg(x, y, 0.6 + d, 8.4, 0.6 + d * 2, 8.9, 0.13)) return 'C';
  return null;
}
// 휠체어 이용자(오른쪽을 본다)
function wheelchair(x, y) {
  const ring = ((x + 0.35) / 1.2) ** 2 + ((y - 7.75) / 1.2) ** 2;
  if ((ring <= 1 && ring >= 0.52) || ell(x, y, -0.35, 7.75, 0.2, 0.2) || ell(x, y, 1.45, 8.68, 0.3, 0.3)) return 'K';
  if (seg(x, y, 0.1, 7.1, 1.15, 7.2, 0.4) || seg(x, y, 1.15, 7.2, 1.35, 8.3, 0.34)) return 'P';
  if (ell(x, y, 1.6, 8.3, 0.4, 0.26)) return 'F';
  const h = head(x + 0.2, y - 2.3);
  if (h) return h;
  if (ell(x, y, 0.75, 6.75, 0.28, 0.28)) return 'S';
  if (seg(x, y, 0.3, 5.1, 0.7, 6.6, 0.3)) return 'c';
  if (y >= 4.55 && y < 7.3 && Math.abs(x + 0.2) <= 1.1) return 'C';
  if (seg(x, y, -1.25, 5.0, -1.25, 7.6, 0.14) || seg(x, y, -1.25, 5.0, -1.75, 4.85, 0.12)) return 'K';
  return null;
}
function stroller(x, y) {
  if (ell(x, y, -0.6, 8.6, 0.36, 0.36) || ell(x, y, 1.0, 8.6, 0.36, 0.36) || seg(x, y, -0.9, 7.0, -1.6, 5.6, 0.12) || seg(x, y, -0.5, 7.8, -0.6, 8.4, 0.1) || seg(x, y, 0.9, 7.8, 1.0, 8.4, 0.1)) return 'K';
  if (ell(x, y, 0.1, 6.95, 0.3, 0.25)) return 'S';
  if (ell(x, y, 0.5, 6.7, 1.05, 0.95) && y < 6.85 && x > -0.2) return 'C';
  if (ell(x, y, 0.2, 7.15, 1.3, 0.85) && y >= 6.85) return 'c';
  return null;
}

// ── 덧그림(몸 좌표에 맞춰 그려 둔 소품) ──
const O = {
  // 달리기 팔: 한쪽은 앞으로 접어 올리고 반대쪽은 뒤로 내린다(f 로 번갈아)
  runArm: (f) => (x, y) => { for (const side of [-1, 1]) { const up = (side < 0) === (f === 0), hx = side * (up ? 1.9 : 1.5), hy = up ? 2.7 : 4.4; if (ell(x, y, hx, hy, 0.34, 0.34) || seg(x, y, side * 1.2, 3.45, hx, hy, 0.26)) return 'S'; } return null; },
  handUp: (side, f) => (x, y) => { const tx = side * (1.75 + f * 0.35), ty = 0.9 + f * 0.25; return ell(x, y, tx, ty, 0.32, 0.32) || seg(x, y, side * 1.15, 2.75, tx, ty, 0.28) ? 'S' : null; },
  cam: (x, y) => (Math.abs(x - 0.1) <= 0.62 && y >= 1.05 && y < 1.95 ? (ell(x, y, 0.1, 1.5, 0.3, 0.3) ? 'L' : 'K') : seg(x, y, -1.1, 3.0, -0.6, 1.7, 0.28) || seg(x, y, 1.1, 3.0, 0.75, 1.7, 0.28) ? 'S' : null),
  point: (side) => (x, y) => (ell(x, y, side * 2.65, 2.45, 0.3, 0.3) || seg(x, y, side * 1.15, 2.8, side * 2.6, 2.45, 0.28) ? 'S' : null),
  cap: (x, y) => ((ell(x, y, 0, 0.62, 0.9, 0.62) && y < 0.78) || (y >= 0.55 && y < 0.85 && x > 0 && x <= 1.45) ? 'A' : null),
  sunhat: (x, y) => (ell(x, y, 0, 0.35, 0.82, 0.55) && y < 0.6 ? (y > 0.36 ? 'B' : 'A') : ell(x, y, 0, 0.7, 1.6, 0.3) ? 'A' : null),
  beanie: (x, y) => (ell(x, y, 0, -0.1, 0.3, 0.3) ? 'B' : ell(x, y, 0, 0.55, 0.9, 0.72) && y < 0.9 ? (y > 0.62 ? 'B' : 'A') : null),
  scarf: (x, y) => ((Math.abs(x) <= 0.85 && y >= 1.95 && y < 2.65) || seg(x, y, 0.5, 2.5, 0.72, 3.9, 0.26) ? (Math.abs(y - 3.2) < 0.12 ? 'B' : 'A') : null),
  coat: (x, y) => (y >= 2.2 && y < 6.9 && Math.abs(x) <= (y < 2.7 ? 1.5 - (2.7 - y) * 1.0 : 1.5) ? (Math.abs(x) < 0.07 || Math.abs(((y - 2.2) % 0.95) - 0.5) < 0.06 ? 'B' : 'A') : null),
  pack: (x, y) => (x >= -2.15 && x < -1.2 && y >= 2.5 && y < 4.7 ? (y < 2.9 ? 'B' : 'A') : seg(x, y, -0.75, 2.3, -0.9, 4.2, 0.13) ? 'B' : null),
  cane: (x, y) => (seg(x, y, 1.75, 4.3, 2.0, 8.9, 0.15) ? 'A' : null),
  broom: (x, y) => (ell(x, y, -2.25, 8.6, 0.55, 0.38) ? 'B' : seg(x, y, -1.6, 3.6, -2.2, 8.4, 0.14) ? 'A' : null),
  umbrella: (x, y) => {
    if (y < 0.4 && ell(x, y, 0, 0.3, 3.3, 2.0)) { const f = (x / 3.3) * 2 + 2.5, fr = f - Math.floor(f); return y > 0.05 ? 'B' : Math.abs(fr - 0.5) < 0.06 ? 'B' : 'A'; }
    return ell(x, y, 0, -1.75, 0.16, 0.2) || seg(x, y, 0.95, 0.4, 0.95, 3.6, 0.1) ? 'K' : null;
  },
  flag: (x, y) => {
    if (seg(x, y, 1.6, 4.3, 1.6, -1.6, 0.11)) return 'K';
    return x > 1.7 && x < 3.6 && y > -1.6 && y < -0.1 && Math.abs(y + 0.85) < (3.6 - x) * 0.4 ? 'A' : null;
  },
  spear: (x, y) => (seg(x, y, 1.75, -1.6, 1.75, -0.8, 0.16) ? 'W' : ell(x, y, 1.75, -0.55, 0.3, 0.3) ? 'A' : seg(x, y, 1.75, 8.8, 1.75, -0.8, 0.11) ? 'K' : null),
  banner: (x, y) => {
    if (seg(x, y, 1.6, 8.8, 1.6, -1.9, 0.11)) return 'K';
    if (x > 1.7 && x < 3.9 && y > -1.8 && y < 1.5) return x > 3.55 || y < -1.45 || y > 1.15 ? 'B' : ell(x, y, 2.75, -0.15, 0.5, 0.7) ? 'B' : 'A';
    return null;
  },
  guitar: (x, y) => (ell(x, y, 0.35, 4.45, 0.3, 0.3) ? 'K' : ell(x, y, 0.3, 4.5, 1.0, 0.78) || ell(x, y, -0.5, 4.3, 0.6, 0.55) ? 'A' : seg(x, y, 1.0, 4.1, 2.5, 2.9, 0.16) ? 'B' : null),
  // 겨울 한복: 털 배자(조끼)
  vest: (x, y) => (y >= 2.25 && y < 4.3 && Math.abs(x) <= 1.25 && Math.abs(x) > 0.2 ? (y < 2.6 || Math.abs(x) < 0.42 ? 'B' : 'A') : null),
};
// 땅 위 소품
const G = {
  bench: (x, y) => (y >= 7.0 && y < 7.6 && Math.abs(x) <= 3.4 ? 'A' : y >= 7.6 && y < 8.9 && (Math.abs(Math.abs(x) - 2.9) < 0.22) ? 'B' : y >= 6.0 && y < 6.5 && Math.abs(x) <= 3.4 ? 'B' : null),
  // 해치: 높은 기단 위에 앉은 석수. 화면 왼쪽 아래(남쪽, 도로 쪽)를 본다. 곱슬 갈기, 정수리 뿔, 부릅뜬 눈과 이를 드러낸 입, 목 방울, 비늘, 말린 꼬리.
  // x −4…4(2 m), y −5…9(기단 1.35 m + 석상 2.15 m). L 밝은 화강암, M 중간, D 그늘, K 눈·입.
  haechi: (x, y) => {
    if (y >= 3.6) {
      if (y < 4.35) return Math.abs(x) <= 3.7 ? 'L' : null;                                  // 갑석
      if (y >= 8.25) return Math.abs(x) <= 3.7 ? (x > 1.3 ? 'D' : 'M') : null;                // 지대석
      return Math.abs(x) <= 3.15 ? (x > 1.3 || y < 4.8 ? 'D' : (Math.abs(x + 0.9) < 1.5 && y > 5.4 && y < 7.6 ? 'L' : 'M')) : null;   // 몸돌(앞면에 밝은 면석)
    }
    // 얼굴: 짙은 눈썹 아래 부릅뜬 눈, 넓은 코, 이를 드러내고 웃는 큰 입(해치의 표정)
    if (ell(x, y, -2.1, -2.7, 0.34, 0.36) || ell(x, y, -0.55, -2.7, 0.34, 0.36)) return 'K';
    if (seg(x, y, -2.7, -3.45, -1.75, -3.2, 0.2) || seg(x, y, -0.9, -3.2, 0.05, -3.45, 0.2)) return 'D';
    if (ell(x, y, -1.3, -1.95, 0.7, 0.3)) return 'D';
    if (x > -2.65 && x < 0.05 && y > -1.5 && y < -0.8 && ell(x, y, -1.3, -1.75, 1.5, 0.98)) return y < -1.32 || (Math.floor((x + 2.65) / 0.45) & 1) ? 'K' : 'L';
    if (ell(x, y, -1.3, -2.3, 1.75, 1.7)) return 'L';
    if (ell(x, y, -1.3, -5.25, 0.5, 0.45)) return 'L';                                         // 정수리 뿔(혹)
    // 갈기: 얼굴을 빙 두른 곱슬 열 덩이. 덩이마다 그늘 테두리를 둘러 소용돌이로 읽히게 한다.
    for (let k = 0; k < 10; k++) {
      const a = (k * 36 + 18) * Math.PI / 180, cx = -1.3 + Math.cos(a) * 2.2, cy = -2.45 + Math.sin(a) * 2.1;
      if (ell(x, y, cx, cy, 0.52, 0.52)) return ell(x, y, cx + 0.1, cy + 0.1, 0.2, 0.2) ? 'D' : 'L';
      if (ell(x, y, cx, cy, 0.82, 0.82)) return 'M';
    }
    if (ell(x, y, -1.3, -2.45, 2.3, 2.2)) return 'D';
    if (ell(x, y, -1.3, 0.45, 0.5, 0.5)) return ell(x, y, -1.3, 0.6, 0.18, 0.18) ? 'K' : 'D';   // 목 방울
    if (y > 0.4 && y < 3.6 && ((x > -2.8 && x < -1.7) || (x > -1.2 && x < -0.1))) return y > 2.9 ? 'M' : 'L';   // 앞다리와 발
    // 말린 꼬리(등 뒤로 솟은 불꽃 모양)
    if (ell(x, y, 3.35, -0.2, 0.28, 0.4)) return 'D';
    if (ell(x, y, 3.3, 0.1, 0.72, 1.35) || ell(x, y, 3.0, -1.5, 0.6, 0.62) || ell(x, y, 3.55, -2.3, 0.4, 0.45)) return 'L';
    if (ell(x, y, -0.95, 1.0, 1.95, 2.6)) return y > 1.4 && Math.abs(x + 0.95) < 0.2 ? 'M' : 'L';   // 가슴
    if (ell(x, y, 1.3, 1.75, 2.3, 1.95)) {                                                       // 몸·엉덩이(비늘 무늬)
      const u = x / 0.9 + (Math.floor(y / 0.8) & 1) * 0.5, fx = u - Math.floor(u) - 0.5, fy = y / 0.8 - Math.floor(y / 0.8) - 0.5;
      return fx * fx + fy * fy < 0.05 ? 'D' : ell(x, y, 1.9, 2.3, 1.5, 1.2) ? 'L' : 'M';
    }
    return null;
  },
  snowman: (x, y) => {
    if (ell(x, y, -0.3, 6.15, 0.14, 0.14) || ell(x, y, 0.3, 6.15, 0.14, 0.14) || ell(x, y, 0, 7.6, 0.13, 0.13) || ell(x, y, 0, 8.1, 0.13, 0.13)) return 'K';
    if (seg(x, y, 0, 6.4, 0.6, 6.5, 0.12)) return 'A';
    if (Math.abs(x) <= 0.95 && y >= 6.85 && y < 7.15) return 'B';
    if (seg(x, y, -1.0, 7.5, -1.9, 6.8, 0.1) || seg(x, y, 1.0, 7.5, 1.9, 6.8, 0.1)) return 'T';
    return ell(x, y, 0, 6.3, 0.8, 0.78) || ell(x, y, 0, 7.95, 1.15, 1.05) ? 'W' : null;
  },
  mat: (x, y) => { const xx = x - (8 - y) * 0.45; return y >= 6.4 && y < 9 && Math.abs(xx) <= 3.3 ? ((Math.floor((xx + 4) / 0.8) + Math.floor(y / 0.65)) & 1 ? 'A' : 'B') : null; },
  kite: (x, y) => (Math.abs(x) / 1.5 + Math.abs(y - 2) / 1.9 <= 1 ? (x * (y - 2) > 0 ? 'A' : 'B') : seg(x, y, 0, 3.9, 0.5, 5.2, 0.12) || seg(x, y, 0.5, 5.2, -0.2, 6.3, 0.12) ? 'B' : null),
};
// 말풍선(픽셀 그림 그대로. 어느 해상도에서나 같은 격자)
// 말풍선 안 그림 3×4. 풍선은 사람 폭(2 px)의 1.25배 = 5칸.
const BUBBLE_ICONS = {
  [BUB.DOTS]: ['###', '...', '##.', '...'],   // 글줄 두 개(읽을 수 있는 글자는 아니다)
  [BUB.NOTE]: ['.##', '.#.', '##.', '##.'],
  [BUB.BANG]: ['.#.', '.#.', '...', '.#.'],
  [BUB.HEART]: ['#.#', '###', '###', '.#.'],
  [BUB.SMILE]: ['#.#', '...', '###', '.#.'],
};
const BUBBLE_COL = { [BUB.DOTS]: [52, 50, 64], [BUB.NOTE]: [36, 84, 176], [BUB.BANG]: [214, 78, 20], [BUB.HEART]: [214, 36, 64], [BUB.SMILE]: [196, 110, 8] };
// 5×7 칸: 어두운 테두리 1, 안쪽 3×4 그림, 아래 꼬리 1줄
const bubblePart = (icon) => (x, y) => {
  const c = Math.floor(x), r = Math.floor(y);
  if (r === 6) return c === 2 ? 'k' : null;
  if (c < 0 || c > 4 || r < 0 || r > 6) return null;
  if (r === 0 || r === 5) return c >= 1 && c <= 3 ? 'k' : null;
  if (c === 0 || c === 4) return 'k';
  return icon[r - 1][c - 1] === '#' ? 'I' : 'W';
};

// ── 색 ──
export const HANBOK_F = [   // [저고리, 치마, 고름·댕기]. 12벌 이상(지금 14벌)
  ['#f6efe6', '#d6456b', '#b0243f'], ['#f3d6de', '#7a3fa0', '#4b2a7a'], ['#f7f1d0', '#c8322f', '#2d4f9e'], ['#e6f0f7', '#2d4f9e', '#c8322f'],
  ['#fbe7b0', '#2f8f6b', '#c8322f'], ['#f4f4f4', '#e58a2e', '#7a3fa0'], ['#cfe3d2', '#40407a', '#d6456b'], ['#dcd3ee', '#6a6f86', '#7a3fa0'],
  ['#f2cf4a', '#d2362e', '#3a8a5a'], ['#3f9a63', '#d2362e', '#f2cf4a'], ['#f4b8c8', '#6faede', '#d6456b'], ['#f4f4f4', '#23263a', '#b0243f'],
  ['#f8d9c0', '#1f8a8a', '#f2cf4a'], ['#f1ead8', '#8a2846', '#d8a628'],
];
export const HANBOK_M = [   // [저고리, 쾌자, 바지, 띠, 갓]
  ['#f4f4f4', '#23335c', '#e8e4da', '#c8322f', 1], ['#e8eef2', '#6a2d2d', '#d9d4c8', '#d8a628', 1], ['#f1ead8', '#2f5f4f', '#e8e4da', '#23335c', 1],
  ['#fbe7b0', '#7a3fa0', '#e8e4da', '#c8322f', 0], ['#e6f0f7', '#7f8ca6', '#f4f4f4', '#23335c', 0], ['#f4f4f4', '#22222a', '#d9d4c8', '#b0243f', 1],
];
export const HANBOK_K = [['#f2cf4a', '#d2362e', '#3a8a5a', 0], ['#f4b8c8', '#7a3fa0', '#f2cf4a', 0], ['#e6f0f7', '#2d4f9e', '#c8322f', 1], ['#fbe7b0', '#2f8f6b', '#23335c', 1]];   // 끝 1 = 바지저고리
const KID_PAL = [['#ff6b6b', '#3b4a66'], ['#ffd23f', '#2b2f3a'], ['#4ecdc4', '#4a4e69'], ['#ff9f1c', '#22577a'], ['#a06cd5', '#3b3b58'], ['#5fa8d3', '#1b263b'], ['#f78fb3', '#574b90'], ['#8ac926', '#33415c']];
const GUARD_PAL = [['#b5332e', '#23335c', '#d8a628'], ['#2b4c9b', '#b5332e', '#d8a628'], ['#d8a628', '#b5332e', '#2b4c9b'], ['#23335c', '#d8a628', '#b5332e']];   // [겉옷, 띠·상모, 소매]. 끝 = 수문장
const DOG_COL = ['#c89b62', '#f1ede4', '#4a4038', '#8a5a3c'], CAT_COL = ['#e0a04a', '#4a4a52', '#efe8dc'];
const CAP_COL = ['#d6453a', '#2f5fa8', '#f1ede4', '#2b2b33', '#3f9a63'], SUN_COL = ['#e4cf9a', '#f4f1ea', '#f1b7c4'], BEANIE_COL = ['#b0243f', '#2d4f9e', '#3d3d48', '#e8e4da'];
const SCARF_COL = ['#c8322f', '#e8e4da', '#2f5f4f', '#d8a628', '#5a5f78'], COAT_COL = ['#26262e', '#30303a', '#f1ede4', '#c9b48e', '#27365c', '#5e6b4a', '#e9b9c6'];
const PACK_COL = ['#d6453a', '#2f8f6b', '#2b2b33', '#e58a2e'];
const UMB_COL = ['#dfe9ee', '#f2cf4a', '#d6453a', '#27365c', '#2b2b33', '#3f9a63', '#dfe9ee', '#7fb7e0'], PARASOL_COL = ['#f4f1ea', '#f6dfe6', '#dfeaf2'];
const FLAG_COL = ['#ffd23f', '#ff7a3d'];
const MAT_COL = [['#e24a4a', '#f4efe6'], ['#3f78c8', '#f4efe6'], ['#3f9a63', '#f2e08a']], KITE_COL = [['#e24a4a', '#f2cf4a'], ['#3f78c8', '#f4efe6'], ['#7a3fa0', '#f2cf4a']];

// ── 칸 목록. scene._cast(addCast) 가 있어야 한다(앉은 자세를 굽는 팔레트 목록).
export function buildCast(scene) {
  if (scene._castReg) return scene._castReg;
  const cast = addCast(scene), pal = scene.walker_palette;
  const cells = [];
  const cell = (box, part, col, o = {}) => { const c = { i: cells.length, box, w: box[2] - box[0], h: box[3] - box[1], part, col, flat: !!o.flat, min: o.min || 4, lo: null }; cells.push(c); return c; };
  const mir = (part) => (x, y) => part(-x, y);
  const BODY = [-3, -2, 3, 10], WIDE = [-4, -2, 4, 10];
  const reg = { cells };
  // 치마저고리 [걷기 0, 걷기 1, 서기]
  reg.hf = HANBOK_F.map((p, i) => {
    const C = vivid(rgb(p[0]), 1.2), P = vivid(rgb(p[1])), col = { C, c: mul(C, 0.9), P, p: mul(P, 0.78), q: mul(P, 0.86), A: vivid(rgb(p[2])), W: WHITE, H: HAIR2[i % 4], S: SKIN2[(i * 5 + 1) % 4], F: WHITE };
    return [0, 1, 2].map((pose) => cell(BODY, (x, y) => hanbokF(x, y, pose), col));
  });
  reg.hm = HANBOK_M.map((p, i) => {
    const C = rgb(p[0]), D = vivid(rgb(p[1]), 1.3), col = { C, c: mul(C, 0.9), D, P: rgb(p[2]), A: vivid(rgb(p[3])), W: WHITE, K: [34, 32, 40], k: [70, 66, 78], H: HAIR2[i % 3], S: SKIN2[(i * 3 + 2) % 5], F: DARK };
    return [0, 1, 2].map((pose) => cell(BODY, (x, y) => hanbokM(x, y, pose, p[4]), col));
  });
  // 어린이 한복: 여자아이는 색동 소매, 남자아이는 바지저고리
  reg.hk = HANBOK_K.map((p, i) => {
    const C = vivid(rgb(p[0]), 1.2), P = vivid(rgb(p[1])), base = { C, c: mul(C, 0.9), P, p: mul(P, 0.8), q: mul(P, 0.86), A: vivid(rgb(p[2])), D: P, W: WHITE, K: DARK, k: DARK, H: HAIR2[i % 3], S: SKIN2[i % 4], F: p[3] ? DARK : WHITE };
    const stripes = [[226, 60, 60], [246, 206, 70], [70, 150, 96], [70, 110, 200]];
    const f = p[3] ? (x, y, pose) => hanbokM(x, y, pose, 0) : (x, y, pose) => { const ch = hanbokF(x, y, pose); return ch === 'c' ? 'r' + (Math.floor(y * 2.2) & 3) : ch; };
    const col = { ...base, r0: stripes[0], r1: stripes[1], r2: stripes[2], r3: stripes[3] };
    return [0, 1, 2].map((pose) => cell([-2, 0, 2, 10], (x, y) => f(x / 0.72, 9 - (9 - y) / 0.72, pose), col));
  });
  // 어린이 [걷기 0..3 → 0·1·2·1, 만세]
  reg.kid = KID_PAL.map((p, i) => {
    const C = rgb(p[0]), col = { C, c: mul(C, 0.86), P: rgb(p[1]), H: HAIR2[i % 5], S: SKIN2[(i * 2 + 1) % 6], F: DARK };
    return [0, 1, 2, 4].map((pose) => cell([-2, 1, 2, 10], (x, y) => (pose === 4 ? kid(x, y, 1, true) : kid(x, y, pose, false)), col));
  });
  reg.guard = GUARD_PAL.map((p, i) => {
    const C = vivid(rgb(p[0]), 1.3), col = { C, A: vivid(rgb(p[1]), 1.3), c: vivid(rgb(p[2]), 1.3), K: [30, 28, 36], S: SKIN2[1 + (i % 3)], F: [36, 32, 40] };
    return [0, 1, 2].map((pose) => cell(BODY, (x, y) => guard(x, y, pose), col));
  });
  // 앉기·무릎: 어른 팔레트 번호 → 칸
  reg.sit = new Map(); reg.kneel = new Map();
  const adultCol = (pi) => { const C = rgb(pal[pi][0]); return { C, c: mul(C, 0.86), P: rgb(pal[pi][1]), H: rgb(pal[pi][2]), S: SKIN[pi % SKIN.length], F: DARK, A: [200, 60, 80] }; };
  for (const pi of cast.sitters) reg.sit.set(pi, cell([-2, 2, 2, 10], sitting, adultCol(pi)));
  for (const pi of cast.kneelers) reg.kneel.set(pi, cell([-2, 1, 3, 10], kneeling, adultCol(pi)));
  // 동물·탈것: [오른쪽 보기, 왼쪽 보기] × 자세
  const both = (box, part, col) => [cell(box, part, col), cell([-box[2], box[1], -box[0], box[3]], mir(part), col)];
  reg.dog = DOG_COL.map((c) => { const C = rgb(c), col = { C, c: mul(C, 0.7) }; return [0, 1, 2].map((pose) => both([-2, 5, 3, 10], (x, y) => dog(x, y, pose), col)); });
  reg.cat = CAT_COL.map((c) => { const C = rgb(c), col = { C }; return [0, 1, 2].map((pose) => both([-2, 6, 2, 10], (x, y) => cat(x, y, pose), col)); });
  reg.wheel = [0, 1, 2].map((i) => { const pi = cast.normal[(i * 7 + 3) % cast.normal.length]; return both([-3, 2, 3, 10], wheelchair, { ...adultCol(pi), K: [52, 54, 64] }); });
  reg.stroller = [['#3d5a80', '#293241'], ['#c8553d', '#5a2a22'], ['#6a8f6b', '#33483a']].map((p) => both([-2, 5, 3, 10], stroller, { C: rgb(p[0]), c: rgb(p[1]), K: [48, 48, 56], S: SKIN2[0] }));
  // 덧그림
  reg.hand = SKIN.map((S) => [[-1, 0], [-1, 1], [1, 0], [1, 1]].map(([side, f]) => cell(side < 0 ? [-3, 0, -1, 4] : [1, 0, 3, 4], O.handUp(side, f), { S })));   // [피부][왼0, 왼1, 오0, 오1]
  reg.runarm = SKIN.map((S) => [0, 1].map((f) => cell([-3, 2, 3, 5], O.runArm(f), { S })));   // [피부][걸음 0, 1]
  reg.cam = SKIN.map((S) => cell([-2, 1, 2, 4], O.cam, { S, K: [40, 40, 48], L: [150, 190, 220] }));
  reg.point = SKIN.map((S) => [-1, 1].map((side) => cell(side < 0 ? [-3, 2, -1, 4] : [1, 2, 3, 4], O.point(side), { S })));
  const tint = (list, box, part, o) => list.map((c) => { const A = rgb(c); return cell(box, part, { A, B: mul(A, 0.78), K: [60, 60, 70], W: [220, 220, 226] }, o); });
  reg.hats = [...tint(CAP_COL, [-1, 0, 2, 1], O.cap), ...tint(SUN_COL, [-2, 0, 2, 1], O.sunhat)];
  reg.beanie = tint(BEANIE_COL, [-1, -1, 1, 1], O.beanie);
  reg.scarf = tint(SCARF_COL, [-1, 1, 1, 4], O.scarf);
  reg.coat = tint(COAT_COL, [-2, 2, 2, 7], O.coat);
  reg.vest = tint(['#f1ede4', '#8a6a4a', '#3d3d48'], [-2, 2, 2, 5], O.vest);
  reg.pack = tint(PACK_COL, [-3, 2, 0, 5], O.pack);
  reg.cane = tint(['#7a5a3c'], [1, 4, 3, 9], O.cane, { min: 2 })[0];
  reg.broom = tint(['#8a6a3c'], [-3, 3, -1, 9], O.broom, { min: 2 })[0];
  reg.umb = tint(UMB_COL, [-4, -2, 4, 4], O.umbrella);
  reg.parasol = tint(PARASOL_COL, [-4, -2, 4, 4], O.umbrella);
  reg.flag = tint(FLAG_COL, [1, -2, 4, 5], O.flag, { min: 2 });
  reg.spear = cell([1, -2, 3, 9], O.spear, { K: [70, 52, 40], W: [214, 216, 222], A: [200, 50, 44] }, { min: 2 });
  reg.banner = cell([1, -2, 4, 9], O.banner, { K: [70, 52, 40], A: vivid([40, 70, 150], 1.3), B: vivid([216, 166, 40], 1.3) }, { min: 2 });
  reg.guitar = cell([-2, 2, 3, 6], O.guitar, { A: [176, 116, 62], B: [96, 66, 44], K: [50, 36, 30] });
  // 땅 위 소품
  reg.bench = cell([-4, 6, 4, 9], G.bench, { A: [150, 110, 72], B: [104, 76, 52] }, { min: 3 });
  reg.haechi = cell([-5, -6, 5, 10], G.haechi, { L: [228, 220, 202], M: [192, 183, 165], D: [142, 136, 126], K: [60, 56, 58] }, { min: 3 });
  reg.snowman = cell([-2, 5, 2, 10], G.snowman, { W: [244, 246, 250], K: [40, 40, 48], A: [236, 130, 40], B: [200, 60, 60], T: [96, 70, 50] }, { min: 2 });
  reg.mat = MAT_COL.map((p) => cell([-5, 6, 5, 9], G.mat, { A: rgb(p[0]), B: rgb(p[1]) }, { flat: true }));
  reg.kite = KITE_COL.map((p) => cell([-2, 0, 2, 7], G.kite, { A: rgb(p[0]), B: rgb(p[1]) }, { flat: true, min: 2 }));
  reg.bubble = {};
  for (const k of Object.keys(BUBBLE_ICONS)) reg.bubble[k] = cell([0, 0, 5, 7], bubblePart(BUBBLE_ICONS[k]), { k: [26, 22, 32], W: [255, 255, 252], I: BUBBLE_COL[k] }, { flat: true, bitmap: true });
  for (const k of Object.keys(reg.bubble)) reg.bubble[k].bitmap = true;
  Object.defineProperty(scene, '_castReg', { value: reg, enumerable: false });
  return reg;
}

// 칸 하나를 배율 k 로 래스터화한다. put(x, y, r, g, b). k = 1 은 3×3 표본의 덮임으로(가는 것은 min 을 낮춰) 판정, k ≥ 2 는 텍셀 중심 + 1 텍셀 윤곽.
export function rasterCell(c, k, put) {
  const W = c.w * k, H = c.h * k, [x0, y0] = c.box, g = new Array(W * H).fill(null);
  const cnt = new Map();
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    let ch = null;
    if (k > 1 || c.bitmap) ch = c.part(x0 + (x + 0.5) / k, y0 + (y + 0.5) / k);
    else {
      cnt.clear();
      let n = 0;
      for (let j = 0; j < 3; j++) for (let i = 0; i < 3; i++) { const p = c.part(x0 + x + (i + 0.5) / 3, y0 + y + (j + 0.5) / 3); if (p) { n++; cnt.set(p, (cnt.get(p) || 0) + (i === 1 && j === 1 ? 1.5 : 1)); } }
      if (n >= c.min) { let best = 0; for (const [p, v] of cnt) if (v > best) { best = v; ch = p; } }
    }
    if (!ch) continue;
    let col = c.col[ch] || DARK;
    if (!c.flat && k > 1 && x0 + (x + 0.5) / k > 0.5 && ch !== 'F' && ch !== 'K') col = mul(col, 0.88);   // 화면 오른쪽은 조금 어둡게(hisprites 와 같은 빛)
    g[y * W + x] = col;
  }
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    let col = g[y * W + x];
    if (!col) {
      if (c.flat || k < 2) continue;
      const nb = (x + 1 < W && g[y * W + x + 1]) || (x > 0 && g[y * W + x - 1]) || (y + 1 < H && g[(y + 1) * W + x]) || (y > 0 && g[(y - 1) * W + x]);
      if (!nb) continue;
      col = mul(nb, 0.42);
    }
    put(x, y, col[0] | 0, col[1] | 0, col[2] | 0);
  }
}
const pack = (cells, k, W, y0) => {
  let x = 0, y = y0, rowH = 0;
  const pos = cells.map((c) => { const w = c.w * k, h = c.h * k; if (x + w > W) { x = 0; y += rowH; rowH = 0; } const o = [x, y]; x += w; rowH = Math.max(rowH, h); return o; });
  return { pos, H: y + rowH };
};
// 기본(0.25 m) 사람 아틀라스 아래에 칸을 덧붙인다. 기존 그림의 좌표는 그대로.
export function extendPeopleAtlas(img, reg) {
  const { pos, H } = pack(reg.cells, 1, img.width, img.height);
  const out = new ImageData(img.width, H);
  out.data.set(img.data);
  reg.cells.forEach((c, i) => { c.lo = pos[i]; rasterCell(c, 1, (x, y, r, g, b) => { const o = ((pos[i][1] + y) * img.width + pos[i][0] + x) * 4; out.data[o] = r; out.data[o + 1] = g; out.data[o + 2] = b; out.data[o + 3] = 255; }); });
  reg.loBytes = (H - img.height) * img.width * 4;
  return out;
}
// 깊은 단계 아틀라스(hisprites.js 제너레이터)를 감싸, 다 만들어진 그림 아래에 칸을 그 해상도로 덧붙인다 → 결과에 cast[i] = [x, y].
export function* withCastHi(gen, reg, SS) {
  let r;
  while (!(r = gen.next()).done) yield;
  const a = r.value, k = SS / 2, W = a.img.width, H0 = a.img.height;
  const { pos, H } = pack(reg.cells, k, W, H0);
  const img = new ImageData(W, H);
  img.data.set(a.img.data);
  yield;
  for (let i = 0; i < reg.cells.length; i++) {
    if (i % 4 === 0) yield;
    rasterCell(reg.cells[i], k, (x, y, r2, g, b) => { const o = ((pos[i][1] + y) * W + pos[i][0] + x) * 4; img.data[o] = r2; img.data[o + 1] = g; img.data[o + 2] = b; img.data[o + 3] = 255; });
  }
  a.img = img; a.cast = pos; a.castBytes = (H - H0) * W * 4; a.bytes = W * H * 4;
  return a;
}

// ── 내보내기 ──
const fr = (v) => v - Math.floor(v);
const WALK4 = [0, 1, 2, 1];
export function createCastDraw(scene, proj) {
  const reg = buildCast(scene);
  const S = [0, 0, 0], P = [0, 0, 0], Q = [0, 0, 0];
  const kH = proj.ey[2] / proj.m, kD = proj.m * proj.ey[2] / proj.vd[2];   // 높이 1 m 당 화면 px, 화면 한 줄 아래로 갈 때 지면 깊이 변화(음수)
  const ex = proj.ex;
  let R = null, hi = null, q = 2, KP = 1, KF = 1, o = null, sys = null, v0 = 0, v1 = 0, v2 = 0, v3 = 0, bubbles = true, drawn = 0;
  const bubAt = [];
  const src = (c) => (hi ? hi.cast[c.i] : c.lo);
  // 칸 하나: (X, Y) = 발 자리(지도 px, 격자에 맞춘 값). kind 1 은 줄별 깊이(발 행 = param)
  const put = (c, X, Y, dep, lift = 0) => { const s = src(c); R.sprite(X + c.box[0] / 2, Y - 4 + c.box[1] / 2 - lift, c.w / 2, c.h / 2, s[0], s[1], dep, KP, (8 - c.box[1]) / 2); };
  // 색 그대로·평면 깊이(말풍선·돗자리·연). 깊은 단계는 kind 9, 기본 단계는 KF(render.js 에 평면 kind 가 생기기 전에는 kind 1, 발 행 0 = 평면)
  const flat = (c, x, y, w, h, sy, dep) => { const s = src(c); R.sprite(x, y, w, h, s[0], s[1] + sy, dep, hi ? 9 : KF, 0); };
  const base = (pal, frame, X, Y, dep, lift) => {
    if (hi) { const c = hi.people[pal][frame]; R.sprite(X - 1, Y - 4 - lift, 2, 4.5, c[0], c[1], dep, 10, 4); }
    else R.sprite(X - 1, Y - 4 - lift, 2, 4.5, (pal % PERSON.perRow) * PERSON.cellW * 4 + frame * PERSON.cellW, Math.floor(pal / PERSON.perRow) * PERSON.cellH, dep, 1, 4);
  };
  const POSE = { stand: 0, walk: 1, wave: 2, cheer: 3, cam: 4, point: 5, sit: 6, kneel: 7, run: 8 };
  // 사람 하나. L = { fam, pal, hat, bag, cane, h }(people.js 가 정한 겉모습), 나머지는 이번 프레임 상태.
  function fig(x, y, z, L, pose, dist, face, hop, prop, bubble, t) {
    proj.project(x, y, z, S);
    if (S[0] < v0 || S[0] > v2 || S[1] < v1 || S[1] > v3) return;
    drawn++;
    const X = Math.round(S[0] * q) / q, Y = Math.round(S[1] * q) / q, dep = S[2];
    const lift = hop > 0 ? Math.round(Math.abs(Math.sin(hop * 9)) * 1.2 * q) / q : 0;
    const fam = L.fam, p = POSE[pose] || 0, moving = p === 1 || p === 8;
    let top = 0, od = dep - 0.02;                                   // top = 머리 위로 더 올라간 높이(말풍선 자리, 몸 좌표)
    let adultLike = false;
    if (fam === 'a') {
      adultLike = true;
      const sit = p === 6 ? reg.sit.get(L.pal) : p === 7 ? reg.kneel.get(L.pal) : null;
      if (sit) { put(sit, X, Y, dep, lift); top = p === 6 ? -2.9 : -1.7; adultLike = false; }
      else base(o.season === 3 && L.palW !== undefined ? L.palW : L.pal, moving ? Math.floor(dist / (p === 8 ? 0.62 : 0.45)) & 3 : 1, X, Y, dep, lift);
    } else if (fam === 'hf' || fam === 'hm' || fam === 'g') {
      adultLike = true;
      put((fam === 'hf' ? reg.hf : fam === 'hm' ? reg.hm : reg.guard)[L.pal][moving ? Math.floor(dist / 0.5) & 1 : 2], X, Y, dep, lift);
      if (fam !== 'hf') top = 1;
    } else if (fam === 'k') { put(reg.kid[L.pal][p === 3 || p === 2 ? 3 : moving ? WALK4[Math.floor(dist / (p === 8 ? 0.5 : 0.36)) & 3] : 1], X, Y, dep, lift); top = -2.3; }
    else if (fam === 'hk') { put(reg.hk[L.pal][moving ? Math.floor(dist / 0.4) & 1 : 2], X, Y, dep, lift); top = -2.5; }
    else if (fam === 'dog' || fam === 'cat') { put((fam === 'dog' ? reg.dog : reg.cat)[L.pal][p === 6 ? 2 : moving ? Math.floor(dist / 0.3) & 1 : 0][face > 0 ? 0 : 1], X, Y, dep, lift); top = -6; }
    else if (fam === 'wheel') { put(reg.wheel[L.pal][face > 0 ? 0 : 1], X, Y, dep, 0); top = -2.3; }
    else if (fam === 'stroller') { put(reg.stroller[L.pal][face > 0 ? 0 : 1], X, Y, dep, 0); top = -5; }
    R.shadow(X - (fam === 'dog' || fam === 'stroller' || fam === 'wheel' ? 1.25 : 1), Y, fam === 'cat' ? 1.5 : 2.5, 0.5, 0, 0, dep, 3);
    if (adultLike) {
      const h = L.h, winter = o.season === 3, sk = fam === 'a' ? L.pal % 4 : 0;
      if (fam === 'a') {
        if (L.bag) { put(reg.pack[L.bag - 1], X, Y, od, lift); od -= 0.02; }
        if (p === 8 && moving) { put(reg.runarm[sk][Math.floor(dist / 0.62) & 1], X, Y, od, lift); od -= 0.02; }
        if (winter && h < 0.78 && !L.uniform && !L.runner) { put(reg.coat[Math.floor(h * 131) % reg.coat.length], X, Y, od, lift); od -= 0.02; }
        if (winter && fr(h * 7) < 0.5) { put(reg.scarf[Math.floor(h * 53) % reg.scarf.length], X, Y, od, lift); od -= 0.02; }
        if (L.hat) { put(reg.hats[L.hat - 1], X, Y, od, lift); od -= 0.02; } else if (winter && fr(h * 13) < 0.3) { put(reg.beanie[Math.floor(h * 71) % reg.beanie.length], X, Y, od, lift); od -= 0.02; top = 1; }
        if (L.cane) { put(L.cane === 2 ? reg.broom : reg.cane, X, Y, od, lift); od -= 0.02; }
      } else if (fam !== 'g' && winter) {
        if (fr(h * 7) < 0.6) { put(reg.vest[Math.floor(h * 53) % reg.vest.length], X, Y, od, lift); od -= 0.02; }
        if (fr(h * 11) < 0.45) { put(reg.scarf[Math.floor(h * 31) % reg.scarf.length], X, Y, od, lift); od -= 0.02; }
      }
      // 손짓(기본 사람 위에 맨 팔을 덧그린다)
      if (p === 2 || p === 3) {
        const f = Math.floor(t * 5 + h * 4) & 1, hands = reg.hand[sk];
        if (p === 3 || face > 0) put(hands[2 + f], X, Y, od, lift);
        if (p === 3 || face <= 0) put(hands[f], X, Y, od, lift);
        od -= 0.02; top = Math.max(top, 1);
      } else if (p === 4) { put(reg.cam[sk], X, Y, od, lift); od -= 0.02; }
      else if (p === 5) { put(reg.point[sk][face > 0 ? 1 : 0], X, Y, od, lift); od -= 0.02; }
      if (prop) {
        const c = prop === 'flag' ? reg.flag[L.pal & 1] : prop === 'spear' ? reg.spear : prop === 'banner' ? reg.banner : prop === 'guitar' ? reg.guitar : null;
        if (c) { put(c, X, Y, od, lift); od -= 0.02; if (prop !== 'guitar') top = Math.max(top, 2); }
      }
      // 우산(비)·양산(여름 한낮). 사진 찍는 자세·수문장은 들지 않는다.
      if (fam !== 'g' && p !== 4 && !prop && !L.noUmb) {
        if (o.rain && fr(h * 3.7) < 0.9) { put(reg.umb[Math.floor(h * 211) % reg.umb.length], X, Y, od - 0.02, lift); top = 2.2; }
        else if (o.parasol && fr(h * 5.3) < (fam === 'a' ? 0.07 : 0.2)) { put(reg.parasol[Math.floor(h * 89) % reg.parasol.length], X, Y, od - 0.02, lift); top = 2.2; }
      }
    }
    // 바로 옆 사람과 말풍선이 겹치면 먼저 그린 쪽만 남긴다
    if (bubble && bubbles && reg.bubble[bubble] && !sys.hidden(x, y) && !bubAt.some((b, i) => !(i & 1) && Math.abs(b - X) < 3 && Math.abs(bubAt[i + 1] - Y) < 4)) {
      bubAt.push(X, Y);
      flat(reg.bubble[bubble], X - 1.25, Y - 4 - (top + 7.4) / 2 - lift, 2.5, 3.5, 0, dep - 4);
    }
  }
  // 땅에 깔린 것(돗자리): 0.5 px 띠로 나눠 띠마다 지면 깊이를 준다 → 그 위에 앉은 사람이 가려지지 않는다
  const decal = (c, x, y) => {
    proj.project(x, y, 0, S);
    if (S[0] < v0 || S[0] > v2 || S[1] < v1 || S[1] > v3) return;
    const X = Math.round(S[0] * q) / q, Y = Math.round(S[1] * q) / q, ty = Y - 4 + c.box[1] / 2;
    for (let r = 0; r < c.h / 2; r += 0.5) flat(c, X + c.box[0] / 2, ty + r, c.w / 2, 0.5, r * q, S[2] + (ty + r + 0.5 - S[1]) * kD + 0.1);
  };
  const dot = (x, y, z, col, size = 0.5) => { proj.project(x, y, z, S); R.sprite(Math.round(S[0] * q) / q, Math.round(S[1] * q) / q, size, size, 0, 0, S[2] - 0.5, 6, col); };

  const LOOK_STAND = { fam: 'a', pal: 0, hat: 0, bag: 0, cane: 0, h: 0 };
  return {
    reg,
    // opt: { alpha(시뮬 스텝 사이 보간), view(cam.view()), cw, ch(캔버스 px), season, rain, day }
    emit(R_, sys_, opt) {
      R = R_; sys = sys_; o = opt; drawn = 0;
      hi = R.hi && R.hi.cast ? R.hi : null; q = hi ? hi.SS : 2; KP = hi ? 10 : 1; KF = R.flatKind || 1;
      const view = opt.view, pad = 8;
      v0 = view.originX - pad; v1 = view.originY - pad; v2 = view.originX + opt.cw / view.scale + pad; v3 = view.originY + opt.ch / view.scale + pad + 6;
      bubbles = view.scale >= 1.4; bubAt.length = 0;
      o.parasol = opt.season === 1 && opt.day > 0.7 && !opt.rain;
      const t = sys.time + opt.alpha * SIM_DT, al = opt.alpha;
      const { walkers, ov } = sys;
      for (let i = 0; i < walkers.length; i++) {
        const w = walkers[i];
        if (!w.vis || ov.skip[i]) continue;
        const d = sys.wpos(i, t, P);
        // 화면 밖이면 동행도 건너뛴다(동행은 2 m 안)
        proj.project(P[0], P[1], P[2], S);
        if (S[0] < v0 - 6 || S[0] > v2 + 6 || S[1] < v1 - 6 || S[1] > v3 + 6) continue;
        const face = sys.wdir(i) * w.sx >= 0 ? 1 : -1;
        fig(P[0], P[1], P[2], w.look, w.run ? 'run' : 'walk', d, face, 0, null, w.bub, t);
        for (const f of w.fol) { const d2 = sys.wpos(i, t, Q, f.dd); fig(Q[0] + f.ox, Q[1] + f.oy, Q[2], f.look, 'walk', d2, face, f.hop > 0 ? f.hop : 0, null, f.bub, t); }
      }
      const st = sys.standing;
      for (let i = 0; i < st.length; i++) { const s = st[i]; if (s.vis) fig(s.x, s.y, s.z, s.look, s.pose, 0, s.face, 0, null, s.bub, t); }
      const one = (a) => {
        const x = a.ox + (a.x - a.ox) * al, y = a.oy + (a.y - a.oy) * al;
        const pose = a.moving ? (a.pose === 'run' ? 'run' : 'walk') : a.waveT > 0 && a.pose === 'stand' ? 'wave' : a.pose === 'run' ? 'stand' : a.pose;
        fig(x, y, a.z, a.look || LOOK_STAND, pose, a.dist, a.face, a.hopT, a.prop, a.bubble, t);
      };
      for (const a of sys.actors) if (a.on) one(a);
      for (const g of sys.guests) { one(g); for (const f of g.fol) fig(f.x, f.y, g.z, f.look, f.look.fam === 'dog' && f.sit ? 'sit' : 'stand', 0, g.face, f.hop, null, f.bub, t); }
      // 궁 둘레 러너: 발을 디딜 때마다 반 칸씩 들썩인다
      for (const r of sys.runners || []) {
        if (!r.vis) continue;
        const face = sys.rpos(r, al, P);
        proj.project(P[0], P[1], 0, S);
        if (S[0] < v0 - 12 || S[0] > v2 + 12 || S[1] < v1 - 12 || S[1] > v3 + 12) continue;
        const d0 = r.ou + (r.u - r.ou) * al;
        fig(P[0], P[1], 0, r.look, 'run', d0, face, (Math.floor(d0 / 0.62) & 1) ? 0.024 : 0, null, 0, t);
        for (const f of r.fol) { const fc = sys.rpos(r, al, Q, f.dd), d1 = d0 + f.dd + 40; fig(Q[0], Q[1], 0, f.look, 'run', d1, fc, (Math.floor(d1 / 0.62) & 1) ? 0.024 : 0, null, 0, t); }
      }
      for (const p of sys.props) {
        if (p.sc && !p.sc.on) continue;
        if (p.type === 'haechi') {
          proj.project(p.x, p.y, 0, S);
          if (S[0] < v0 - 6 || S[0] > v2 + 6 || S[1] < v1 - 4 || S[1] > v3 + 10) continue;
          const hx = Math.round(S[0] * q) / q, hy = Math.round(S[1] * q) / q;
          R.shadow(hx - 1.6, hy + 0.1, 6.5, 1.3, 0, 0, S[2], 3);
          put(reg.haechi, hx, hy, S[2]);
          if (opt.day < 0.5) R.light(S[0], S[1] - 2.5, 9, 0.55, 0.5, 0.4);   // 밤에는 옅은 조명
          continue;
        }
        if (p.type === 'mat') decal(reg.mat[p.variant], p.x, p.y);
        else if (p.type === 'kite') {
          const alt = 9 + 1.2 * Math.sin(t * 0.7 + p.ph), sway = 2.2 * Math.sin(t * 0.45 + p.ph * 2);
          proj.project(p.x + 3 + sway, p.y + 3, 0, S);
          if (S[0] < v0 || S[0] > v2 || S[1] - alt * kH < v1 - 20 || S[1] > v3 + 30) continue;
          const c = reg.kite[p.variant], kx = Math.round(S[0] * q) / q, ky = Math.round((S[1] - alt * kH) * q) / q;
          flat(c, kx - 1, ky, c.w / 2, c.h / 2, 0, S[2] - 12);
          proj.project(p.x, p.y, 0, Q);
          for (let k = 1; k <= 7; k++) { const u = k / 8, sag = Math.sin(u * Math.PI) * 1.5; R.sprite(Math.round((Q[0] + 0.6 + (kx - Q[0] - 0.6) * u) * q) / q, Math.round((Q[1] - 3.4 + (ky + 2 - Q[1] + 3.4) * u + sag) * q) / q, 0.25, 0.25, 0, 0, S[2] - 12, 6, 1); }
        } else {
          proj.project(p.x, p.y, 0, S);
          if (S[0] < v0 || S[0] > v2 || S[1] < v1 || S[1] > v3) continue;
          put(p.type === 'snowman' ? reg.snowman : reg.bench, Math.round(S[0] * q) / q, Math.round(S[1] * q) / q, S[2] + (p.type === 'bench' ? 0.25 : 0));
        }
      }
      for (const f of sys.fx) {
        const u = f.t / f.T;
        if (f.type === 'flash') {
          proj.project(f.x, f.y, f.z, S);
          R.sprite(Math.round(S[0] * q) / q - 0.25, Math.round(S[1] * q) / q - 0.25, 0.75, 0.75, 0, 0, S[2] - 1, 4, 0);
          if (opt.day < 0.6) R.light(S[0], S[1] + 2, 12, 0.9, 0.9, 0.8);
        } else if (f.type === 'ball') dot(f.x + (f.x1 - f.x) * u, f.y + (f.y1 - f.y) * u, f.z + Math.sin(u * Math.PI) * 0.9, 3);
        else if (f.type === 'soap') dot(f.x + Math.sin(f.ph + u * 5) * 0.4 + u * f.dx, f.y + u * f.dy, f.z + u * 2.6, u < 0.85 ? 2 : 5, 0.25 + 0.25 * (f.ph % 2 > 1));
      }
      // 걸어가는 사람 머리 위 말풍선(탭했는데 설 수 없는 자리)
      for (const fl of sys.floaters) {
        if (!bubbles) break;
        sys.wpos(fl.wi, t, P); proj.project(P[0], P[1], P[2], S);
        flat(reg.bubble[fl.icon], Math.round(S[0] * q) / q - 1.25, Math.round(S[1] * q) / q - 7.4, 2.5, 3.5, 0, S[2] - 4);
      }
      return drawn;
    },
  };
}
