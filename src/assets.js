// 자산 로더. 개발 서버에서는 /assets/web-poc/ 에서 fetch, 오프라인 단일 HTML 에서는
// window.__ISO_ASSETS__ (이름 → base64) 에서 읽는다. 이미지는 색공간 변환·premultiply 없이 디코드한다.
// 구형 WebKit(트위터 인앱 브라우저의 오래된 iOS) 대비: 비압축 장면 우선 → gz(DecompressionStream → JS gunzip),
// createImageBitmap 옵션을 못 받으면 옵션 없이 → 그것도 없으면 <img>.
import { gunzip } from './gunzip.js';
import { decodePng } from './png.js';
import { currentMap } from './maps.js';
import { sceneFromMap } from './mapscene.js';

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

async function image(name, onBytes, optional = false) {
  const u8 = await bytes(name, { onBytes, optional });
  if (!u8) return null;
  const blob = new Blob([u8], { type: 'image/png' });
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

// 수치 맵(깊이·클래스): 브라우저 디코더를 거치지 않고 바이트를 직접 푼다(png.js 머리말: 사파리가 회색조 값을 바꾼다).
// → ImageData(없으면 같은 모양의 객체). 못 풀면 예전처럼 브라우저 디코더로.
async function dataMap(name, onBytes, optional = false) {
  const u8 = await bytes(name, { onBytes, optional });
  if (!u8) return null;
  try {
    const m = await decodePng(u8);
    return typeof ImageData === 'function' ? new ImageData(m.data, m.width, m.height) : m;
  } catch (e) { console.warn(`${name}: 직접 디코드 실패, 브라우저 디코더로 읽습니다`, e); }
  return image(name, undefined, optional);
}

// 있으면 그림, 없으면(404·오프라인 HTML 에 안 들어 있음) null. 네트워크 오류는 예외.
export const optionalImage = (name) => image(name, undefined, true);

const utf8 = (u8) => new TextDecoder().decode(u8);
// 장면: 공개 배포본에는 비압축 scene.json 이 같이 들어간다. 개발 폴더·오프라인 HTML 에는 gz 만 있다.
// 지도 설정에 map(지도 고유 값 파일, 예: yeouido/map.json)이 있으면 그것을 장면 모양으로 바꾼다(mapscene.js).
async function sceneJson(onBytes, map) {
  if (map.map) return sceneFromMap(JSON.parse(utf8(await bytes(`${map.dir}/${map.map}`, { onBytes }))));
  try {
    const raw = await bytes(map.scene, { optional: true, onBytes });
    if (raw) return JSON.parse(utf8(raw));
  } catch { /* file:// 등에서 fetch 자체가 실패 → gz 로 */ }
  const gz = await bytes(map.scene + '.gz', { onBytes });
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

// 배경 타일 피라미드(tools/redraw/make_tiles.py): redraw/tiles/manifest.json 이 있으면 바탕은 z1.png(0.5 m) 하나만 받고,
// 확대하면 보이는 칸의 z2·z4·z8 타일을 받는다(데스크톱·휴대폰 같은 경로). 없으면 예전처럼 bg.png / bg_1x.png 통짜.
//   ?tiles=0 끔, ?maxlod=1|2|4|8 가장 세밀한 단계 상한
// 안전판(메모리가 빠듯한 휴대폰): 깊은 단계(z4·z8)를 그리던 중에 탭이 죽었거나(pagehide 없이 다시 열림) WebGL 컨텍스트를 잃었으면,
// 이 탭에서는 다음부터 그보다 한 단계 얕게만 쓴다(sessionStorage). ?maxlod 를 주면 그 값이 우선.
const ss = (k, v) => { try { if (v === undefined) return sessionStorage.getItem(k); if (v === null) sessionStorage.removeItem(k); else sessionStorage.setItem(k, String(v)); } catch { /* 사생활 보호 모드 */ } return null; };
export function lodLive(F) { ss('iso-lod-live', F >= 4 ? F : null); }
export function lodFailed(F) { if (F >= 4) ss('iso-lod-cap', F / 2); ss('iso-lod-live', null); }
function lodCap() {
  const live = Number(ss('iso-lod-live')) || 0;
  let cap = Number(ss('iso-lod-cap')) || 8;
  if (live >= 4) { cap = Math.min(cap, live / 2); ss('iso-lod-cap', cap); }
  ss('iso-lod-live', null);
  return cap;
}
async function tileManifest(dir) {
  const q = new URLSearchParams(location.search);
  if (q.get('tiles') === '0') return null;
  try {
    const raw = await bytes(dir + '/tiles/manifest.json', { optional: true });
    if (!raw) return null;
    const m = JSON.parse(utf8(raw));
    const cap = Number(q.get('maxlod')) || lodCap();
    m.dir = dir + '/tiles/';   // 타일 파일 폴더(bgtiles.js)
    m.zs = Object.keys(m.levels).map(Number).filter((z) => z <= cap).sort((a, b) => a - b);
    return m;
  } catch { return null; }
}

export async function loadAssets(onProgress = () => {}, { res = pickResolution(), map = currentMap() } = {}) {
  // 정식 폴더에 지도 값 파일이 없고 개발용 임시 폴더가 있으면 그쪽으로(개발 서버 전용)
  if (map.map && map.devDir && !emb()) {
    const probe = await bytes(`${map.dir}/${map.map}`, { optional: true }).catch(() => null);
    if (!probe) { console.warn(`${map.dir}/${map.map} 이 없어 임시 세트 ${map.devDir} 를 씁니다`); map = { ...map, dir: map.devDir }; }
  }
  const D = map.dir;
  const man = await tileManifest(D);
  const names = {
    bg: res === 2 ? `${D}/bg.png` : `${D}/bg_1x.png`,   // 5504×3392(지도 px 의 2배) 또는 휴대폰·저사양용 2752×1696
    depth: `${D}/depth_rg8.png`,         // 2752×1696 깊이(디코드 상수는 장면 데이터의 occlusion)
    sem: `${D}/classes.png`,
  };
  if (map.cls) names.cls = map.cls;      // 가림 판정 클래스(검증 오버레이). 없는 지도는 렌더러가 의미 클래스로 대신한다
  if (man) names.bg = D + '/tiles/' + man.base;
  // 진행률: 항목별 대략 무게(바이트)로 가중. content-length 가 있으면 바이트 단위로 움직인다.
  const W = { scene: 0.3, bg: res === 2 && !man ? 5.5 : 1.6, depth: 1.7, cls: 0.25, sem: 0.4 };
  if (!names.cls) delete W.cls;
  const frac = {};
  const report = () => {
    let s = 0, t = 0;
    for (const k in W) { s += W[k] * (frac[k] || 0); t += W[k]; }
    onProgress(s / t);
  };
  const onBytes = (k) => (got, total) => { if (total) { frac[k] = Math.min(0.98, got / total); report(); } };
  const done = (k) => { frac[k] = 1; report(); };
  // tiles: 타일 피라미드 manifest(없으면 null). phone: 아틀라스·합성 창 크기 상한을 휴대폰 기준으로
  const out = { res, tiles: man, phone: isPhone(), map, cls: null };
  await Promise.all([
    sceneJson(onBytes('scene'), map).then((s) => { out.scene = s; done('scene'); }),
    // 수관 마스크(선택): 다시 그린 그림의 실제 나무 자리. 없으면 클래스 맵의 수목 칸을 그대로 쓴다
    dataMap(`${D}/crown.png`, undefined, true).then((m) => { out.crown = m && m.width === 2752 ? m : null; }, () => { out.crown = null; }),
    ...Object.keys(names).map((k) => (k === 'bg' ? image : dataMap)(names[k], onBytes(k)).then((im) => { out[k] = im; done(k); })),
  ]);
  return out;
}

// WebGL2 가 없을 때 보여 줄 정지 그림 주소(오프라인 HTML 이면 내장 base64)
export function stillUrl(map = currentMap()) {
  const e = emb(), n = `${map.dir}/bg_1x.png`;
  if (e && e[n]) return 'data:image/png;base64,' + e[n];
  return BASE + n;
}
