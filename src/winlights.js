// 고층 지도(여의도)의 밤 창문: 벽면을 층(가로 띠) × 칸으로 나눠 칸 단위로 켜고 끈다.
// 지도 설정(maps.js)에 windows: WINDOW_GRID 가 있으면 render.js 조명 패스가 이 조각(WINDOW_GLSL)을 쓴다. 경복궁은 예전 식 그대로.
//   · 커튼월(벽면 둘레가 대체로 푸른 유리·금빛 반사 유리) = 사무동: 층고 3.8 m, 칸 1.6 m, 칸 안 창 사각형(아래·위 스팬드럴, 양옆 멀리언)만 켠다.
//   · 그 밖(흰 벽에 그려진 창 = 아파트·석재 건물): 층고 2.9 m, 칸 3 m, 그림의 창 픽셀만 켠다.
//   · 켜진 비율은 시각(0~24시) 곡선 × 층마다 다른 배율. 방(사무동 칸 3~6개, 집 1~2칸)을 한 번에 켜서 층 띠가 읽히게 한다.
//   · 지붕·헬리패드(수직면이 아닌 곳)에는 켜지 않는다.
//   · 층·칸의 주기와 위상은 면마다 그림의 창틀에서 잰다(winfaces.js). 못 잰 면·축은 위 기본값(사무동 3.8 m × 1.6 m, 아파트 2.9 m × 3 m).

export const WINDOW_GRID = {
  office: { floor: 3.8, col: 1.6 },   // m
  home: { floor: 2.9, col: 3.0 },
  bldBand: 24,                        // 건물 구분: 벽 밑동 깊이를 이 폭(m)으로 끊는다
};

// 켜진 비율 곡선 [시각, 비율]: 점 사이 선형. 사무동은 퇴근 뒤 밤이 깊을수록 꺼지고, 아파트는 저녁(19~22시)에 가장 많다.
export const SCHEDULE = {
  office: [[0, 0.12], [3, 0.05], [6, 0.06], [8, 0.35], [17, 0.8], [19, 0.62], [21, 0.4], [23, 0.22], [24, 0.12]],
  home: [[0, 0.3], [2, 0.12], [4, 0.05], [6, 0.18], [8, 0.15], [17, 0.3], [19, 0.55], [21, 0.66], [22.5, 0.56], [24, 0.3]],
};

// 셰이더와 같은 식(점마다 mix 를 이어 붙인다: 지난 구간은 끝값, 지금 구간은 선형, 다음 구간은 그대로)
export function ratioAt(kind, h) {
  const s = SCHEDULE[kind];
  h = ((h % 24) + 24) % 24;
  let r = s[0][1];
  for (let i = 0; i + 1 < s.length; i++) {
    const [t0] = s[i], [t1, v1] = s[i + 1];
    const k = Math.min(1, Math.max(0, (h - t0) / (t1 - t0)));
    r += (v1 - r) * k;
  }
  return r;
}

// 층 하나의 켜진 비율: base = 시각 곡선 값, hf = 층마다 다른 난수(0~1).
// 층마다 갈린다: 일부는 거의 다 켜진 층(야근·청소), 일부는 거의 꺼진 층, 나머지는 base 근처. 다 켜진 층의 몫은 base 를 따라 늘고 준다
// → 층 띠가 읽히고, 층들의 평균은 대략 base(테스트가 확인).
export function floorRatio(base, hf) {
  const full = base * 0.35;
  if (hf < full) return 0.92;
  if (hf > 0.7) return base * 0.1;
  const m = (base * 0.97 - 0.92 * full) / (0.7 - full);   // 나머지 층의 평균: 전체 평균이 base 가 되게
  return Math.min(1, m * (0.5 + (hf - full) / (0.7 - full)));
}

const F = (v) => (Number.isInteger(v) ? v.toFixed(1) : String(v));
const sched = (name, s) => {
  let g = `float ${name}(float h){ h = mod(h, 24.0); float r = ${F(s[0][1])};`;
  for (let i = 0; i + 1 < s.length; i++) g += ` r = mix(r, ${F(s[i + 1][1])}, clamp((h - ${F(s[i][0])}) / ${F(s[i + 1][0] - s[i][0])}, 0.0, 1.0));`;
  return g + ' return r; }';
};

