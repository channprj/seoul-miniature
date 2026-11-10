// 배경음. 기본은 꺼짐, 켜도 첫 사용자 동작(클릭·키) 뒤에만 소리를 낸다. 파일은 처음 켤 때 받는다.
// WebAudio(루프 BufferSource + GainNode): iOS 는 <audio>.volume 을 스크립트로 못 바꿔서 페이드가 안 된다.
// 낮 곡 assets/audio/bgm.mp3, 있으면 밤 곡 bgm_night.mp3 로 크로스페이드. 없으면 밤에 볼륨만 조금 낮춘다.
const BASE = 'assets/audio/';
const KEY = 'iso-seoul.bgm';
export const VOL = 0.5;                  // 기본 음량(전체)
export const NIGHT_DIP = 0.7;            // 밤 곡이 없을 때 밤 음량 배율
export const NIGHT_ON = 0.25, NIGHT_OFF = 0.45;   // env.day 히스테리시스: 0.25 아래로 내려가면 밤, 0.45 위로 오르면 낮
export const FADE = 1, XFADE = 3.5;      // 켜고 끄기 / 낮↔밤 전환(초)
// 파일 구성: [루프 끝 PAD초] + [루프 본체 L초, GRID 배수] + [루프 머리 PAD초]. 곡마다 L 이 달라도 길이만으로 루프를 찾는다.
// 파일 전체가 주기적이라, MP3 인코더 지연·패딩(합 0.1초 미만)을 안 지우는 디코더에서도 루프 창이 조금 밀릴 뿐 이음매는 맞다.
export const PAD = 0.5, GRID = 0.1;

// ── 순수 로직(test/audio.test.js)
export function nightState(prev, day) {
  if (prev) return !(day > NIGHT_OFF);
  return day < NIGHT_ON;
}

// 지금 두 트랙의 목표 음량. hasNight 는 밤 곡을 실제로 디코드했는지.
export function targetGains({ on, night, hasNight }) {
  if (!on) return { day: 0, night: 0 };
  if (hasNight) return night ? { day: 0, night: VOL } : { day: VOL, night: 0 };
  return { day: night ? VOL * NIGHT_DIP : VOL, night: 0 };
}

// 목표가 바뀐 트랙만 골라 [{ track, gain, sec }] 로 돌려준다. 켜고 끌 때는 FADE, 낮↔밤은 XFADE.
export function plan(prev, next, toggled) {
  const sec = toggled ? FADE : XFADE;
  return ['day', 'night'].filter((k) => prev[k] !== next[k]).map((k) => ({ track: k, gain: next[k], sec }));
}

// 디코드된 길이에서 루프 구간을 정한다. 지연·패딩이 남아 길이가 조금 늘어도 GRID 로 내림해 같은 L 이 나온다.
export function loopPoints(duration) {
  const x = duration - 2 * PAD;
  if (!(x >= 1)) return { start: 0, end: duration };   // 이 구성이 아닌 짧은 파일은 통째로 돈다
  const len = Math.floor(x / GRID + 1e-3) * GRID;
  return { start: PAD, end: PAD + len };
}

export function readPref(search) {
  const q = new URLSearchParams(search).get('bgm');
  if (q === '1') return true;
  if (q === '0') return false;
  try { return localStorage.getItem(KEY) === '1'; } catch { return false; }
}

