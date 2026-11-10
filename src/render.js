// WebGL2 렌더러.
// 모든 합성은 지도 원본 해상도(2752×1696) FBO 에서 텍셀 단위로 한다(픽셀아트 일관성, 깊이 가림이 텍셀 정합).
//   A  albedo : 배경(계절 변환) → 그림자 → 스프라이트(배경 깊이와 픽셀 단위 비교)
//   L  light  : 가로등·전조등 빛 웅덩이(1/2 해상도, 가산)
//   B  lit    : 낮/밤 조명, 창문 불빛, 구름 그림자, 디오라마 옆면
//   →  screen : 카메라 변환 + sharp-bilinear 확대 / mip 축소 + 눈·비
const smoothstep = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const SPR_STRIDE = 9;   // dstX,dstY,w,h, srcX,srcY, depth, kind, param
const LGT_STRIDE = 6;   // x,y,radius, r,g,b

const COMMON = (P, L2 = false) => `#version 300 es
precision highp float;
precision highp int;
${L2 ? '#define LOOK2' : ''}
const vec2 MAPSZ = vec2(${P.W}.0, ${P.H}.0);
const vec3 EX = vec3(${P.ex.join(',')});
const vec3 EY = vec3(${P.ey.join(',')});
const vec3 VD = vec3(${P.vd.join(',')});
const float CX = ${P.cx}; const float CY = ${P.cy}; const float CAMVD = ${P.camDotVd};
const float MPP = ${P.m.toFixed(4)};
uniform sampler2D uDepth;
uniform float uF;   // 합성 해상도 배율(1 또는 2). gl_FragCoord / uF = 지도 px
float bgDepth(ivec2 p){
  p = clamp(p, ivec2(0), ivec2(MAPSZ) - 1);
  vec2 rg = floor(texelFetch(uDepth, p, 0).rg * 255.0 + 0.5);
  float v = rg.r * 256.0 + rg.g;
  return v > 65534.5 ? 1.0e9 : 2060.0 + v * 0.02;
}
float groundDepth(float py){ float v = (MAPSZ.y * 0.5 - py) * MPP + CY; return -v * EY.z / VD.z - CAMVD; }
float heightOf(ivec2 p, float d){ return VD.z * (d - groundDepth(float(p.y) + 0.5)); }
vec3 worldOf(ivec2 p, float d){
  float u = (float(p.x) + 0.5 - MAPSZ.x * 0.5) * MPP + CX;
  float v = (MAPSZ.y * 0.5 - float(p.y) - 0.5) * MPP + CY;
  return u * EX + v * EY + (d + CAMVD) * VD;
}
// 수직면이면 1. 벽에서는 화면 1px 위로 갈 때 높이가 MPP/EY.z 만큼 오른다.
float wallness(ivec2 p){
  float d0 = bgDepth(p + ivec2(0,-1)), d1 = bgDepth(p + ivec2(0,1));
  if (d0 > 1.0e8 || d1 > 1.0e8) return 0.0;
  float dz = heightOf(p + ivec2(0,-1), d0) - heightOf(p + ivec2(0,1), d1);
  float per = 2.0 * MPP / EY.z;
  return smoothstep(0.45, 0.8, dz / per) * (1.0 - smoothstep(1.6, 2.4, dz / per));
}
float hash(vec2 p){ vec3 q = fract(vec3(p.xyx) * .1031); q += dot(q, q.yzx + 33.33); return fract((q.x + q.y) * q.z); }
float hash3(vec3 p){ p = fract(p * .1031); p += dot(p, p.zyx + 31.32); return fract((p.x + p.y) * p.z); }
float vnoise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(hash(i), hash(i+vec2(1,0)), f.x), mix(hash(i+vec2(0,1)), hash(i+vec2(1,1)), f.x), f.y); }
float fbm(vec2 p){ return 0.5*vnoise(p) + 0.25*vnoise(p*2.03+7.1) + 0.125*vnoise(p*4.01+3.3) + 0.125*vnoise(p*8.1); }
`;

const VS_FULL = `#version 300 es
void main(){ vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2); gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0); }`;