// 조명 패스에 들어가는 함수들. hash3 은 render.js COMMON 의 것.
export const WINDOW_GLSL = `
${sched('winOffice', SCHEDULE.office)}
${sched('winHome', SCHEDULE.home)}
float winFloorRatio(float base, float hf){
  float full = base * 0.35;
  if (hf < full) return 0.92;
  if (hf > 0.7) return base * 0.1;
  float m = (base * 0.97 - 0.92 * full) / (0.7 - full);
  return min(1.0, m * (0.5 + (hf - full) / (0.7 - full)));
}
// 커튼월 유리 색: 푸른 유리(어두운 띠·옅은 하늘색 포함) 또는 금빛 반사 유리(63빌딩). 붉은 기둥·벽돌(초록/빨강 < 0.68)은 아니다.
bool winGold(vec3 c){ float l = dot(c, vec3(.3,.59,.11)), s = max(c.r, max(c.g, c.b)) - min(c.r, min(c.g, c.b));
  return c.g > c.r * 0.68 && c.g < c.r * 0.88 && c.b < c.r * 0.62 && s > 0.15 && l > 0.2 && l < 0.85; }
bool winGlassC(vec3 c){ return (c.b > c.r * 1.05 && dot(c, vec3(.3,.59,.11)) < 0.85) || winGold(c); }
// 창 하나의 빛(0 = 꺼짐). zc = 벽 위 높이(m), xm = 화면 가로 위치(m), bld = 건물 번호(켜짐 난수 씨앗), glassy = 커튼월, pane = 이 텍셀이 창(그림 기준),
// th = 이 텍셀의 세로 크기(벽 높이 m), tw = 가로 크기(m), clock = 시각(시), t = 흐른 시간(초).
// gv·gh = 그림에서 잰 창 격자(winfaces.js): (주기 m, 창 구간이 시작하는 위상 m, 창 구간 폭(주기 비율), -). 주기 0 = 못 찾음 → 기본 층고·칸 폭.
// 반환 xyz = 빛 색, w = 켜짐(0/1)
vec4 winCell(float zc, float xm, float bld, bool glassy, bool pane, float th, float tw, float clock, float t, vec4 gv, vec4 gh){
  float FLH = gv.x > 0.0 ? gv.x : glassy ? ${F(WINDOW_GRID.office.floor)} : ${F(WINDOW_GRID.home.floor)};
  float WC = gh.x > 0.0 ? gh.x : glassy ? ${F(WINDOW_GRID.office.col)} : ${F(WINDOW_GRID.home.col)};
  float fz = (zc - (gv.x > 0.0 ? gv.y : 0.0)) / FLH, fl = floor(fz); fz -= fl;
  float cx = (xm - (gh.x > 0.0 ? gh.y : 0.0)) / WC, col = floor(cx), fx = cx - col;
  // 창틀(그림의 창 구간 밖): 텍셀이 굵어도(z1·z2) 층마다 한 줄은 어둡게 남게 텍셀 크기 이상. 세로 창틀은 텍셀이 칸 1/4 보다 가늘 때만(z4·z8)
  if (gv.x > 0.0) { if (fz > min(gv.z, 1.0 - th * 1.05 / FLH)) return vec4(0.0); }
  else if (glassy) { float sp = max(0.24, th * 1.05 / FLH); if (fz < sp || fz > 0.94) return vec4(0.0); }
  if (tw < WC * 0.25) {
    if (gh.x > 0.0) { if (glassy && fx > min(gh.z, 1.0 - tw * 1.05 / WC)) return vec4(0.0); }   // 아파트는 그림의 창 픽셀(pane)이 이미 가로를 가른다: 잰 칸은 집 나누기에만
    else if (glassy && (fx < 0.12 || fx > 0.88)) return vec4(0.0);
  }
  if (!glassy && !pane) return vec4(0.0);
  float hf = hash3(vec3(fl, bld, 7.0));
  float fr = winFloorRatio(glassy ? winOffice(clock) : winHome(clock), hf);
  float rw = glassy ? 3.0 + floor(hash3(vec3(fl, bld, 3.0)) * 4.0) : max(1.0, floor((3.0 + 3.0 * hash3(vec3(fl, bld, 3.0))) / WC + 0.5));   // 방 = 사무동 칸 3~6 개, 집 3~6 m 를 한 번에
  float room = floor(col / rw);
  float rr = hash3(vec3(room, fl, bld));
  bool on = rr < fr;
  if (hash3(vec3(col, fl, bld + 0.5)) < 0.08) on = !on;                       // 방 안에서 칸 몇 개는 따로
  if (hash3(vec3(room, fl, floor(t / 45.0 + rr * 11.0))) < 0.05) on = !on;    // 가끔 방 하나가 켜지거나 꺼진다
  if (!on) return vec4(0.0);
  float hc = hash3(vec3(room, fl, bld + 2.0));
  vec3 e = glassy ? (hc < 0.7 ? vec3(0.84, 0.92, 1.0) : vec3(0.98, 0.93, 0.80))
                  : (hc < 0.65 ? vec3(1.0, 0.80, 0.50) : vec3(0.98, 0.92, 0.76));
  return vec4(e, 1.0);
}
`;
