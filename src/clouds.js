// 흐르는 구름 그림자와 바람 값. 셰이더(render.js 조명 패스)와 테스트가 같은 상수를 쓴다.
// 구름 무늬는 지면(월드 xy, m)에 붙은 절차 잡음이고 시각 uTime 만으로 정해진다(텍스처 없음, 프레임 결정적).
// 지면에서 높이 z 인 점은 해 쪽으로 z 만큼 어긋난 자리의 무늬를 읽는다 → 그림자가 지붕·타워를 타고 넘는다.

// 바람: 북서 → 남동(월드 x 동, y 북). 나뭇잎 돌풍 띠(render.js 알베도 패스)와 구름이 같은 방향으로 간다.
export const WIND = { dir: [0.7071, -0.7071], gust: 11, gust2: 8 };   // m/s: 돌풍 띠 앞머리 두 개의 속도

export const CLOUD = {
  speed: 8,        // m/s(둘째 돌풍 띠와 같다)
  cell: 260,       // 가장 큰 덩어리의 잡음 칸(m). 덩어리 하나가 수백 m
  evolve: 1.12,    // 둘째 옥타브가 조금 더 빨리 흘러 모양이 천천히 바뀐다
  lo: 0.54, hi: 0.72,            // 잡음 → 그림자 문턱(사이가 부드러운 가장자리)
  dark: [0.21, 0.18, 0.12],      // 한낮 맑은 날 그림자 한가운데가 어두워지는 정도(r,g,b: 푸른 기가 남는다)
  maxLean: 2.5,    // 높이 1 m 당 어긋남의 한도(m). 해가 아주 낮을 때 타워 위 무늬가 멀리 달아나지 않게
  maxZ: 400,       // 어긋남에 쓰는 높이 한도(m)
};

const sm = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

// 그림자 세기 0~1: 밤 0, 해 질 녘 옅게, 비 오는 날 아주 옅게, 눈 내리는 겨울엔 절반 아래. on = 설정(칩·?clouds=0)
export function cloudAmount({ day, rain = 0, winter = 0, on = true }) {
  if (!on) return 0;
  return sm(0.25, 0.95, day) * (1 - 0.85 * rain) * (1 - 0.55 * winter);
}

// 높이 1 m 당 지면 무늬가 어긋나는 양(m, 월드 xy). sun = 해 쪽 단위 벡터
export function cloudLean(sun) {
  const z = Math.max(sun[2], 1e-3);
  let x = sun[0] / z, y = sun[1] / z;
  const l = Math.hypot(x, y);
  if (l > CLOUD.maxLean) { x *= CLOUD.maxLean / l; y *= CLOUD.maxLean / l; }
  return [x, y];
}

// 시각 t(초)까지 구름이 흘러간 거리(m, 월드 xy)
export function cloudDrift(t) { return [WIND.dir[0] * CLOUD.speed * t, WIND.dir[1] * CLOUD.speed * t]; }

// ── 셰이더와 같은 식의 JS 판(테스트·검산용. GPU 의 float32 와 끝자리까지 같지는 않다)
const fr = (v) => v - Math.floor(v);
function hash(x, y) {
  let a = fr(x * 0.1031), b = fr(y * 0.1031), c = fr(x * 0.1031);
  const d = a * (b + 33.33) + b * (c + 33.33) + c * (a + 33.33);
  a += d; b += d; c += d;
  return fr((a + b) * c);
}
function vnoise(x, y) {
  const ix = Math.floor(x), iy = Math.floor(y);
  let fx = x - ix, fy = y - iy; fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
  const m = (a, b, t) => a + (b - a) * t;
  return m(m(hash(ix, iy), hash(ix + 1, iy), fx), m(hash(ix, iy + 1), hash(ix + 1, iy + 1), fx), fy);
}
// 지면 (x, y) m 의 구름 그림자 0~1(세기를 곱하기 전)
export function cloudCover(x, y, t) {
  const [dx, dy] = cloudDrift(t), C = CLOUD;
  const ux = (x - dx) / C.cell, uy = (y - dy) / C.cell;
  const vx = (x - dx * C.evolve) / C.cell, vy = (y - dy * C.evolve) / C.cell;
  const n = 0.62 * vnoise(ux, uy) + 0.30 * vnoise(vx * 2.17 + 13.7, vy * 2.17 + 13.7) + 0.08 * vnoise(ux * 4.9 + 5.3, uy * 4.9 + 5.3);
  return sm(C.lo, C.hi, n);
}

// GLSL: COMMON(vnoise) 뒤에 붙인다. uTime 은 붙이는 쪽 셰이더에 이미 있다.
const f = (v) => { const s = String(v); return /[.e]/.test(s) ? s : s + '.0'; };
export const CLOUD_GLSL = `
uniform float uCloud;      // 구름 그림자 세기(밤·끔 0)
uniform vec2 uCloudLean;   // 높이 1 m 당 지면 무늬 어긋남(m)
float cloudCover(vec2 g){
  vec2 w = vec2(${f(WIND.dir[0])}, ${f(WIND.dir[1])}) * (uTime * ${f(CLOUD.speed)});
  vec2 u = (g - w) / ${f(CLOUD.cell)}, v = (g - w * ${f(CLOUD.evolve)}) / ${f(CLOUD.cell)};
  float n = 0.62 * vnoise(u) + 0.30 * vnoise(v * 2.17 + 13.7) + 0.08 * vnoise(u * 4.9 + 5.3);
  return smoothstep(${f(CLOUD.lo)}, ${f(CLOUD.hi)}, n);
}
// 월드 xy 와 높이 z(m)인 면의 색에 곱할 값
vec3 cloudShade(vec2 xy, float z){
  if (uCloud < 0.003) return vec3(1.0);
  return 1.0 - vec3(${CLOUD.dark.map(f).join(', ')}) * (uCloud * cloudCover(xy - uCloudLean * clamp(z, 0.0, ${f(CLOUD.maxZ)})));
}
`;