// ── 브라우저 쪽. btn 은 aria-pressed 토글 버튼, getDay() 는 0(밤)..1(낮).
export function createBgm(btn, getDay) {
  // 오프라인 단일 HTML 에는 소리를 넣지 않는다
  if (globalThis.__ISO_ASSETS__ || location.protocol === 'file:' || !(window.AudioContext || window.webkitAudioContext)) { btn.hidden = true; return null; }
  let want = readPref(location.search);    // 사용자가 고른 상태(버튼 표시)
  let gesture = false, ctx = null, night = nightState(false, getDay());
  const tr = { day: null, night: null };   // { gain, src }
  let cur = { day: 0, night: 0 }, nightTried = false, dead = false;
  btn.setAttribute('aria-pressed', String(want));

  const fail = (e) => {
    console.warn('배경음을 못 불러옴:', e);
    dead = true; want = false; btn.disabled = true; btn.hidden = true;
  };
  async function load(name) {
    const r = await fetch(BASE + name);
    if (!r.ok) throw new Error(`${name} ${r.status}`);
    const data = await r.arrayBuffer();
    const buf = await new Promise((ok, no) => { const p = ctx.decodeAudioData(data, ok, no); if (p && p.catch) p.catch(no); });   // 구형 WebKit 은 콜백 형식만
    const lp = loopPoints(buf.duration);
    const gain = ctx.createGain(); gain.gain.value = 0; gain.connect(ctx.destination);
    const src = ctx.createBufferSource();
    src.buffer = buf; src.loop = true; src.loopStart = lp.start; src.loopEnd = lp.end;
    src.connect(gain); src.start(0, lp.start);
    return { gain, src };
  }
  // 켜기→끄기→켜기를 받는 중에 하면 두 번 받아 첫 소스가 음량 조절 밖에서 울린다. 트랙마다 한 번만 받는다.
  const pending = {};
  const once = (name) => (pending[name] ||= load(name));
  function apply(toggled) {
    const next = targetGains({ on: want && gesture && !dead, night, hasNight: !!tr.night });
    for (const s of plan(cur, next, toggled)) {
      const t = tr[s.track];
      if (!t) continue;
      const g = t.gain.gain, now = ctx.currentTime;
      g.cancelScheduledValues(now); g.setValueAtTime(g.value, now); g.linearRampToValueAtTime(s.gain, now + s.sec);
    }
    cur = next;
    if (!next.day && !next.night && ctx) setTimeout(() => { if (!cur.day && !cur.night && ctx.state === 'running') { ctx.suspend(); if (keep) keep.pause(); } }, FADE * 1000 + 200);
  }
  // iOS 는 Web Audio 만 쓰면 무음 스위치(벨소리 끔)에 같이 묻힌다. 오디오 세션을 '재생'으로 바꾸고(iOS 17+),
  // 그게 없는 판에서는 소리 없는 <audio> 를 함께 돌려 같은 효과를 낸다. 사용자 동작 안에서 불러야 한다.
  let keep = null;
  function unmute() {
    try { if (navigator.audioSession) navigator.audioSession.type = 'playback'; } catch { /* 지원 안 함 */ }
    if (keep) { if (keep.paused) keep.play().catch(() => {}); return; }
    try {
      const n = 4000, b = new Uint8Array(44 + n), v = new DataView(b.buffer);
      const w = (o, t) => { for (let i = 0; i < t.length; i++) b[o + i] = t.charCodeAt(i); };
      w(0, 'RIFF'); v.setUint32(4, 36 + n, true); w(8, 'WAVEfmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
      v.setUint32(24, 8000, true); v.setUint32(28, 8000, true); v.setUint16(32, 1, true); v.setUint16(34, 8, true); w(36, 'data'); v.setUint32(40, n, true);
      b.fill(128, 44);   // 8비트 무음
      keep = new Audio(URL.createObjectURL(new Blob([b], { type: 'audio/wav' })));
      keep.loop = true; keep.setAttribute('playsinline', ''); keep.play().catch(() => {});
    } catch { keep = null; }
  }
  async function start() {
    if (dead || !want || !gesture) return;
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    unmute();
    if (ctx.state !== 'running' && !document.hidden) ctx.resume();
    if (!tr.day) {
      try { tr.day = await once('bgm.mp3'); } catch (e) { fail(e); return; }
    }
    apply(true);
    if (night && !nightTried) loadNight();
  }
  async function loadNight() {
    nightTried = true;
    try { tr.night = await once('bgm_night.mp3'); } catch { tr.night = null; }   // 없으면 낮 곡 음량만 낮춘다
    cur = { ...cur, night: 0 };
    apply(false);
  }

  // 첫 사용자 동작에서만 시작한다(자동재생 정책). 미리 켜 둔 상태(bgm=1·저장값)도 여기서 시작.
  const onGesture = () => {
    gesture = true;
    for (const ev of GEST) removeEventListener(ev, onGesture, true);
    start();
  };
  const GEST = ['pointerup', 'touchend', 'click', 'keydown'];   // iOS 는 누르는 순간(pointerdown)을 소리 허용 동작으로 치지 않는다
  for (const ev of GEST) addEventListener(ev, onGesture, true);

  btn.onclick = () => {
    if (dead) return;
    want = !want;
    btn.setAttribute('aria-pressed', String(want));
    try { localStorage.setItem(KEY, want ? '1' : '0'); } catch { /* 저장 불가 */ }
    gesture = true;
    if (want) start(); else if (ctx) apply(true);
  };
  document.addEventListener('visibilitychange', () => {
    if (!ctx) return;
    if (document.hidden) { ctx.suspend(); if (keep) keep.pause(); }
    else if (cur.day || cur.night) { ctx.resume(); if (keep) keep.play().catch(() => {}); }
  });
  // 0.5초마다 시각을 보고 낮↔밤을 바꾼다
  setInterval(() => {
    const n = nightState(night, getDay());
    if (n === night) return;
    night = n;
    if (!ctx || !tr.day) return;
    if (night && !nightTried && want) { loadNight(); return; }
    apply(false);
  }, 500);

  // 버튼은 파일이 있을 때만 보인다(HEAD 만, 본 파일은 켤 때 받는다)
  btn.hidden = true;
  fetch(BASE + 'bgm.mp3', { method: 'HEAD' }).then((r) => { if (r.ok) btn.hidden = false; else dead = true; }, () => { dead = true; });

  const api = { get state() { return { want, gesture, night, hasNight: !!tr.night, ctx: ctx && ctx.state, cur, dead, loop: tr.day && [tr.day.src.loopStart, tr.day.src.loopEnd] }; } };
  globalThis.__isoBgm = api;
  return api;
}