const FS_ALBEDO = (P) => COMMON(P) + `
uniform sampler2D uBg, uSem;
uniform float uBgScale;
uniform vec4 uSeason;   // 봄, 여름, 가을, 겨울 가중치
uniform float uTime, uDay, uRain;
out vec4 o;
int semAt(ivec2 q){ q = clamp(q, ivec2(0), ivec2(MAPSZ) - 1); return int(texelFetch(uSem, q, 0).r * 255.0 + 0.5); }
// 배경은 0.25 m/px(지도 px 의 2배). 1배 합성일 때는 mip 1(2×2 평균)을 읽는다.
// off = 그림 픽셀 단위 가로 이동(나뭇잎·물결). 1배 합성에서는 옮긴 2×2 를 직접 평균한다.
vec3 bgRead(ivec2 p, ivec2 fp, int off){
  if (uBgScale > 1.5) {
    if (uF > 1.5) return texelFetch(uBg, fp + ivec2(off, 0), 0).rgb;
    if (off == 0) return texelFetch(uBg, p, 1).rgb;
    ivec2 b = p * 2 + ivec2(off, 0);
    return 0.25 * (texelFetch(uBg, b, 0).rgb + texelFetch(uBg, b + ivec2(1, 0), 0).rgb + texelFetch(uBg, b + ivec2(0, 1), 0).rgb + texelFetch(uBg, b + ivec2(1, 1), 0).rgb);
  }
  return texelFetch(uBg, p + ivec2(off, 0), 0).rgb;
}
void main(){
  ivec2 p = ivec2(gl_FragCoord.xy / uF);
  ivec2 fp = ivec2(gl_FragCoord.xy);
  float d = bgDepth(p);
  if (d > 1.0e8) { o = vec4(bgRead(p, fp, 0), 0.0); return; }
  // 그림 픽셀 좌표(움직임은 이 격자 단위로만 한다)와 지도 px 당 그림 픽셀 수
  int apm = uBgScale > 1.5 ? 2 : 1;
  ivec2 a = uBgScale > 1.5 ? (uF > 1.5 ? fp : p * 2) : p;
  vec2 am = vec2(a) / float(apm);
  float z = heightOf(p, d);
  vec3 wp = worldOf(p, d);
  // 의미 클래스(밑그림에서 온 맵): 2 도로, 3 녹지, 4 수면, 5 궁궐 마당, 6/7 건물 지붕/벽, 8/9 궁궐 지붕/벽, 10 수목, 11 보행로
  int sem = semAt(p);
  int off = 0;
  if (sem == 10) {
    // 나뭇잎 흔들림: 수관을 4×3 그림 px 조각(벽돌 배치)으로 나눠 조각마다 1px(돌풍 때 가끔 2px) 가로로 옮긴다.
    // 돌풍 = 북서에서 남동으로 지나가는 띠. 앞머리는 저주파 노이즈로 구불게 해서 직선 띠로 안 보이게.
    float s = dot(wp.xy, vec2(0.7071, -0.7071)) + 80.0 * vnoise(wp.xy * 0.005);
    float g1 = fract((s - uTime * 11.0) / 560.0), g2 = fract((s + 190.0 - uTime * 8.0) / 350.0);
    float gust = max(smoothstep(0.0, 0.03, g1) * (1.0 - smoothstep(0.05, 0.16, g1)),
                     0.6 * smoothstep(0.0, 0.04, g2) * (1.0 - smoothstep(0.06, 0.18, g2)));
    float calm = 0.18 + 0.16 * vnoise(wp.xy * 0.02 + uTime * 0.05);
    vec2 cell = vec2(ivec2(a.x + ((a.y / 3) & 1) * 2, a.y) / ivec2(4, 3));
    float ph = hash(cell + 17.0);
    // 시계 두 개(3 Hz, 돌풍 때 7 Hz). 주기를 연속으로 바꾸면 uTime 이 클 때 계단이 폭주한다.
    float stp = gust > ph ? floor(uTime * 7.0 + ph * 5.0) + 1000.0 : floor(uTime * 3.0 + ph * 5.0);
    float r = hash3(vec3(cell, stp));
    float pm = mix(calm, 0.85, gust) * (1.0 - 0.35 * uSeason.w);   // 겨울 맨가지는 덜 흔들린다
    if (r < pm) {
      off = hash3(vec3(cell, stp + 31.0)) < 0.5 ? -1 : 1;
      if (gust > 0.45 && r < pm * 0.3) off *= 2;
    }
    // 원본 텍셀도 수목일 때만 옮긴다 → 수관 가장자리가 벽·지붕 위로 번지지 않고 벽은 안 흔들린다
    if (off != 0 && (semAt((a + ivec2(off, 0)) / apm) != 10 || semAt((a + ivec2(off / 2, 0)) / apm) != 10)) off = 0;
  }
  // 물결 너울: 그림 px 줄이 천천히 지나가는 사인파를 따라 1px 씩 좌우로 밀린다(6 Hz 계단). 얼면 멈춘다.
  float tq = floor(uTime * 6.0) / 6.0;
  float swell = 5.0 * vnoise(am * 0.03) - tq * 1.7;
  if (sem == 4 && uSeason.w < 0.5) {
    off = int(floor(sin(am.y * 1.1 + am.x * 0.12 + swell) * 1.2 + 0.5));
    if (off != 0 && semAt((a + ivec2(off, 0)) / apm) != 4) off = 0;
  }
  vec3 c = bgRead(p, fp, off);
  float lum = dot(c, vec3(.3,.59,.11));
  float wall = wallness(p);
  float tree = sem == 10 ? 1.0 : 0.0;
  float lawn = sem == 3 ? 1.0 : 0.0;
  float water = sem == 4 ? 1.0 : 0.0;
  float clump = hash(floor(wp.xy / 5.0));
  // 계절 잡음은 옮겨 온 원본 텍셀 기준(꽃·단풍 점이 잎과 함께 움직이게)
  float fine = hash(vec2(uF > 1.5 ? fp + ivec2(off, 0) : fp));
  // 봄: 벚꽃(일부 나무) + 연두
  if (uSeason.x > 0.0) {
    vec3 blossom = mix(vec3(1.0,0.74,0.84), vec3(1.0,0.90,0.94), fine) * (0.45 + lum * 1.25);
    vec3 fresh = c * vec3(1.06, 1.10, 0.80);
    vec3 s = mix(fresh, blossom, step(clump, 0.55) * step(0.25, fine));
    c = mix(c, s, tree * uSeason.x);
    c = mix(c, c * vec3(1.03,1.06,0.90), lawn * uSeason.x);
  }
  // 가을: 단풍
  if (uSeason.z > 0.0) {
    vec3 pal = clump < 0.38 ? vec3(0.86,0.36,0.12) : (clump < 0.72 ? vec3(0.93,0.66,0.16) : vec3(0.70,0.17,0.13));
    pal = mix(pal, vec3(0.42,0.52,0.20), step(0.9, hash(floor(wp.xy / 5.0) + 9.0)));
    vec3 s = pal * (0.35 + lum * 1.55) + (fine - 0.5) * 0.06;
    c = mix(c, s, tree * uSeason.z);
    c = mix(c, vec3(lum) * vec3(1.25, 1.08, 0.62), lawn * uSeason.z * 0.75);
  }
  // 겨울: 앙상한 나무, 위를 향한 면에 눈, 얼어붙은 연못
  if (uSeason.w > 0.0) {
    vec3 bare = vec3(0.50,0.45,0.42) * (0.4 + lum * 1.3);
    c = mix(c, bare, tree * uSeason.w * 0.85);
    float road = sem == 2 ? 1.0 : 0.0;
    float cover = (1.0 - wall) * (0.62 + 0.38 * vnoise(wp.xy * 0.35)) * (1.0 - road * 0.82);
    cover *= mix(1.0, 0.55 + 0.45 * step(0.35, fine), tree);
    vec3 snow = vec3(0.90,0.93,0.98) * (0.80 + 0.20 * smoothstep(0.2, 0.8, lum));
    c = mix(c, snow, clamp(cover, 0.0, 1.0) * uSeason.w * (1.0 - water));
    c = mix(c, vec3(0.74,0.84,0.91) * (0.9 + 0.1 * fine), water * uSeason.w);
  }
  // 물결 마루·골(너울과 같은 파를 위상만 밀어서), 낮의 드문 반짝임, 빗방울 동심원. 얼면 꺼진다.
  float liquid = water * (1.0 - uSeason.w);
  if (liquid > 0.3) {
    float crest = sin(am.y * 1.1 + am.x * 0.12 + swell + 1.3);
    // 마루·골 줄을 가로로 잘라 짧은 획으로(줄자로 그은 평행선처럼 안 보이게). 획 자체도 천천히 흘러간다.
    float dash = step(0.52, vnoise(vec2(am.x * 0.09 - tq * 0.4, am.y * 0.55)));
    c *= 1.0 + liquid * dash * (0.06 * step(0.85, crest) - 0.04 * step(crest, -0.9));
    // 반짝임: 마루 위 2px 칸, 칸마다 제 박자로 켜졌다 꺼진다
    vec2 gc = vec2(a.x / 2, a.y);
    float gl = hash3(vec3(gc, floor(uTime * 3.0 + hash(gc * 0.37) * 5.0)));
    c = mix(c, vec3(1.0, 0.98, 0.92), liquid * uDay * step(0.9992, gl) * step(0.2, crest));
    if (uRain > 0.01) {
      // 빗방울: 9×9 그림 px 칸마다 0.8 초에 한 번 떨어져 반지름 0→2px 로 번진다(세로는 35° 시점이라 눌림)
      vec2 ci = floor(vec2(a) / 9.0);
      float tt = uTime / 0.8 + hash(ci + 3.1);
      float k = floor(tt), f = fract(tt);
      vec2 ctr = ci * 9.0 + 2.0 + floor(vec2(hash3(vec3(ci, k)), hash3(vec3(ci, k + 7.0))) * 5.0);
      vec2 dd = (vec2(a) - ctr) * vec2(1.0, 1.75);
      float ring = step(abs(length(dd) - floor(f * 3.0)), 0.5) * step(hash3(vec3(ci, k + 13.0)), uRain * 0.7);
      c = mix(c, vec3(0.86, 0.92, 0.98), liquid * ring * (1.0 - f) * 0.55);
    }
  }
  o = vec4(c, 0.0);
}`;

const VS_SPRITE = (P, L2 = false) => `#version 300 es
precision highp float;
${L2 ? '#define LOOK2' : ''}
layout(location=0) in vec2 aCorner;
layout(location=1) in vec4 aDst;
layout(location=2) in vec4 aSrc;   // srcX, srcY, depth, kind
layout(location=3) in float aParam;
const vec2 MAPSZ = vec2(${P.W}.0, ${P.H}.0);
out vec2 vSrc; out vec2 vLocal; flat out float vDepth; flat out float vKind; flat out float vParam; flat out vec2 vSize;
void main(){
  vec4 dst = aDst;
#ifdef LOOK2
  // 룩 2: 사람 발밑 그림자(가로로 긴 띠)를 해 반대쪽으로 반 px 민 타원 칸으로 키운다. 새 그림자(정사각)는 그대로.
  if (aSrc.w > 2.5 && aSrc.w < 3.5 && aDst.z >= aDst.w * 3.0) dst = vec4(aDst.x + (aDst.z - 0.5) * 0.5 - 1.25, aDst.y - 0.5, 3.5, 1.5);
#endif
  vec2 px = dst.xy + aCorner * dst.zw;
  // 아틀라스는 지도 px 의 2배 해상도(geom.js SPRITE_SCALE)
  vLocal = aCorner * dst.zw; vSrc = aSrc.xy + vLocal * 2.0;
  vDepth = aSrc.z; vKind = aSrc.w; vParam = aParam; vSize = dst.zw;
  gl_Position = vec4(px / MAPSZ * 2.0 - 1.0, 0.0, 1.0);
}`;

