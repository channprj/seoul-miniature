import { buildVehicleAtlas } from './vehicles.js';
import { loadAssets, probeWebGL2, pickResolution, stillUrl } from './assets.js';
import { makeProjection, decodeDepth } from './geom.js';
import { createRenderer } from './render.js';
import { createMovers, createFallbackTraffic, buildPeopleAtlas } from './movers.js';
import { createCamera } from './camera.js';
import { PLACES, TOUR, sampleTour } from './tour.js';
import { aboutHtml, verifyHtml } from './panels.js';
import { createBirds, emitBirds } from './birds.js';
import { createBgm } from './audio.js';
import { buildStaticLights } from './nightlights.js';

const $ = (s) => document.querySelector(s);
const canvas = $('#c');
const params = new URLSearchParams(location.search);
const SIM_DT = 1 / 30;
const LOOK0 = params.get('look') === '1' ? 1 : 2;   // 기본 룩 2(세련된 픽셀아트), ?look=1 = 예전 룩
const DAY_SECONDS = 150;                 // 자동 흐름에서 하루가 지나는 실제 시간

const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
const lerp = (a, b, t) => a + (b - a) * t;
const mix3 = (a, b, t) => [0, 1, 2].map((i) => lerp(a[i], b[i], t));
const hex = (c) => '#' + c.map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');
// 이미지 픽셀을 JS 로 읽는다(클래스·깊이 맵은 색 변환 없는 PNG 라 값이 그대로 나온다)
function readPixels(bmp) {
  const c = document.createElement('canvas'); c.width = bmp.width; c.height = bmp.height;
  const g = c.getContext('2d', { willReadFrequently: true });
  g.drawImage(bmp, 0, 0);
  const d = g.getImageData(0, 0, bmp.width, bmp.height).data;
  c.width = c.height = 0;   // 2D 캔버스 뒷버퍼를 바로 놓는다(iOS 는 캔버스 메모리 한도가 빡빡하다)
  return d;
}

// 화면 위 안내 상자(컨텍스트 유실 등). 자동 새로고침은 하지 않는다(무한 새로고침 방지).
function showAlert(title, text, label, onClick) {
  let el = $('#alert');
  if (!el) { el = document.createElement('div'); el.id = 'alert'; el.setAttribute('role', 'alert'); document.body.appendChild(el); }
  el.innerHTML = '<div class="card"><h2></h2><p></p><div class="row"><button class="primary"></button></div></div>';
  el.querySelector('h2').textContent = title; el.querySelector('p').textContent = text;
  const b = el.querySelector('button'); b.textContent = label; b.onclick = onClick;
}
// WebGL2 가 없거나 컨텍스트를 못 만들면 빈 화면 대신 정지 그림(가로로 밀어 볼 수 있게)과 안내
function showStill(reason) {
  document.body.classList.add('still');
  const d = document.createElement('div');
  d.id = 'still';
  d.innerHTML = '<div class="scroll"><img alt="경복궁 일대 픽셀아트 미니어처 정지 그림"></div>' +
    '<div class="card"><h2>움직이는 미니어처를 띄우지 못했습니다</h2><p></p><div class="row"><button class="primary">다시 시도</button></div></div>';
  d.querySelector('p').textContent = `${reason} 대신 정지 그림을 보여 드립니다. 최신 Safari·Chrome 에서 열면 시간·계절이 바뀌고 차와 사람이 움직입니다.`;
  d.querySelector('button').onclick = () => location.reload();
  const img = d.querySelector('img'), sc = d.querySelector('.scroll');
  img.onload = () => { sc.scrollLeft = (sc.scrollWidth - sc.clientWidth) * 0.45; sc.scrollTop = (sc.scrollHeight - sc.clientHeight) * 0.5; };
  img.src = stillUrl();
  document.body.appendChild(d);
  // 정지 그림 화면에서도 출처 패널은 열려야 한다(안내 문구가 「출처」를 가리킨다). 나머지 버튼은 CSS 로 숨긴다.
  const panel = $('#panel');
  $('#about').onclick = () => { $('#panel-body').innerHTML = aboutHtml(); panel.hidden = false; };
  panel.onclick = (e) => { if (e.target === panel || e.target.classList.contains('close')) panel.hidden = true; };
  $('#loading').classList.add('done');
}
class NoWebGL extends Error {}

