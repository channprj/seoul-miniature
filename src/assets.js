// 자산 로더. 개발 서버에서는 /assets/web-poc/ 에서 fetch, 오프라인 단일 HTML 에서는
// window.__ISO_ASSETS__ (이름 → base64) 에서 읽는다. 이미지는 색공간 변환·premultiply 없이 디코드한다.
// 구형 WebKit(트위터 인앱 브라우저의 오래된 iOS) 대비: 비압축 장면 우선 → gz(DecompressionStream → JS gunzip),
// createImageBitmap 옵션을 못 받으면 옵션 없이 → 그것도 없으면 <img>.
import { gunzip } from './gunzip.js';

const BASE = 'assets/';   // 상대 경로: github.io 의 하위 경로에서도 동작
const emb = () => globalThis.__ISO_ASSETS__;

// optional = 없으면(404·내장 목록에 없음) null. onBytes(받은 바이트, 전체 바이트|0)
async function bytes(name, { optional = false, onBytes } = {}) {
  const e = emb();
  if (e) {
    if (!e[name]) { if (optional) return null; throw new Error(`내장 자산 없음: ${name}`); }
    const bin = atob(e[name]);
    const u8 = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
    return u8;
  }
  const r = await fetch(BASE + name);
  if (!r.ok) { if (optional && r.status === 404) return null; throw new Error(`자산을 못 읽음: ${name} (${r.status})`); }
  const total = Number(r.headers.get('content-length')) || 0;
  if (!onBytes || !r.body || !r.body.getReader) return new Uint8Array(await r.arrayBuffer());
  // 진행률: 조각 단위로 읽어 센다(content-length 가 없으면 끝날 때 한 번에 채운다)
  const reader = r.body.getReader(), parts = [];
  let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parts.push(value); got += value.length; onBytes(got, total);
  }
  const u8 = new Uint8Array(got);
  let o = 0;
  for (const p of parts) { u8.set(p, o); o += p.length; }
  return u8;
}

async function image(name, onBytes) {
  const blob = new Blob([await bytes(name, { onBytes })], { type: 'image/png' });
  if (typeof createImageBitmap === 'function') {
    try { return await createImageBitmap(blob, { premultiplyAlpha: 'none', colorSpaceConversion: 'none' }); } catch { /* 옵션 미지원 */ }
    try { return await createImageBitmap(blob); } catch { /* Blob 미지원(구형 사파리) */ }
  }
  const url = URL.createObjectURL(blob);
  try {
    const img = new Image();
    img.src = url;
    if (img.decode) await img.decode(); else await new Promise((ok, no) => { img.onload = ok; img.onerror = no; });
    return img;
  } finally { setTimeout(() => URL.revokeObjectURL(url), 0); }
}

const utf8 = (u8) => new TextDecoder().decode(u8);
// 장면: 공개 배포본에는 비압축 scene.json 이 같이 들어간다. 개발 폴더·오프라인 HTML 에는 gz 만 있다.
async function sceneJson(onBytes) {
  try {
    const raw = await bytes('web-poc/scene.json', { optional: true, onBytes });
    if (raw) return JSON.parse(utf8(raw));
  } catch { /* file:// 등에서 fetch 자체가 실패 → gz 로 */ }
  const gz = await bytes('web-poc/scene.json.gz', { onBytes });
  if (typeof DecompressionStream === 'function') {
    try {
      const ds = new Blob([gz]).stream().pipeThrough(new DecompressionStream('gzip'));
      return JSON.parse(await new Response(ds).text());
    } catch { /* 아래 JS gunzip */ }
  }
  return JSON.parse(utf8(gunzip(gz)));
}

// WebGL2 확인용 임시 컨텍스트. 확인 뒤 바로 버린다(iOS 는 동시 컨텍스트 수가 적다).
export function probeWebGL2() {
  try {
    const gl = document.createElement('canvas').getContext('webgl2');
    if (!gl) return null;
    const info = { maxTex: gl.getParameter(gl.MAX_TEXTURE_SIZE) };
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    return info;
  } catch { return null; }
}

// 휴대폰(굵은 포인터 + 짧은 변 820 CSS px 이하)은 기본으로 절반 해상도 그림 → 렌더러도 1배 FBO 만 만든다.
// 5504×3392 그림과 2배 FBO 여러 장은 WKWebView(인앱 브라우저)가 탭을 죽이기 쉽다. UA 대신 기능으로 판정.
//   ?res=2 강제 고해상도(텍스처 한도는 그래도 지킨다), ?res=1 강제 절반
export function isPhone() {
  try {
    const coarse = matchMedia('(pointer: coarse)').matches;
    const short = Math.min(screen.width || innerWidth, screen.height || innerHeight);
    return coarse && short <= 820;
  } catch { return false; }
}
export function pickResolution(gl = probeWebGL2()) {
  const q = new URLSearchParams(location.search).get('res');
  if (q === '1' || !gl || gl.maxTex < 8192) return 1;
  if (q === '2') return 2;
  if (isPhone()) return 1;
  if (navigator.deviceMemory && navigator.deviceMemory < 4) return 1;
  return 2;
}

export async function loadAssets(onProgress = () => {}, { res = pickResolution() } = {}) {
  const names = {
    bg: res === 2 ? 'redraw/bg.png' : 'redraw/bg_1x.png',   // 5504×3392(0.25 m/px) 또는 휴대폰·저사양용 2752×1696
    depth: 'redraw/depth_rg8.png',       // 2752×1696, 외곽 OSM 건물까지 포함한 깊이
    cls: 'web-poc/occlusion_class8.png',
    sem: 'redraw/classes.png',
  };
  // 진행률: 항목별 대략 무게(바이트)로 가중. content-length 가 있으면 바이트 단위로 움직인다.
  const W = { scene: 0.3, bg: res === 2 ? 5.5 : 1.6, depth: 1.7, cls: 0.25, sem: 0.4 };
  const frac = {};
  const report = () => {
    let s = 0, t = 0;
    for (const k in W) { s += W[k] * (frac[k] || 0); t += W[k]; }
    onProgress(s / t);
  };
  const onBytes = (k) => (got, total) => { if (total) { frac[k] = Math.min(0.98, got / total); report(); } };
  const done = (k) => { frac[k] = 1; report(); };
  const out = { res };
  await Promise.all([
    sceneJson(onBytes('scene')).then((s) => { out.scene = s; done('scene'); }),
    ...Object.keys(names).map((k) => image(names[k], onBytes(k)).then((im) => { out[k] = im; done(k); })),
  ]);
  return out;
}

// WebGL2 가 없을 때 보여 줄 정지 그림 주소(오프라인 HTML 이면 내장 base64)
export function stillUrl() {
  const e = emb(), n = 'redraw/bg_1x.png';
  if (e && e[n]) return 'data:image/png;base64,' + e[n];
  return BASE + n;
}