// kind: 0 차량, 1 사람, 2 차량 그림자, 3 단색 그림자(사람·새), 4 발광 점(전조등/미등), 5 신호등, 6 새(단색 px)
const FS_SPRITE = (P, L2 = false) => COMMON(P, L2) + `
uniform sampler2D uVeh, uVehDepth, uVehShadow, uPeople;
uniform vec3 uShadowTint;
uniform float uShadowAmt;
in vec2 vSrc; in vec2 vLocal; flat in float vDepth; flat in float vKind; flat in float vParam; flat in vec2 vSize;
out vec4 o;
void main(){
  ivec2 p = ivec2(gl_FragCoord.xy / uF);
  ivec2 s = ivec2(floor(vSrc));
  float bd = bgDepth(p);
  int k = int(vKind + 0.5);
  if (k == 0) {
    vec4 c = texelFetch(uVeh, s, 0);
    float code = floor(texelFetch(uVehDepth, s, 0).r * 255.0 + 0.5);
    if (c.a < 0.5 || code < 0.5) discard;
    float fd = vDepth + (code - 128.0) * 0.1;
    if (!(bd > fd - 0.6)) discard;
#ifdef LOOK2
    float l = dot(c.rgb, vec3(.3,.59,.11));
    c.rgb = vec3(l) + (c.rgb - l) * 0.8;   // 차 채도 −20%
#endif
    o = vec4(c.rgb, 0.0);
  } else if (k == 1) {
    vec4 c = texelFetch(uPeople, s, 0);
    if (c.a < 0.5) discard;
    float row = floor(vLocal.y);
    float fd = vDepth + VD.z * (max(0.0, vParam - row) * MPP / EY.z);
    if (!(bd > fd - 0.35)) discard;
#ifdef LOOK2
    // 옷: 색상은 두고 채도 낮추고 밝게, 검정은 짙은 남갈색
    float l = dot(c.rgb, vec3(.3,.59,.11));
    vec3 m = vec3(l) + (c.rgb - l) * 0.6;
    m = mix(m, vec3(0.94, 0.92, 0.88), 0.08);
    c.rgb = mix(m, vec3(0.20, 0.18, 0.23), 1.0 - smoothstep(0.07, 0.2, l));
#endif
    o = vec4(c.rgb, 0.0);
  } else if (k == 2) {
    float a = texelFetch(uVehShadow, s, 0).r;
    if (a < 0.5 || !(bd > vDepth - 0.6)) discard;
    o = vec4(mix(vec3(1.0), uShadowTint, uShadowAmt), 1.0);
  } else if (k == 3) {
    if (!(bd > vDepth - 0.35)) discard;
#ifdef LOOK2
    vec2 e = (vLocal - vSize * 0.5) / (vSize * 0.5);
    if (vSize.x > 3.0 && dot(e, e) > 1.0) discard;   // 사람: 타원
#endif
#ifdef LOOK2
    o = vec4(mix(vec3(1.0), uShadowTint, uShadowAmt * (vSize.x > 3.0 ? 0.7 : 1.0)), 1.0);
#else
    o = vec4(mix(vec3(1.0), uShadowTint, uShadowAmt), 1.0);
#endif
  } else if (k == 4) {
    if (!(bd > vDepth - 0.6)) discard;
    o = vec4(vParam > 0.5 ? vec3(1.0, 0.16, 0.10) : vec3(1.0, 0.95, 0.72), 1.0);
  } else if (k == 5) {
    if (!(bd > vDepth - 0.6)) discard;
    o = vec4(vParam < 0.5 ? vec3(0.20, 0.95, 0.55) : (vParam < 1.5 ? vec3(1.0, 0.78, 0.15) : vec3(1.0, 0.18, 0.12)), 1.0);
  } else {
    // 6 새: 단색 그림 px. vParam = 팔레트 번호(birds.js BIRD_COLORS 와 같은 순서)
    if (!(bd > vDepth - 0.35)) discard;
    int ci = int(vParam + 0.5);
    vec3 col = ci == 0 ? vec3(0.50, 0.53, 0.60) : ci == 1 ? vec3(0.27, 0.29, 0.36) : ci == 2 ? vec3(0.74, 0.75, 0.80)
             : ci == 3 ? vec3(0.96, 0.96, 0.93) : ci == 4 ? vec3(0.07, 0.08, 0.11) : vec3(0.90, 0.92, 0.95);
    o = vec4(col, 0.0);
  }
}`;

const VS_LIGHT = (P) => `#version 300 es
precision highp float;
layout(location=0) in vec2 aCorner;
layout(location=1) in vec3 aPos;   // x, y, radius (지도 px)
layout(location=2) in vec3 aCol;
const vec2 MAPSZ = vec2(${P.W}.0, ${P.H}.0);
out vec2 vQ; out vec3 vCol;
void main(){
  vQ = aCorner * 2.0 - 1.0; vCol = aCol;
  // 지면 위의 원은 화면에서 세로로 눌린 타원(고도 35°)
  vec2 px = aPos.xy + vQ * aPos.z * vec2(1.0, 0.62);
  gl_Position = vec4(px / MAPSZ * 2.0 - 1.0, 0.0, 1.0);
}`;
const FS_LIGHT1 = `#version 300 es
precision highp float;
in vec2 vQ; in vec3 vCol; out vec4 o;
void main(){ float r = length(vQ); float a = clamp(1.0 - r, 0.0, 1.0); o = vec4(vCol * a * a, 1.0); }`;
// 룩 2 빛: 역제곱 근사 감쇠(가장자리에서 0). RGBA8 포화를 막으려 ×0.25 로 담고 합성에서 ×4.
const FALLOFF = `float falloff(float r){ return max(0.0, (1.0 / (1.0 + 16.0 * r * r) - 0.0588) * 1.0625); }`;
const FS_LIGHT = (L2 = false) => L2 ? `#version 300 es
precision highp float;
in vec2 vQ; in vec3 vCol; out vec4 o;
${FALLOFF}
void main(){ o = vec4(vCol * falloff(length(vQ)) * 0.25, 1.0); }` : FS_LIGHT1;

// 룩 2 정적 빛(가로등·궁궐 처마·업라이트·창문 빛)을 절반 해상도 맵에 한 번 굽는다.
// 광원마다 높이 제한, 면 방향, 수신점→광원 깊이 차폐(6 탭)를 따진다. 매 프레임 비용 없음.
const VS_BAKE = (P) => `#version 300 es
precision highp float;
layout(location=0) in vec2 aCorner;
layout(location=1) in vec3 aPos;   // x, y(광원 바닥, 지도 px), 반경
layout(location=2) in vec3 aCol;
layout(location=3) in float aH;    // 광원 높이(m)
const vec2 MAPSZ = vec2(${P.W}.0, ${P.H}.0);
out vec2 vQ; flat out vec3 vCol; flat out vec3 vL;
void main(){
  vQ = aCorner * 2.0 - 1.0; vCol = aCol; vL = vec3(aPos.xy, aH);
  vec2 px = aPos.xy + vQ * aPos.z * vec2(1.0, 0.62);
  gl_Position = vec4(px / MAPSZ * 2.0 - 1.0, 0.0, 1.0);
}`;
const FS_BAKE = (P) => COMMON(P, true) + `
in vec2 vQ; flat in vec3 vCol; flat in vec3 vL; out vec4 o;
${FALLOFF}
// 면 법선: 단차 쪽을 피해 가까운 이웃으로 한쪽 차분
vec3 surfNormal(ivec2 p, float d){
  ivec2 dx = ivec2(1, 0), dy = ivec2(0, 1);
  float l = bgDepth(p - dx), r = bgDepth(p + dx), u = bgDepth(p - dy), w = bgDepth(p + dy);
  vec3 c = worldOf(p, d);
  vec3 a = abs(r - d) < abs(l - d) ? worldOf(p + dx, r) - c : c - worldOf(p - dx, l);
  vec3 b = abs(w - d) < abs(u - d) ? worldOf(p + dy, w) - c : c - worldOf(p - dy, u);
  vec3 n = cross(b, a);
  return dot(n, n) > 1.0e-8 ? normalize(n) : vec3(0.0, 0.0, 1.0);
}
void main(){
  float a = falloff(length(vQ));
  if (a <= 0.0) discard;
  ivec2 p = ivec2(gl_FragCoord.xy * 2.0);
  float d = bgDepth(p);
  if (d > 1.0e8) discard;
  vec3 rw = worldOf(p, d);
  float z = heightOf(p, d);
  ivec2 ci = ivec2(floor(vL.xy));
  vec3 v = worldOf(ci, groundDepth(float(ci.y) + 0.5)) + vec3(0.0, 0.0, vL.z) - rw;
  float len = length(v);
  // 광원보다 높은 지붕·윗면은 못 받고, 벽은 위로 갈수록 옅게(처마 밑 빛은 벽 아래로만)
  float vis = mix(1.0 - step(vL.z + 0.4, z), 1.0 - smoothstep(vL.z + 1.0, vL.z + 9.0, z), step(0.5, wallness(p)));
  vis *= smoothstep(-0.1, 0.3, dot(surfNormal(p, d), v / max(len, 1.0e-3)));
  for (int i = 1; i <= 6; i++) {
    if (vis <= 0.0) break;
    vec3 P = v * (float(i) / 7.0);
    if (length(P) < 1.0 || len - length(P) < 0.8) continue;
    ivec2 q = p + ivec2(floor(vec2(dot(P, EX), -dot(P, EY)) / MPP + 0.5));
    float gap = (d + dot(P, VD)) - bgDepth(q);
    if (gap > 0.6 && gap < 25.0) vis = 0.0;
  }
  if (vis <= 0.0) discard;
  o = vec4(vCol * a * vis * 0.25, 1.0);
}`;
// 룩 2 블룸(지도 공간): 밝은 부분만 뽑아 1/2 → 1/4 로 줄인다. 화면 패스에서 가산만(그림은 안 흐린다).
const FS_BRIGHT = `#version 300 es
precision highp float;
uniform sampler2D uSrc; uniform float uF, uThr; out vec4 o;
void main(){
  ivec2 b = ivec2(gl_FragCoord.xy) * 2;
  vec3 s = vec3(0.0);
  for (int i = 0; i < 4; i++) {
    vec3 c = texelFetch(uSrc, (b + ivec2(i & 1, i >> 1)) * int(uF), 0).rgb;
    float l = max(c.r, max(c.g, c.b));
    s += c * max(0.0, l - uThr) / max(l, 1.0e-3);
  }
  o = vec4(s * 0.25, 1.0);
}`;
const FS_BLUR = `#version 300 es
precision highp float;
uniform sampler2D uSrc; uniform vec2 uTexel; out vec4 o;   // uTexel = 원본(1/2) 텍셀 크기
void main(){
  vec2 uv = gl_FragCoord.xy * 2.0 * uTexel;
  vec3 s = vec3(0.0);
  for (int i = 0; i < 4; i++) {
    vec2 k = vec2(i & 1, i >> 1) * 2.0 - 1.0;
    s += texture(uSrc, uv + k * uTexel).rgb + 0.5 * texture(uSrc, uv + k * 3.0 * uTexel).rgb;
  }
  o = vec4(s / 6.0, 1.0);
}`;