async function boot() {
  const bar = $('#loading .bar i');
  // 무거운 그림을 받기 전에 WebGL2 부터 확인한다
  const gl = probeWebGL2();
  if (!gl) throw new NoWebGL('이 브라우저에서는 WebGL2 를 쓸 수 없습니다.');
  const assets = await loadAssets((p) => { bar.style.width = `${Math.round(p * 100)}%`; }, { res: pickResolution(gl) });
  const scene = assets.scene;
  const proj = makeProjection(scene.camera);
  assets.people = buildPeopleAtlas(scene.walker_palette);
  // 차량 스프라이트는 코드로 그린다(배경과 같은 픽셀 격자). 교통 sim 이 쓰는 차종·색 조합은 그대로 둔다.
  const va = buildVehicleAtlas(scene, proj);
  assets.veh = va.veh; assets.vehDepth = va.vehDepth; assets.vehShadow = va.vehShadow;
  scene.vehicle_atlas = { ...scene.vehicle_atlas, frames: va.frames };
  let R;
  try { R = createRenderer(canvas, assets, proj, { look: LOOK0 }); } catch (e) { console.error(e); throw new NoWebGL('그래픽(WebGL2) 화면을 만들지 못했습니다.'); }
  // 메모리가 모자라면 iOS·안드로이드가 컨텍스트를 빼앗는다. 복구는 새로고침뿐이라 안내만 띄운다.
  let lost = false;
  canvas.addEventListener('webglcontextlost', (e) => {
    e.preventDefault(); lost = true;
    showAlert('화면이 멈췄습니다', '기기 그래픽 메모리가 모자라 미니어처를 더 그리지 못했습니다. 다시 불러오면 이어서 볼 수 있습니다.', '다시 불러오기', () => location.reload());
  });
  const movers = createMovers(scene, proj);
  // 새: classes.png 로 앉을 곳·돌 곳을 고정 시드로 고른다. 깊이는 앉는 자리에서만 읽고 버린다.
  const birds = (() => {
    const W = assets.sem.width, H = assets.sem.height, sp = readPixels(assets.sem);
    const cls = new Uint8Array(W * H);
    let bad = 0;
    for (let i = 0; i < cls.length; i++) { cls[i] = sp[i * 4]; if (cls[i] > 11) bad++; }
    if (bad) console.warn('classes.png 값이 0–11 밖:', bad);
    let dp = readPixels(assets.depth);
    const DW = assets.depth.width;
    const groundAt = (y) => -((proj.H / 2 - y) * proj.m + proj.cy) * proj.ey[2] / proj.vd[2] - proj.camDotVd;
    const depthAt = (x, y) => { const o = (y * DW + x) * 4, d = decodeDepth(dp[o], dp[o + 1]); return Number.isFinite(d) ? d : groundAt(y + 0.5); };
    R.setStaticLights(buildStaticLights({ w: W, h: H, cls }, movers.lamps, proj, [-258.6, 12.2, 297.3, 878.1]));   // 룩 2 야간 정적 광원
    const b = createBirds({ w: W, h: H, cls }, { seed: Number(params.get('birdseed') || 11), depthAt });
    dp = null;   // depthAt 클로저가 18 MB 픽셀 배열을 붙잡지 않게
    return b;
  })();
  // 텍스처로 올렸고 픽셀도 다 읽었으니 디코드된 그림을 놓는다(ImageBitmap 은 close 로 즉시, <img> 폴백은 GC 에 맡김)
  for (const k of ['bg', 'depth', 'cls', 'sem']) { try { assets[k].close?.(); } catch { /* 이미 닫힘 */ } assets[k] = null; }
  const birdView = { day: 1, F: 1, kH: proj.ey[2] / proj.m, kD: proj.m * proj.ey[2] / proj.vd[2], vdz: proj.vd[2] };

  let traffic, trafficKind = 'live';
  try {
    const mod = await import('./sim/traffic.js');
    traffic = mod.createTraffic(scene, { seed: Number(params.get('seed') || 7), targetCount: Number(params.get('cars') || 150) });   // 도심답게 막히지만 흐르는 수준(교착·강제 제거 0 확인)
  } catch (e) {
    console.warn('교통 sim 을 불러오지 못해 단순 대체를 씁니다:', e);
    traffic = createFallbackTraffic(scene); trafficKind = 'fallback';
  }

  const cam = createCamera(canvas, proj.W, proj.H);
  // 휴대폰 경로(절반 해상도 그림 + 원본 타일): 최대 확대 = 원본 텍셀(0.25 m) 하나가 기기 4 px. 더블탭은 텍셀 1·2·4 px 배율에 멈춘다.
  if (assets.res === 1) { cam.maxScale = 8; cam.tapSteps = [2, 4, 8]; }
  const state = {
    tod: Number(params.get('tod') || 9), autoTime: !params.has('tod'),
    season: Number(params.get('season') || 1), seasonW: [0, 0, 0, 0],
    rain: false, debug: false, hud: false, tour: null, time: 0, manual: false,
    tilt: params.get('tilt') !== '0',
    look: LOOK0,
  };
  state.seasonW[state.season] = 1;

  // ── UI
  const places = $('#places');
  for (const p of PLACES) {
    const b = document.createElement('button');
    b.textContent = p.name;
    b.onclick = () => { stopTour(); cam.flyTo(p.x, p.y, fitVh(p.vh), 1.8); setCaption(p.note); };
    places.appendChild(b);
  }
  const todInput = $('#tod'), clock = $('#clock'), playBtn = $('#play');
  todInput.oninput = () => { state.tod = Number(todInput.value); state.autoTime = false; playBtn.setAttribute('aria-pressed', 'false'); stopTour(); };
  playBtn.onclick = () => { state.autoTime = !state.autoTime; playBtn.setAttribute('aria-pressed', String(state.autoTime)); };
  playBtn.setAttribute('aria-pressed', String(state.autoTime));
  const seasonBtns = [...document.querySelectorAll('#seasons button')];
  const setSeason = (s) => { state.season = s; seasonBtns.forEach((b) => b.classList.toggle('on', Number(b.dataset.s) === s)); };
  seasonBtns.forEach((b) => { b.onclick = () => { stopTour(); setSeason(Number(b.dataset.s)); }; });
  setSeason(state.season);
  const rainBtn = $('#rain');
  rainBtn.onclick = () => { state.rain = !state.rain; rainBtn.setAttribute('aria-pressed', String(state.rain)); };
  const tiltBtn = $('#tilt');
  tiltBtn.setAttribute('aria-pressed', String(state.tilt));
  tiltBtn.onclick = () => { state.tilt = !state.tilt; tiltBtn.setAttribute('aria-pressed', String(state.tilt)); };
  const lookBtn = $('#look');
  if (lookBtn) lookBtn.onclick = () => { state.look = state.look === 2 ? 1 : 2; };
  const caption = $('#caption');
  let captionTimer = 0;
  function setCaption(text, hold = 6) { caption.textContent = text || ''; captionTimer = hold; }

  const tourBtn = $('#tour');
  function startTour() { state.tour = { t: 0 }; document.body.classList.add('cinema'); tourBtn.classList.add('on'); cam.lock(true); }
  function stopTour() {
    if (!state.tour) return;
    state.tour = null; document.body.classList.remove('cinema'); tourBtn.classList.remove('on'); cam.lock(false);
    todInput.value = state.tod;
  }
  tourBtn.onclick = () => (state.tour ? stopTour() : startTour());
  cam.onUserInput = () => { if (state.tour && !state.manual) stopTour(); };
  // 비둘기: 탭하거나 마우스를 (버튼 안 누르고) 가까이 가져가면 날아오른다. 드래그로 지나가는 것만으로는 안 난다.
  const scareAt = (x, y) => {
    const v = cam.view();
    birds.scare(v.originX + x * cam.dpr / v.scale, v.originY + y * cam.dpr / v.scale, Math.max(6, 36 / cam.zoom));
  };
  canvas.addEventListener('pointermove', (e) => { if (e.pointerType === 'mouse' && !e.buttons) scareAt(e.clientX, e.clientY); }, { passive: true });
  cam.onTap = (x, y) => scareAt(x, y);

  const panel = $('#panel'), body = $('#panel-body');
  const openPanel = (html) => { body.innerHTML = html; panel.hidden = false; };
  panel.onclick = (e) => { if (e.target === panel || e.target.classList.contains('close')) panel.hidden = true; };
  $('#about').onclick = () => openPanel(aboutHtml());
  $('#verify').onclick = () => {
    openPanel(verifyHtml(state));
    body.querySelector('[data-a=cls]').onclick = (e) => { state.debug = !state.debug; e.target.setAttribute('aria-pressed', String(state.debug)); };
    body.querySelector('[data-a=bus]').onclick = () => { panel.hidden = true; cam.flyTo(1042, 201, 150, 1.2); setCaption('버스 가림 사례 구간(자하문로). 지붕 뒤로 지나가는 차를 확인하세요.', 12); };
    body.querySelector('[data-a=hud]').onclick = (e) => { state.hud = !state.hud; $('#hud').hidden = !state.hud; e.target.setAttribute('aria-pressed', String(state.hud)); };
    body.querySelector('[data-a=bench]').onclick = () => { panel.hidden = true; runBench(); };
  };
  addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { panel.hidden = true; stopTour(); }
    if (e.key === 'h') document.body.classList.toggle('clean');
    if (e.key === ' ') { e.preventDefault(); playBtn.click(); }
  });

  // ── 환경(시각 → 조명)
  const env = { season: new Float32Array(4), shadowTint: new Float32Array(scene.sun.shadow_tint), palace: new Float32Array([-258.6, 12.2, 297.3, 878.1]),
    day: 1, dusk: 0, lateNight: 0, time: 0, shadowAmt: 1, snow: 0, rain: 0, debug: false, tilt: 0, tiltR: 0,
    look: LOOK0, sun: new Float32Array([0, 0, 1]), shadeCol: new Float32Array(3), sunAmt: 0, rayLen: 14 };
  const SKY = { night: [[10, 14, 34], [24, 30, 62]], dusk: [[62, 58, 110], [242, 150, 96]], day: [[156, 196, 232], [226, 234, 232]] };
  // 룩 2: 지도 밖은 옅은 회청(위) → 따뜻한 종이색(아래)
  const SKY2 = { night: [[10, 14, 32], [24, 28, 54]], dusk: [[92, 86, 116], [226, 186, 156]], day: [[196, 206, 214], [238, 233, 222]] };
  // 룩 2 해: 방위는 장면 sun(차·사람 그림자와 같은 방향), 고도만 시각·계절 따라
  const sunEz = scene.sun.euler_deg[2] * Math.PI / 180;
  const SUN_H = [Math.sin(sunEz), -Math.cos(sunEz)];
  const SUN_MAX = [46, 54, 40, 28];   // 계절별 한낮 고도(도)
  createBgm($('#sound'), () => env.day);   // 배경음(기본 꺼짐, 파일 없으면 버튼 숨김)
  function updateEnv(dt) {
    const t = ((state.tod % 24) + 24) % 24;
    env.day = smooth(5.6, 7.4, t) * (1 - smooth(17.6, 19.6, t));
    env.dusk = 4 * env.day * (1 - env.day);
    env.lateNight = t < 12 ? smooth(0.0, 1.5, t) * (1 - smooth(4.5, 5.6, t)) : smooth(23.0, 24.0, t) * 0.4;
    for (let i = 0; i < 4; i++) {
      const target = i === state.season ? 1 : 0;
      state.seasonW[i] += (target - state.seasonW[i]) * (1 - Math.exp(-dt * 2.2));
      env.season[i] = state.seasonW[i];
    }
    env.shadowAmt = env.day;
    env.snow = state.seasonW[3] * 0.85;
    env.rain = state.rain ? 1 - state.seasonW[3] : 0;
    env.debug = state.debug; env.time = state.time;
    env.look = state.look;
    const sky = state.look === 2 ? SKY2 : SKY;
    if (state.look === 2) {
      const up = Math.max(0, Math.sin(Math.PI * (t - 6) / 12));
      const emax = SUN_MAX.reduce((s, v, i) => s + v * state.seasonW[i], 0);
      const e = (6 + (emax - 6) * up) * Math.PI / 180;
      env.sun[0] = SUN_H[0] * Math.cos(e); env.sun[1] = SUN_H[1] * Math.cos(e); env.sun[2] = Math.sin(e);
      env.sunAmt = env.day * (1 - 0.65 * env.rain) * (1 - 0.3 * state.seasonW[3]);   // 비·눈밭에선 옅게
      env.rayLen = lerp(18, 13, up);
      const sc = mix3(mix3([0.70, 0.72, 0.86], [0.60, 0.52, 0.72], Math.min(1, env.dusk * 1.3)), [0.70, 0.72, 0.84], env.day * env.day);
      env.shadeCol.set(mix3(sc, [0.76, 0.83, 0.98], state.seasonW[3] * env.day));   // 눈 위 그림자는 맑은 하늘빛
    }
    document.body.classList.toggle('look2', state.look === 2);
    if (lookBtn) lookBtn.setAttribute('aria-pressed', String(state.look === 2));
    const a = hex(mix3(mix3(sky.night[0], sky.dusk[0], Math.min(1, env.dusk * 1.2)), sky.day[0], env.day * env.day));
    const b = hex(mix3(mix3(sky.night[1], sky.dusk[1], Math.min(1, env.dusk * 1.2)), sky.day[1], env.day * env.day));
    document.body.classList.toggle('dark', env.day < 0.5);
    document.documentElement.style.setProperty('--sky-a', a);
    document.documentElement.style.setProperty('--sky-b', b);
    const hh = Math.floor(t), mm = Math.floor((t - hh) * 60);
    clock.textContent = `${String(hh).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
    if (state.autoTime || state.tour) todInput.value = t;
  }

  // ── 딥링크: #x,y,vh(지도 px 중심·세로 시야) [&t=시각(시간 멈춤일 때만)] [&s=계절 0..3]
  let hashLast = location.hash, hashAt = 0;
  function hashNow() {
    let h = `#${Math.round(cam.cx)},${Math.round(cam.cy)},${Math.round(canvas.clientHeight / cam.zoom)}`;
    if (!state.autoTime) h += `&t=${(((state.tod % 24) + 24) % 24).toFixed(1)}`;
    return h + `&s=${state.season}`;
  }
  // replaceState 는 hashchange 를 안 일으킨다. 0.5초에 한 번, 바뀐 때만(사파리는 30초에 100회 넘으면 예외), 투어 중에는 안 씀.
  function syncHash(now, force = false) {
    if (state.tour || (!force && now - hashAt < 500)) return;
    hashAt = now;
    const h = hashNow();
    if (h === hashLast) return;
    try { history.replaceState(null, '', h); hashLast = h; } catch { /* file:// 등 */ }
  }
  function applyHash(fly) {
    const m = /^#(-?[\d.]+),(-?[\d.]+),([\d.]+)(.*)$/.exec(location.hash);
    if (!m) return false;
    const x = Number(m[1]), y = Number(m[2]), vh = Math.max(20, Number(m[3]));
    if (![x, y, vh].every(Number.isFinite)) return false;
    const q = new URLSearchParams(m[4].replace(/^&/, ''));
    const t = Number(q.get('t'));
    if (q.has('t') && Number.isFinite(t)) {
      state.tod = ((t % 24) + 24) % 24; state.autoTime = false;
      playBtn.setAttribute('aria-pressed', 'false'); todInput.value = state.tod;
    }
    const s = Number(q.get('s'));
    if (q.has('s') && [0, 1, 2, 3].includes(s)) {
      setSeason(s);
      if (!fly) { state.seasonW.fill(0); state.seasonW[s] = 1; }
    }
    if (fly) cam.flyTo(x, y, vh, 1.4); else cam.set(x, y, vh);
    hashLast = location.hash;
    return true;
  }
  const shareBtn = $('#share');
  shareBtn.onclick = async () => {
    syncHash(performance.now(), true);
    const url = location.href;
    let ok = false;
    try { if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(url); ok = true; } } catch { /* 권한 거부 */ }
    if (!ok) {
      // file:// 등 보안 컨텍스트가 아니면 clipboard API 가 없다 → 숨은 textarea 복사, 그것도 안 되면 캡션에 주소를 보여 준다
      const ta = document.createElement('textarea');
      ta.value = url; ta.setAttribute('readonly', ''); ta.style.cssText = 'position:fixed;left:-9999px;opacity:0';
      document.body.appendChild(ta); ta.select();
      try { ok = document.execCommand('copy'); } catch { ok = false; }
      ta.remove();
    }
    shareBtn.textContent = ok ? '복사됨' : '주소를 위에 표시';
    if (!ok) setCaption(url, 15);
    setTimeout(() => { shareBtn.textContent = '링크 복사'; }, 1800);
  };

  // ── 세로 화면 보정
  // 투어·장소의 vh 는 가로 화면 기준이다. 세로에서는 같은 vh 면 좌우가 너무 좁아지므로 화면비에 따라 물러난다(최대 2배, 지도 전체 높이 근처까지).
  function fitVh(vh) {
    const r = canvas.clientHeight / Math.max(1, canvas.clientWidth);
    const k = Math.min(2, Math.max(1, Math.sqrt(1.6 * r)));
    return Math.min(vh * k, Math.max(vh, proj.H * 1.15));
  }
  // 첫 장면. 세로 화면이면 광화문–근정전–경회루가 위아래 UI 사이에 들어오게 맞춘다(해시가 있으면 applyHash 가 덮는다).
  function initialView() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    // 넓은 화면은 전체 지도. 세로 화면과 키 낮은 가로 휴대폰은 궁궐 축에 맞춘다(전체 지도가 너무 작게 보여서).
    if (h <= w * 1.15 && h > 500) { cam.set(proj.W * 0.47, proj.H * 0.52, proj.H * 0.86); return; }
    const box = [715, 720, 1370, 1290];   // 지도 px: 광화문(서쪽 끝 포함) ~ 경회루 연못
    const rect = (sel) => { const e = $(sel); const r = e && getComputedStyle(e).display !== 'none' ? e.getBoundingClientRect() : null; return r && r.height ? r : null; };
    const top = Math.max(rect('#places')?.bottom || 0, rect('#title')?.bottom || 0) + 8;
    const bot = h - (rect('#dock')?.top ?? h) + 8;
    const zoom = Math.min(w / (box[2] - box[0]), Math.max(80, h - top - bot) / (box[3] - box[1]));
    const cy = (box[1] + box[3]) / 2 + ((bot - top) / 2) / zoom;   // 보이는 띠의 가운데에 상자 가운데가 오게
    cam.set((box[0] + box[2]) / 2, cy, h / zoom);
  }
  // 첫 방문 힌트(4초). 다시 오면 안 보인다. 첫 조작에 바로 사라진다.
  function showHint() {
    if (params.has('clean') || params.has('tour') || params.has('nohint')) return;
    try { if (localStorage.getItem('iso-hint')) return; localStorage.setItem('iso-hint', '1'); } catch { /* 사생활 보호 모드 */ }
    const el = document.createElement('div');
    el.id = 'hint'; el.setAttribute('aria-hidden', 'true');
    el.textContent = matchMedia('(pointer: coarse)').matches ? '드래그로 이동 · 두 손가락으로 확대 · 둘러보기 ▶' : '드래그로 이동 · 휠로 확대 · 둘러보기 ▶';
    document.body.appendChild(el);
    requestAnimationFrame(() => el.classList.add('on'));
    const off = () => { el.classList.remove('on'); setTimeout(() => el.remove(), 600); canvas.removeEventListener('pointerdown', off); };
    canvas.addEventListener('pointerdown', off);
    setTimeout(off, 4000);
  }

  // ── 프레임
  let acc = 0;
  const ft = new Float32Array(240); let fi = 0, fn = 0;
  function advance(dt) {
    state.time += dt;
    acc += dt;
    let n = 0;
    while (acc >= SIM_DT && n < 8) { traffic.step(SIM_DT); birds.step(SIM_DT); acc -= SIM_DT; n++; }
    if (n === 8) acc = 0;
    if (state.tour) {
      state.tour.t += dt;
      const s = sampleTour(state.tour.t);
      if (!s) stopTour();
      else {
        cam.set(s.x, s.y, fitVh(s.vh));
        state.tod = s.tod; if (s.season !== state.season) setSeason(s.season);
        if (s.caption !== caption.textContent) setCaption(s.caption, 99);
      }
    } else if (state.autoTime) state.tod = (state.tod + dt * 24 / DAY_SECONDS) % 24;
    cam.update(dt);
    updateEnv(dt);
    if (captionTimer > 0 && !state.tour) { captionTimer -= dt; if (captionTimer <= 0) caption.textContent = ''; }
  }
  function draw() {
    const view = cam.view();
    const night = 1 - env.day;
    R.begin();
    R.look = env.look;   // movers 가 룩 2 전조등 원뿔을 고른다
    movers.emitPeople(R, state.time, night);
    movers.emitVehicles(R, traffic.vehicles, acc / SIM_DT, night);
    movers.emitSignals(R, traffic.signals);
    if (night > 0.02) movers.emitLamps(R, traffic.signals, R.look === 2);
    birdView.day = env.day; birdView.F = R.pickF(view.scale);
    emitBirds(R, birds, birdView);
    // 틸트시프트: 멀리·중간 배율에서만. 가까이 당기면(화면 1px 당 지도 1.3→2.8 px) 사라져 픽셀이 또렷하게 남는다.
    env.tilt = state.tilt ? 1 - smooth(1.3, 2.8, view.scale / cam.dpr) : 0;
    env.tiltR = 4.5 * cam.dpr;
    R.render(view, env);
  }
  let last = performance.now(), running = true;
  function frame(now) {
    if (lost) { running = false; return; }
    // 탭이 숨겨지면 루프를 멈춘다(배터리·발열). 돌아오면 last 를 다시 잡아 큰 dt 없이 이어 간다.
    if (document.hidden) { running = false; return; }
    if (!state.manual) {
      const dt = Math.min(0.25, (now - last) / 1000);
      last = now;
      ft[fi] = dt * 1000; fi = (fi + 1) % ft.length; fn = Math.min(fn + 1, ft.length);
      advance(dt); draw();
      syncHash(now);
      if (state.hud) drawHud();
      if (bench) bench.tick(dt);
    }
    requestAnimationFrame(frame);
  }
  function stats() {
    const a = Array.from(ft.subarray(0, fn)).sort((x, y) => x - y);
    const avg = a.reduce((s, v) => s + v, 0) / (a.length || 1);
    return { avg, p95: a[Math.floor(a.length * 0.95)] || 0, max: a[a.length - 1] || 0 };
  }
  function drawHud() {
    const s = stats(), c = R.counts();
    $('#hud').textContent = `frame  avg ${s.avg.toFixed(1)} ms  p95 ${s.p95.toFixed(1)}  max ${s.max.toFixed(1)}\n` +
      `canvas ${canvas.width}×${canvas.height} dpr ${cam.dpr}  zoom ${(cam.view().scale / cam.dpr).toFixed(2)}×\n` +
      `차량 ${traffic.vehicles.length} (${trafficKind})  스프라이트 ${c.sprites}  빛 ${c.lights}`;
  }

  // ── 벤치마크: 고정 시나리오(투어)를 돌리며 프레임타임 기록 → JSON
  let bench = null;
  function runBench() {
    const samples = [];
    startTour();
    bench = {
      tick(dt) {
        samples.push(Math.round(dt * 1000 * 100) / 100);
        if (!state.tour || samples.length > 60 * 60) {
          bench = null; stopTour();
          const a = [...samples].sort((x, y) => x - y);
          const dbg = R.gl.getExtension('WEBGL_debug_renderer_info');
          const result = {
            note: '이 기기에서 실제로 잰 값입니다. 다른 기기의 성능을 뜻하지 않습니다.',
            userAgent: navigator.userAgent, gpu: dbg ? R.gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : 'unknown',
            canvas: [canvas.width, canvas.height], dpr: cam.dpr, frames: a.length,
            avg_ms: a.reduce((s, v) => s + v, 0) / a.length, p50_ms: a[a.length >> 1], p95_ms: a[Math.floor(a.length * 0.95)], p99_ms: a[Math.floor(a.length * 0.99)], max_ms: a[a.length - 1],
            vehicles: traffic.vehicles.length, samples_ms: samples,
          };
          const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 1)], { type: 'application/json' }));
          openPanel(`<h2>벤치마크 결과(이 기기 실측)</h2><pre>${JSON.stringify({ ...result, samples_ms: `[${samples.length}개]` }, null, 1)}</pre><div class="row"><a href="${url}" download="iso-seoul-bench.json">JSON 내려받기</a></div>`);
        }
      },
    };
  }

  // ── 캡처·테스트용 수동 시계: __iso.manual(true) 후 __iso.step(dt) 로 한 프레임씩 결정론적으로 진행
  window.__iso = {
    state, cam, traffic, env, R,
    manual(on) { state.manual = on; last = performance.now(); },
    step(dt) { advance(dt); draw(); },
    startTour, stopTour, setSeason,
    tourLength: TOUR.total,
    birds, scareBirds: (x, y, r) => birds.scare(x, y, r), launchBirds: (i) => birds.launch(i),
    applyHash, hashNow,
  };

  document.addEventListener('visibilitychange', () => {
    if (document.hidden || running || lost) return;
    running = true; last = performance.now();
    requestAnimationFrame((t) => { last = t; frame(t); });
  });

  addEventListener('resize', () => cam.resize());
  cam.resize();
  initialView();
  applyHash(false);
  addEventListener('hashchange', () => { if (location.hash !== hashLast) { stopTour(); applyHash(true); } });
  for (let i = 0; i < 3; i++) advance(SIM_DT);
  draw();
  $('#loading').classList.add('done');
  if (params.has('tour')) startTour();
  if (params.has('clean')) document.body.classList.add('clean');
  showHint();
  requestAnimationFrame((t) => { last = t; frame(t); });
}

// iOS: 페이지 전체 핀치 확대를 막는다(지도 핀치는 캔버스가 받는다)
document.addEventListener('gesturestart', (e) => e.preventDefault());
if (matchMedia('(pointer: coarse)').matches) $('#caption').textContent = '드래그로 이동 · 두 손가락으로 확대';

boot().catch((e) => {
  console.error(e);
  if (e instanceof NoWebGL) { showStill(e.message); return; }
  $('#loading p').textContent = '불러오지 못했습니다: ' + e.message;
});