const FS_LIT = (P, L2 = false) => COMMON(P, L2) + `
uniform sampler2D uAlbedo, uLight, uSem, uCls;
uniform float uDay, uDusk, uTime, uLateNight, uDebug;
uniform vec4 uSeason;
uniform vec4 uPalace; // 궁궐 로컬 경계 x0,y0,x1,y1
out vec4 o;
#ifdef LOOK2
// ── 룩 2(세련된 픽셀아트): 깊이로 만든 그림자·접지 음영 + 색 보정. 모두 텍셀 단위 계단값(흐림 없음).
uniform vec3 uSun;        // 해 쪽 단위 벡터(월드). 방위는 장면 sun 고정, 고도만 시각 따라
uniform vec3 uShadeCol;   // 그림자 색(시각 따라)
uniform float uSunAmt;    // 해 그림자 세기(밤 0)
uniform float uRayLen;    // 해 쪽으로 짚는 거리(m)
uniform float uRain;
uniform sampler2D uStatic;  // 구운 정적 빛(×0.25)
uniform float uLampOn;      // 정적 빛 세기(밤 1)
const float NB = 1.22;    // 밤 불빛(궁궐 조명·창문·가로등) 세기: 색 보정 뒤에도 예전 룩보다 또렷하게
// 해 쪽으로 깊이를 짚어 가며 가림 여부. 가까이서 막히면 1, 멀리서만 막히면 0.5(계단 반그림자).
float castShadow(ivec2 p, float d){
  vec2 sp = vec2(dot(uSun, EX), -dot(uSun, EY)) / MPP;   // 1 m 당 화면 px
  float sd = dot(uSun, VD);                               // 1 m 당 깊이 변화(카메라 쪽이 −)
  for (int i = 1; i <= 12; i++) {
    float t = float(i) / 12.0 * uRayLen;
    ivec2 q = p + ivec2(floor(sp * t + 0.5));
    float gap = (d + sd * t) - bgDepth(q);
    if (gap > 0.6 + 0.03 * t && gap < 28.0) return i <= 7 ? 1.0 : 0.5;
  }
  return 0.0;
}
// 건물 밑동 접지 음영: 둘레 8 점이 이 면보다 얼마나 높은가. 수평으로 가까운 점만(지붕 실루엣 뒤 땅에 테가 생기지 않게).
float contactAO(ivec2 p, float d, float z){
  vec3 w0 = worldOf(p, d);
  float occ = 0.0;
  for (int i = 0; i < 8; i++) {
    float a = float(i) * 0.7854;
    ivec2 q = p + ivec2(floor(vec2(cos(a), sin(a)) * 3.0 + 0.5));
    float dq = bgDepth(q);
    if (dq > 1.0e8 || length(worldOf(q, dq).xy - w0.xy) > 3.0) continue;
    occ += clamp((heightOf(q, dq) - z - 0.8) / 2.5, 0.0, 1.0);
  }
  return occ > 2.2 ? 1.0 : (occ > 0.9 ? 0.5 : 0.0);
}
// 지붕 면 방향: 해를 향하면 +1, 등지면 −1, 아니면 0
float roofFacing(ivec2 p){
  ivec2 dx = ivec2(2, 0), dy = ivec2(0, 2);
  float l = bgDepth(p - dx), r = bgDepth(p + dx), u = bgDepth(p - dy), w = bgDepth(p + dy);
  if (max(max(l, r), max(u, w)) > 1.0e8) return 0.0;
  vec3 a = worldOf(p + dx, r) - worldOf(p - dx, l), b = worldOf(p + dy, w) - worldOf(p - dy, u);
  if (abs(a.z) > 2.5 || abs(b.z) > 2.5) return 0.0;      // 처마·단차 → 판정 안 함
  float rel = dot(normalize(cross(b, a)), uSun) - uSun.z;
  return rel > 0.14 ? 1.0 : (rel < -0.14 ? -1.0 : 0.0);
}
#else
const float NB = 1.0;
#endif
#ifdef LOOK2
vec3 grade(vec3 c, int sem){
  float l = dot(c, vec3(.3,.59,.11));
  // 형광 초록 → 세이지·올리브(색 키, 녹지·수목 클래스는 조금 더)
  float g = clamp((c.g - max(c.r, c.b)) * (sem == 3 || sem == 10 ? 7.0 : 5.0), 0.0, 1.0);
  vec3 s = vec3(l) + (c - l) * 0.66;
  s.r += (s.g - s.r) * 0.22;
  s.b += (s.g - s.b) * 0.10;
  c = mix(c, s, g);
  // 원색 파랑 물 → 차분한 청록
  if (sem == 4) { vec3 w = vec3(l) + (c - l) * 0.6; w.g += (w.b - w.g) * 0.3; c = w * 0.96 + vec3(0.01, 0.03, 0.035); }
  // 마당·광장 베이지 → 따뜻한 회색 쪽
  if (sem == 5 || sem == 11) c = vec3(l) + (c - l) * 0.78;
  l = dot(c, vec3(.3,.59,.11));
  c = vec3(l) + (c - l) * 0.92;
  // 중간톤 약한 S 커브(밝기에만 더해 채도는 그대로). 낮에만 온전히.
  c += (l * l * (3.0 - 2.0 * l) - l) * mix(0.1, 0.28, uDay);
  // 스플릿 톤: 밝은 곳 따뜻하게, 어두운 곳 차갑게
  c += smoothstep(0.45, 0.9, l) * vec3(0.022, 0.008, -0.018) + (1.0 - smoothstep(0.06, 0.3, l)) * vec3(-0.006, 0.0, 0.016);
  // 검정만 짙은 남색·자두색으로(순수 검정 없음). 어두운 벽면까지 뜨지 않게 범위는 좁게, 밤엔 더 적게.
  c += vec3(0.06, 0.048, 0.085) * (1.0 - smoothstep(0.0, 0.22, l)) * mix(0.35, 1.0, uDay);
  c = max(c, vec3(0.022, 0.02, 0.035));
  return c;
}
#endif
void main(){
  ivec2 p = ivec2(gl_FragCoord.xy / uF);
  ivec2 fp = ivec2(gl_FragCoord.xy);
  float d = bgDepth(p);
  if (d > 1.0e8) {
    // 디오라마 옆면: 바로 위쪽에 지오메트리가 있으면 흙 단면을 그린다
    for (int k = 1; k <= 22; k++) {
      ivec2 q = p - ivec2(0, k);
      if (q.y < 0) break;
      if (bgDepth(q) < 1.0e8) {
        float t = float(k) / 22.0;
        vec3 top = texelFetch(uAlbedo, ivec2(vec2(q) * uF), 0).rgb;
        vec3 soil = mix(vec3(0.47,0.36,0.27), vec3(0.23,0.18,0.16), t);
        soil *= 0.92 + 0.16 * hash(vec2(p.x / 2, k / 3));
        vec3 c = k <= 2 ? top * 0.72 : soil;
        vec3 amb = mix(vec3(0.24,0.30,0.52), vec3(1.0), uDay);
        o = vec4(c * amb, 1.0);
#ifdef LOOK2
        o.rgb = grade(o.rgb, 0);
#endif
        return;
      }
    }
    o = vec4(0.0); return;
  }
  vec4 a = texelFetch(uAlbedo, fp, 0);
  vec3 c = a.rgb;
  float z = heightOf(p, d);
  vec3 wp = worldOf(p, d);
  float night = 1.0 - uDay;
  // 구름 그림자(낮)
  float cl = fbm(wp.xy * 0.0042 + vec2(uTime * 0.012, uTime * 0.005));
  c *= 1.0 - 0.13 * uDay * smoothstep(0.50, 0.66, cl);
#ifdef LOOK2
  vec3 amb = mix(vec3(0.12,0.16,0.36), vec3(1.0), uDay);   // 빛 밖은 차가운 남청 어둠
#else
  vec3 amb = mix(vec3(0.20,0.26,0.50), vec3(1.0), uDay);
#endif
  amb += uDusk * vec3(0.30, 0.06, -0.12);
  vec3 lit = c * amb;
#ifdef LOOK2
  int sem2 = int(texelFetch(uSem, p, 0).r * 255.0 + 0.5);
  {
    // 받는 면: 평지(땅·도로·녹지·마당·보행로). 벽·수목·지붕은 깊이가 거칠어 얼룩이 생기므로 제외.
    bool rcv = (sem2 <= 3 || sem2 == 5 || sem2 == 11) && z < 1.5 && wallness(p) < 0.5;   // 깊이로도 땅 높이인 곳만
    float sh = rcv && uSunAmt > 0.01 ? castShadow(p, d) : 0.0;
    float ao = rcv ? contactAO(p, d, z) : 0.0;
    vec3 m = mix(vec3(1.0), uShadeCol, max(sh * uSunAmt, ao * mix(0.55, 0.8, uDay)));
    if ((sem2 == 6 || sem2 == 8) && wallness(p) < 0.5) m *= 1.0 + roofFacing(p) * mix(0.0, 0.05, uSunAmt);
    lit *= m;
    // 비: 젖은 도로·보행로는 어둡고 차갑게, 밤엔 가로등·전조등이 길게 비친다(아래 빛 웅덩이에 더함)
    if (uRain > 0.01 && (sem2 == 2 || sem2 == 11) && z < 1.5) lit *= mix(vec3(1.0), vec3(0.74, 0.79, 0.90), uRain);
  }
#endif
  // 가로등·전조등: 낮은 면(도로, 마당)에만 번진다
  vec3 L = texture(uLight, (vec2(p) + 0.5) / MAPSZ).rgb;
#ifndef LOOK2
  float low = 1.0 - smoothstep(3.0, 7.0, z);
  lit += c * L * night * low * 1.25;
#endif
  // 창문 불빛
  float wall = wallness(p);
  int sem = int(texelFetch(uSem, p, 0).r * 255.0 + 0.5);
  if (night > 0.02) {
    if (sem == 9) {
      // 궁궐 야간 조명: 기둥·벽을 아래에서 비추는 따뜻한 빛
      float l9 = dot(c, vec3(.3,.59,.11));
      lit += (c * 0.4 + vec3(l9) * 0.6 + 0.05) * vec3(1.10, 0.80, 0.48) * night * 0.85 * NB;
    } else if (sem == 7 && z > 1.6) {
      // 그림에 그려진 창(푸르거나 어두운 벽 픽셀)에 불을 켠다. 켜짐 여부는 창 칸(가로 1.5 m × 층) 단위.
      float lum = dot(c, vec3(.3,.59,.11));
      // 유리: 푸른 기가 도는 중간 밝기 픽셀만(검은 외곽선·창틀은 제외해 창살이 남게 한다)
      float glass = step(c.r * 1.12, c.b) * step(0.10, lum) * (1.0 - step(0.62, lum));
      float fl = floor(z / 3.3);
      float col = floor(float(p.x) / 4.0);
      float bld = floor(d / 9.0);
      float r = hash3(vec3(col, fl, bld));
      float flick = hash3(vec3(col, fl, floor(uTime / 7.0 + r * 9.0)));
      float thresh = mix(0.36, 0.10, uLateNight);
      if (glass > 0.5 && r < thresh && flick > 0.04) {
        vec3 e = r < thresh * 0.55 ? vec3(1.0,0.83,0.50) : (r < thresh * 0.85 ? vec3(0.98,0.93,0.78) : vec3(0.72,0.86,1.0));
        lit = mix(lit, e * (0.62 + 0.75 * lum) * NB, 0.88 * night);
      }
    } else if (sem == 4) {
      // 수면에 비친 궁궐 야간 조명. 물가(위쪽 첫 비수면 줄)를 축으로 뒤집은 점이 불 켜진 궁궐 벽이면 그 빛을 줄무늬로 깬다.
      int k = 0;
      for (int i = 1; i <= 48; i++) {
        ivec2 q = p - ivec2(0, i);
        if (q.y < 0) break;
        if (int(texelFetch(uSem, q, 0).r * 255.0 + 0.5) != 4) { k = i; break; }
      }
      if (k > 0 && p.y - 2 * k >= 0) {
        float tq = floor(uTime * 5.0);
        int jx = int(floor(hash3(vec3(float(p.y), tq, 3.0)) * 3.0)) - 1;
        ivec2 r = ivec2(p.x + jx, p.y - 2 * k);
        if (int(texelFetch(uSem, r, 0).r * 255.0 + 0.5) == 9) {
          vec3 rc = texelFetch(uAlbedo, ivec2(vec2(r) * uF), 0).rgb;
          float rl = dot(rc, vec3(.3,.59,.11));
          vec3 glow = (rc * 0.4 + vec3(rl) * 0.6 + 0.05) * vec3(1.10, 0.80, 0.48);
          float rows = step(0.3, hash3(vec3(float(p.y), tq, 9.0)));   // 끊긴 줄 = 물결
          lit += glow * night * 0.55 * rows * (1.0 - float(k) / 48.0) * (1.0 - 0.8 * uSeason.w);
        }
      }
    }
  }
#ifdef LOOK2
  // 색 보정(발광 점은 제외 → 신호·전조등 색 유지), 먼 쪽 옅은 연무, 밤 빛 번짐(1/2 해상도 빛 패스를 계단으로)
  lit = grade(lit, sem);
  lit *= mix(vec3(1.0), vec3(0.9, 0.92, 0.96), uRain * uDay);   // 비 오는 낮: 흐린 하늘
  float far = 1.0 - smoothstep(0.0, 0.5, float(p.y) / MAPSZ.y);
  lit = mix(lit, mix(vec3(0.20, 0.22, 0.32), vec3(0.86, 0.87, 0.88), uDay), mix(0.025, 0.05, uDay) * far);
  if (night > 0.02) {
    // 빛 웅덩이: 알베도 × 빛색 × 세기. 세기만 sqrt 공간 4단계로 약하게 끊는다(색은 그대로).
    vec2 uvL = (vec2(p) + 0.5) / MAPSZ;
    vec3 Ls = (texture(uStatic, uvL).rgb * uLampOn + L) * 4.0;
    float Li = max(Ls.r, max(Ls.g, Ls.b));
    if (Li > 0.002) {
      float qs = floor(sqrt(Li) * 4.0 + 0.5) / 4.0;
      vec3 Lq = mix(Ls, Ls * (qs * qs / Li), 0.45 * smoothstep(0.04, 0.3, Li)) / (1.0 + 0.3 * Li);   // 옅은 가장자리는 안 끊어 테가 안 생기게   // 겹친 광원이 흰색으로 타지 않게 완만히 누른다
      // 텍셀 마스크(절반 해상도 빛이 처마·지붕으로 새지 않게): 지붕 윗면은 거의 못 받고, 벽·나무는 높을수록 옅게
      float mk = 1.0;
      if ((sem == 6 || sem == 8) && wall < 0.5 && z > 2.5) mk = 0.12;
      else if (wall > 0.5) mk = 1.0 - 0.85 * smoothstep(5.0, 16.0, z);
      else if (sem == 10) mk = 1.0 - 0.6 * smoothstep(3.0, 10.0, z);
      if (uRain > 0.01 && (sem == 2 || sem == 11)) mk *= 1.0 + 0.5 * uRain;   // 젖은 도로는 더 번들
      lit += grade(c, sem) * Lq * mk * night * 1.6;
      lit += Lq * vec3(1.0, 0.86, 0.66) * night * 0.012;   // 지면 안개가 받는 옅은 빛 무리
    }
    // 연못: 물가 빛이 물결 따라 흔들리는 세로 줄무늬로 비친다
    if (sem == 4 && uSeason.w < 0.5) {
      float tq = floor(uTime * 4.0);
      int jx = int(floor(hash3(vec3(float(p.y), tq, 5.0)) * 3.0)) - 1;
      vec3 acc = vec3(0.0);
      for (int j = 1; j <= 6; j++) {
        ivec2 q = ivec2(p.x + jx, p.y - j * 4);
        if (int(texelFetch(uSem, q, 0).r * 255.0 + 0.5) == 4) continue;   // 물가(물 밖) 빛만 비친다
        vec2 uq = (vec2(q) + 0.5) / MAPSZ;
        acc = max(acc, (texture(uStatic, uq).rgb * uLampOn + texture(uLight, uq).rgb) * 4.0 * (1.0 - float(j) * 0.12));
      }
      float rows = step(0.35, hash3(vec3(float(p.y), tq, 11.0)));
      lit += floor(acc * 5.0) / 5.0 * rows * vec3(1.0, 0.85, 0.62) * night * 0.6;
    }
  }
#endif
  lit = mix(lit, c, a.a * night);             // 발광 점
  if (uDebug > 0.5) {                          // 가림 판정 클래스 오버레이
    float k = floor(texelFetch(uCls, p, 0).r * 255.0 + 0.5);
    vec3 dc = k < 0.5 ? vec3(0.0) : k < 1.5 ? vec3(0.9,0.2,0.2) : k < 2.5 ? vec3(0.2,0.7,0.3) : k < 3.5 ? vec3(1.0,0.6,0.1) : k < 4.5 ? vec3(0.2,0.8,0.9) : vec3(0.9,0.2,0.9);
    lit = mix(lit, dc, 0.45);
  }
  o = vec4(lit, 1.0);
}`;

const FS_SCREEN = (L2 = false) => `#version 300 es
precision highp float;
${L2 ? '#define LOOK2' : ''}
uniform sampler2D uLit;
uniform vec2 uMapSz, uCanvas, uOrigin;   // uOrigin: 화면 좌상단의 지도 좌표
uniform float uScale, uTime, uSnow, uRain, uDay, uF;
uniform vec2 uTilt;
#ifdef LOOK2
uniform sampler2D uBH, uBQ; uniform float uBloom;   // 블룸 1/2, 1/4
#endif                       // 틸트시프트: x = 세기(0..1), y = 최대 흐림 반경(기기 px)
out vec4 o;
float hash(vec2 p){ vec3 q = fract(vec3(p.xyx) * .1031); q += dot(q, q.yzx + 33.33); return fract((q.x + q.y) * q.z); }
void main(){
  vec2 s = vec2(gl_FragCoord.x, uCanvas.y - gl_FragCoord.y);
  vec2 m = uOrigin + s / uScale;
  vec2 uv;
  float ts = uScale / uF;                 // 기기 px / 합성 텍셀
  if (ts >= 1.0) {
    vec2 t = m * uF - 0.5; vec2 i = floor(t); vec2 f = t - i;
    f = clamp((f - 0.5) * ts + 0.5, 0.0, 1.0);
    uv = (i + 0.5 + f) / (uMapSz * uF);
  } else uv = m / uMapSz;
  vec4 c = texture(uLit, uv);
#ifdef LOOK2
  if (uBloom > 0.0) c.rgb += (texture(uBH, m / uMapSz).rgb * 0.45 + texture(uBQ, m / uMapSz).rgb * 0.7) * uBloom;
#endif
  if (uTilt.x > 0.0) {
    // 틸트시프트(미니어처 사진 느낌): 가운데 띠는 선명, 위·아래 가장자리로 갈수록 흐리게. 셰이더에서만 → UI 는 안 흐려진다.
    // 탭 반경(지도 px)은 render() 의 scissor 여유(24 px)보다 작게 유지된다(최대 반경 / 최소 배율).
    float yn = abs(gl_FragCoord.y / uCanvas.y - 0.5);
    // 세로 화면은 선명한 띠를 넓힌다(같은 비율이면 화면의 2/3 가 흐려진다)
    float tall = clamp(uCanvas.y / uCanvas.x - 1.0, 0.0, 1.0);
    float rad = uTilt.y * uTilt.x * (1.0 - 0.3 * tall) * smoothstep(0.12 + 0.16 * tall, 0.5, yn);
    if (rad > 0.5) {
      // 분기 안에서는 미분이 정의되지 않으니 mip 단계를 직접 정한다(축소 화면에서만 mip 이 있다)
      float lod = ts < 1.0 ? -log2(ts) : 0.0;
      vec4 acc = c;
      for (int i = 0; i < 12; i++) {
        float fi = float(i);
        float rr = sqrt((fi + 0.5) / 12.0) * rad / uScale;
        vec2 dv = vec2(cos(fi * 2.39996), sin(fi * 2.39996)) * rr;
        acc += textureLod(uLit, (m + dv) / uMapSz, lod);
      }
      c = acc / 13.0;
    }
    float l = dot(c.rgb, vec3(.3,.59,.11));
    c.rgb = mix(vec3(l), c.rgb, 1.0 + 0.10 * uTilt.x);   // 채도 살짝
  }
  vec2 e = min(m, uMapSz - m);
  float fade = smoothstep(0.0, 48.0, min(e.x, e.y));
  c *= fade;
  // 눈·비: 지도 좌표 격자에 고정한 입자(확대하면 입자도 커지는 픽셀 눈)
  float cov = 0.0;
  if (uSnow > 0.01) {
    for (int L = 0; L < 3; L++) {
      float cell = 22.0 + float(L) * 15.0;
      float sp = 9.0 + float(L) * 5.0;
      vec2 q = vec2(m.x + sin(uTime * 0.6 + float(L) * 2.1 + m.y * 0.02) * 5.0, m.y - uTime * sp) / cell;
      vec2 id = floor(q); vec2 f = fract(q);
      vec2 c0 = vec2(hash(id + float(L) * 17.0), hash(id.yx + 3.7 + float(L)));
      vec2 dd = (f - c0) * cell;
      float sz = 0.7 + float(L) * 0.35;
      cov = max(cov, step(max(abs(dd.x), abs(dd.y)), sz) * step(hash(id + 51.0), uSnow));
    }
    c = mix(c, vec4(0.97, 0.98, 1.0, 1.0), cov * 0.92 * fade);
  }
  if (uRain > 0.01) {
    vec2 q = vec2(m.x + m.y * 0.25, m.y - uTime * 95.0) / vec2(11.0, 46.0);
    vec2 id = floor(q); vec2 f = fract(q);
    float r = step(abs(f.x - hash(id)), 0.045) * step(f.y, 0.34) * step(hash(id + 9.0), uRain);
    c = mix(c, vec4(0.72, 0.80, 0.92, 1.0), r * 0.42 * fade);
  }
  o = c;
}`;

function compile(gl, vs, fs) {
  const mk = (type, src) => {
    const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) + '\n' + src.split('\n').map((l, i) => `${i + 1}: ${l}`).join('\n'));
    return s;
  };
  const p = gl.createProgram();
  gl.attachShader(p, mk(gl.VERTEX_SHADER, vs)); gl.attachShader(p, mk(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
  const u = {};
  const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
  for (let i = 0; i < n; i++) { const info = gl.getActiveUniform(p, i); u[info.name] = gl.getUniformLocation(p, info.name); }
  return { p, u };
}

export function createRenderer(canvas, assets, proj, opts = {}) {
  const gl = canvas.getContext('webgl2', { alpha: true, premultipliedAlpha: true, antialias: false, depth: false, stencil: false, powerPreference: 'high-performance' });
  if (!gl) throw new Error('WebGL2 를 쓸 수 없습니다');
  const { W, H } = proj;

  const bgScale = Math.round(assets.bg.width / W);
  const tex = (img, { filter = gl.NEAREST, internal = gl.RGBA8, format = gl.RGBA, mip = false } = {}) => {
    const t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    gl.texImage2D(gl.TEXTURE_2D, 0, internal, format, gl.UNSIGNED_BYTE, img);
    if (mip) gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, mip ? gl.NEAREST_MIPMAP_NEAREST : filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return t;
  };
  const T = {
    bg: tex(assets.bg, { mip: bgScale === 2 }), depth: tex(assets.depth), cls: tex(assets.cls), sem: tex(assets.sem),
    veh: tex(assets.veh), vehDepth: tex(assets.vehDepth), vehShadow: tex(assets.vehShadow), people: tex(assets.people),
  };
  const target = (w, h, filter, mip) => {
    const t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texStorage2D(gl.TEXTURE_2D, mip ? Math.floor(Math.log2(Math.max(w, h))) + 1 : 1, gl.RGBA8, w, h);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, mip ? gl.LINEAR_MIPMAP_LINEAR : filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    const f = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, f);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t, 0);
    return { t, f, w, h };
  };
  // 합성 타깃 두 벌: 1배(축소 화면용, mip 포함)와 2배(확대 화면용, 배경이 0.25 m/px 일 때만)
  const hiOk = bgScale === 2 && gl.getParameter(gl.MAX_TEXTURE_SIZE) >= W * 2 && !assets.lowMem;
  const SETS = { 1: { FA: target(W, H, gl.NEAREST, false), FB: target(W, H, gl.LINEAR, true) } };
  if (hiOk) SETS[2] = { FA: target(W * 2, H * 2, gl.NEAREST, false), FB: target(W * 2, H * 2, gl.LINEAR, false) };
  const FL = target(W >> 1, H >> 1, gl.LINEAR, false);

  const pAlbedo = compile(gl, VS_FULL, FS_ALBEDO(proj));
  // 룩별 스프라이트·조명 프로그램은 쓸 때 컴파일한다(첫 화면은 opts.look 하나만).
  // 룩 2(LOOK2 변형)가 실패하면 경고만 남기고 예전 룩으로 그린다. 예전 룩까지 실패하면 예외 → 정지 그림.
  let look1 = null, look2 = null;
  const progs = (look) => {
    if (look === 2 && look2 !== false) {
      if (!look2) {
        try {
          look2 = { sprite: compile(gl, VS_SPRITE(proj, true), FS_SPRITE(proj, true)), lit: compile(gl, VS_FULL, FS_LIT(proj, true)),
            light: compile(gl, VS_LIGHT(proj), FS_LIGHT(true)), screen: compile(gl, VS_FULL, FS_SCREEN(true)),
            bake: compile(gl, VS_BAKE(proj), FS_BAKE(proj)), bright: compile(gl, VS_FULL, FS_BRIGHT), blur: compile(gl, VS_FULL, FS_BLUR) };
        }
        catch (e) { console.warn('룩 2 셰이더 실패, 예전 룩으로 그립니다:', e); look2 = false; }
      }
      if (look2) return look2;
    }
    return look1 ||= { sprite: compile(gl, VS_SPRITE(proj), FS_SPRITE(proj)), lit: compile(gl, VS_FULL, FS_LIT(proj)),
      light: compile(gl, VS_LIGHT(proj), FS_LIGHT()), screen: compile(gl, VS_FULL, FS_SCREEN()) };
  };
  progs(opts.look === 1 ? 1 : 2);
  // 룩 2 전용 타깃(처음 쓸 때 만든다): 정적 빛 1/2, 블룸 1/2·1/4. 모두 지도 해상도 이하라 휴대폰 경로에도 풀해상도 타깃은 없다.
  let FS = null, FH = null, FQ = null, staticData = null, nStatic = 0, baked = false;

  const quad = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, quad);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), gl.STATIC_DRAW);

  const MAX_SPR = 8192, MAX_LGT = 4096;
  const sprData = new Float32Array(MAX_SPR * SPR_STRIDE);
  const shdData = new Float32Array(MAX_SPR * SPR_STRIDE);
  const lgtData = new Float32Array(MAX_LGT * LGT_STRIDE);
  const mkInst = (data, stride, layout) => {
    const vao = gl.createVertexArray(); gl.bindVertexArray(vao);
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, data.byteLength, gl.DYNAMIC_DRAW);
    let off = 0;
    layout.forEach((n, i) => {
      gl.enableVertexAttribArray(i + 1); gl.vertexAttribPointer(i + 1, n, gl.FLOAT, false, stride * 4, off * 4);
      gl.vertexAttribDivisor(i + 1, 1); off += n;
    });
    gl.bindVertexArray(null);
    return { vao, buf };
  };
  const sprI = mkInst(sprData, SPR_STRIDE, [4, 4, 1]);
  const shdI = mkInst(shdData, SPR_STRIDE, [4, 4, 1]);
  const lgtI = mkInst(lgtData, LGT_STRIDE, [3, 3]);
  let bakeI = null;
  const emptyVao = gl.createVertexArray();

  let nSpr = 0, nShd = 0, nLgt = 0;
  const order = new Uint32Array(MAX_SPR);
  const tmp = new Float32Array(MAX_SPR * SPR_STRIDE);

  const bind = (unit, t) => { gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, t); };

  return {
    gl, W, H,
    begin() { nSpr = 0; nShd = 0; nLgt = 0; },
    sprite(dx, dy, w, h, sx, sy, depth, kind, param = 0) {
      if (nSpr >= MAX_SPR) return;
      const o = nSpr++ * SPR_STRIDE;
      sprData[o] = dx; sprData[o + 1] = dy; sprData[o + 2] = w; sprData[o + 3] = h; sprData[o + 4] = sx; sprData[o + 5] = sy;
      sprData[o + 6] = depth; sprData[o + 7] = kind; sprData[o + 8] = param;
    },
    shadow(dx, dy, w, h, sx, sy, depth, kind) {
      if (nShd >= MAX_SPR) return;
      const o = nShd++ * SPR_STRIDE;
      shdData[o] = dx; shdData[o + 1] = dy; shdData[o + 2] = w; shdData[o + 3] = h; shdData[o + 4] = sx; shdData[o + 5] = sy;
      shdData[o + 6] = depth; shdData[o + 7] = kind; shdData[o + 8] = 0;
    },
    light(x, y, radius, r, g, b) {
      if (nLgt >= MAX_LGT) return;
      const o = nLgt++ * LGT_STRIDE;
      lgtData[o] = x; lgtData[o + 1] = y; lgtData[o + 2] = radius; lgtData[o + 3] = r; lgtData[o + 4] = g; lgtData[o + 5] = b;
    },
    counts() { return { sprites: nSpr, shadows: nShd, lights: nLgt, staticLights: nStatic }; },
    // 룩 2 정적 광원: Float32Array [x, y, 반경, r, g, b, 높이(m)] × n. 다음 밤 프레임에 한 번 굽는다.
    setStaticLights(data) { staticData = data; nStatic = data.length / 7; baked = false; },
    // 합성 배율: 확대 화면이고 0.25 m/px 배경이 올라가 있으면 2배
    pickF(scale) { return SETS[2] && scale > 1.05 ? 2 : 1; },

    // view: {originX, originY, scale}  (scale = 기기 px / 지도 px), env: 조명·계절 상태
    render(view, env) {
      const cw = canvas.width, ch = canvas.height;
      // 화면에 보이는 지도 영역만 합성(scissor). 축소 시 mip 경계 번짐을 막으려 여유를 둔다.
      const pad = 24;
      const x0 = Math.max(0, Math.floor(view.originX) - pad), y0 = Math.max(0, Math.floor(view.originY) - pad);
      const x1 = Math.min(W, Math.ceil(view.originX + cw / view.scale) + pad), y1 = Math.min(H, Math.ceil(view.originY + ch / view.scale) + pad);
      const vis = x1 > x0 && y1 > y0;
      const F = this.pickF(view.scale);
      const { FA, FB } = SETS[F];
      this.F = F;
      const set = progs(env.look);
      const { sprite: pSprite, lit: pLit, light: pLight, screen: pScreen } = set;
      const L2 = set === look2;
      const nightOn = env.day < 0.98;
      if (L2 && !FS) {
        FS = target(W >> 1, H >> 1, gl.LINEAR, false); FH = target(W >> 1, H >> 1, gl.LINEAR, false); FQ = target(W >> 2, H >> 2, gl.LINEAR, false);
      }
      if (L2 && nightOn && !baked) {
        // 정적 빛 굽기(전체 지도, 한 번)
        baked = true;
        gl.bindFramebuffer(gl.FRAMEBUFFER, FS.f); gl.viewport(0, 0, FS.w, FS.h);
        gl.disable(gl.SCISSOR_TEST); gl.clearColor(0, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT);
        if (nStatic) {
          if (!bakeI) bakeI = mkInst(staticData, 7, [3, 3, 1]);
          gl.bindVertexArray(bakeI.vao); gl.bindBuffer(gl.ARRAY_BUFFER, bakeI.buf); gl.bufferData(gl.ARRAY_BUFFER, staticData, gl.STATIC_DRAW);
          gl.useProgram(set.bake.p);
          bind(0, T.depth); gl.uniform1i(set.bake.u.uDepth, 0); gl.uniform1f(set.bake.u.uF, 1);
          gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);
          gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, nStatic);
          gl.disable(gl.BLEND);
        }
      }

      // 깊이 정렬(먼 것부터). 사람·차량·발광 점이 한 버퍼에 섞여 있다.
      for (let i = 0; i < nSpr; i++) order[i] = i;
      const ord = order.subarray(0, nSpr);
      ord.sort((a, b) => sprData[b * SPR_STRIDE + 6] - sprData[a * SPR_STRIDE + 6]);
      for (let i = 0; i < nSpr; i++) {
        const s = ord[i] * SPR_STRIDE, d = i * SPR_STRIDE;
        for (let k = 0; k < SPR_STRIDE; k++) tmp[d + k] = sprData[s + k];
      }

      gl.disable(gl.DEPTH_TEST);
      if (vis) {
        gl.enable(gl.SCISSOR_TEST);
        // ── A: albedo
        gl.bindFramebuffer(gl.FRAMEBUFFER, FA.f);
        gl.viewport(0, 0, W * F, H * F); gl.scissor(x0 * F, y0 * F, (x1 - x0) * F, (y1 - y0) * F);
        gl.disable(gl.BLEND);
        gl.useProgram(pAlbedo.p);
        gl.uniform1f(pAlbedo.u.uF, F); gl.uniform1f(pAlbedo.u.uBgScale, bgScale);
        bind(0, T.depth); gl.uniform1i(pAlbedo.u.uDepth, 0);
        bind(1, T.bg); gl.uniform1i(pAlbedo.u.uBg, 1);
        bind(2, T.sem); gl.uniform1i(pAlbedo.u.uSem, 2);
        gl.uniform4fv(pAlbedo.u.uSeason, env.season);
        gl.uniform1f(pAlbedo.u.uTime, env.time);
        gl.uniform1f(pAlbedo.u.uDay, env.day); gl.uniform1f(pAlbedo.u.uRain, env.rain);
        gl.bindVertexArray(emptyVao); gl.drawArrays(gl.TRIANGLES, 0, 3);

        gl.useProgram(pSprite.p);
        gl.uniform1f(pSprite.u.uF, F);
        bind(0, T.depth); gl.uniform1i(pSprite.u.uDepth, 0);
        bind(1, T.veh); gl.uniform1i(pSprite.u.uVeh, 1);
        bind(2, T.vehDepth); gl.uniform1i(pSprite.u.uVehDepth, 2);
        bind(3, T.vehShadow); gl.uniform1i(pSprite.u.uVehShadow, 3);
        bind(4, T.people); gl.uniform1i(pSprite.u.uPeople, 4);
        gl.uniform3fv(pSprite.u.uShadowTint, env.shadowTint);
        gl.uniform1f(pSprite.u.uShadowAmt, env.shadowAmt);
        if (nShd) {
          gl.enable(gl.BLEND); gl.blendFuncSeparate(gl.DST_COLOR, gl.ZERO, gl.ZERO, gl.ONE);
          gl.bindVertexArray(shdI.vao); gl.bindBuffer(gl.ARRAY_BUFFER, shdI.buf);
          gl.bufferSubData(gl.ARRAY_BUFFER, 0, shdData, 0, nShd * SPR_STRIDE);
          gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, nShd);
          gl.disable(gl.BLEND);
        }
        if (nSpr) {
          gl.bindVertexArray(sprI.vao); gl.bindBuffer(gl.ARRAY_BUFFER, sprI.buf);
          gl.bufferSubData(gl.ARRAY_BUFFER, 0, tmp, 0, nSpr * SPR_STRIDE);
          gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, nSpr);
        }

        // ── L: 빛 웅덩이
        gl.bindFramebuffer(gl.FRAMEBUFFER, FL.f);
        gl.viewport(0, 0, FL.w, FL.h); gl.scissor(x0 >> 1, y0 >> 1, ((x1 - x0) >> 1) + 1, ((y1 - y0) >> 1) + 1);
        gl.clearColor(0, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT);
        if (nLgt && env.day < 0.98) {
          gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);
          gl.useProgram(pLight.p);
          gl.bindVertexArray(lgtI.vao); gl.bindBuffer(gl.ARRAY_BUFFER, lgtI.buf);
          gl.bufferSubData(gl.ARRAY_BUFFER, 0, lgtData, 0, nLgt * LGT_STRIDE);
          gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, nLgt);
          gl.disable(gl.BLEND);
        }

        // ── B: 조명
        gl.bindFramebuffer(gl.FRAMEBUFFER, FB.f);
        gl.viewport(0, 0, W * F, H * F); gl.scissor(x0 * F, y0 * F, (x1 - x0) * F, (y1 - y0) * F);
        gl.useProgram(pLit.p);
        gl.uniform1f(pLit.u.uF, F);
        bind(0, T.depth); gl.uniform1i(pLit.u.uDepth, 0);
        bind(1, FA.t); gl.uniform1i(pLit.u.uAlbedo, 1);
        bind(2, FL.t); gl.uniform1i(pLit.u.uLight, 2);
        bind(3, T.sem); gl.uniform1i(pLit.u.uSem, 3);
        bind(4, T.cls); gl.uniform1i(pLit.u.uCls, 4);
        gl.uniform1f(pLit.u.uDay, env.day); gl.uniform1f(pLit.u.uDusk, env.dusk);
        gl.uniform1f(pLit.u.uLateNight, env.lateNight); gl.uniform1f(pLit.u.uTime, env.time);
        gl.uniform1f(pLit.u.uDebug, env.debug ? 1 : 0);
        gl.uniform4fv(pLit.u.uSeason, env.season);
        gl.uniform4fv(pLit.u.uPalace, env.palace);
        if (L2) {
          bind(5, FS.t); gl.uniform1i(pLit.u.uStatic, 5); gl.uniform1f(pLit.u.uLampOn, smoothstep(0.2, 0.8, 1 - env.day));   // 황혼에 서서히 켜진다
          gl.uniform3fv(pLit.u.uSun, env.sun); gl.uniform3fv(pLit.u.uShadeCol, env.shadeCol);
          gl.uniform1f(pLit.u.uSunAmt, env.sunAmt); gl.uniform1f(pLit.u.uRayLen, env.rayLen); gl.uniform1f(pLit.u.uRain, env.rain);
        }
        gl.bindVertexArray(emptyVao); gl.drawArrays(gl.TRIANGLES, 0, 3);
        if (L2 && nightOn) {
          // ── 블룸: 밝은 부분 1/2 → 1/4
          gl.bindFramebuffer(gl.FRAMEBUFFER, FH.f); gl.viewport(0, 0, FH.w, FH.h);
          gl.scissor(x0 >> 1, y0 >> 1, ((x1 - x0) >> 1) + 2, ((y1 - y0) >> 1) + 2);
          gl.useProgram(set.bright.p);
          bind(0, FB.t); gl.uniform1i(set.bright.u.uSrc, 0); gl.uniform1f(set.bright.u.uF, F); gl.uniform1f(set.bright.u.uThr, 0.86);
          gl.drawArrays(gl.TRIANGLES, 0, 3);
          gl.bindFramebuffer(gl.FRAMEBUFFER, FQ.f); gl.viewport(0, 0, FQ.w, FQ.h);
          gl.scissor(x0 >> 2, y0 >> 2, ((x1 - x0) >> 2) + 2, ((y1 - y0) >> 2) + 2);
          gl.useProgram(set.blur.p);
          bind(0, FH.t); gl.uniform1i(set.blur.u.uSrc, 0); gl.uniform2f(set.blur.u.uTexel, 1 / FH.w, 1 / FH.h);
          gl.drawArrays(gl.TRIANGLES, 0, 3);
        }
        gl.disable(gl.SCISSOR_TEST);
        if (F === 1 && view.scale < 1) { gl.bindFramebuffer(gl.FRAMEBUFFER, null); bind(0, FB.t); gl.generateMipmap(gl.TEXTURE_2D); }
      }

      // ── 화면
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      gl.viewport(0, 0, cw, ch);
      gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
      gl.useProgram(pScreen.p);
      bind(0, FB.t); gl.uniform1i(pScreen.u.uLit, 0);
      gl.uniform2f(pScreen.u.uMapSz, W, H); gl.uniform2f(pScreen.u.uCanvas, cw, ch);
      gl.uniform2f(pScreen.u.uOrigin, view.originX, view.originY);
      gl.uniform1f(pScreen.u.uScale, view.scale); gl.uniform1f(pScreen.u.uF, F); gl.uniform1f(pScreen.u.uTime, env.time);
      gl.uniform1f(pScreen.u.uSnow, env.snow); gl.uniform1f(pScreen.u.uRain, env.rain); gl.uniform1f(pScreen.u.uDay, env.day);
      gl.uniform2f(pScreen.u.uTilt, env.tilt || 0, env.tiltR || 0);
      if (L2) {
        bind(1, FH.t); gl.uniform1i(pScreen.u.uBH, 1); bind(2, FQ.t); gl.uniform1i(pScreen.u.uBQ, 2);
        gl.uniform1f(pScreen.u.uBloom, nightOn ? (1 - env.day) : 0);
      }
      gl.bindVertexArray(emptyVao); gl.drawArrays(gl.TRIANGLES, 0, 3);
    },
  };
}
