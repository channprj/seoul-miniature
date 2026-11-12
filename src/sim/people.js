// 사람들 사이의 상호작용(행동 로직만, DOM·WebGL 없음 → node --test 로 검사: test/people.test.js). 그리기는 src/emotes.js.
//
// 두 종류의 사람을 다룬다.
//   1) 걷는 사람(scene.walkers): 닫힌 식(위상 + 시간×속도)으로 걷는다(그리기는 emotes.js). 여기서는 사람별 「누적 정지 시간」(ov.off)만 빼서
//      잠깐 세울 수 있게 하고, 서 있는 동안은 ov.skip 으로 movers 가 건너뛰게 한 뒤 이쪽(guests)에서 인사·손 흔들기 자세로 그린다.
//      걷는 사람의 유형(직장인·학생·어르신·관광객·한복…)과 동행(아이·유모차·휠체어·개)은 번호 해시와 경로 위치로 고정된다.
//   2) 출연진(actors): 사진 찍는 무리, 가이드와 관광객, 한복 일행, 아이와 보호자, 수문장 등. 지도에 늘 살고 있고(시야 안에서 생기거나
//      사라지지 않는다), 미리 검사해 둔 직선 구간만 걷는다.
//
// 좌표는 로컬 미터(z = 0 지면). 장소는 손으로 찍지 않고 classes.png(화면 공간 클래스 맵)와 고정 시드로 고른다(그림을 다시 그려도 동작).
// 클래스 맵은 화면 공간이라, 발 픽셀이 지붕·벽이면 「건물 안」이 아니라 「건물에 가려진 곳」이다. 그래서
//   · 멈추거나 연출하는 자리는 발 픽셀이 궁궐 마당(5)·광장/보행로(11)(소풍은 잔디 3, 고양이는 맨땅 1 포함)인 곳만 쓰고
//   · 가려진 곳(궁궐 지붕·벽 8·9)은 수문장 행렬이 나오고 들어가는 자리로만 쓴다.
import { cumLengths, pointAt, hash01, makeProjection } from '../geom.js';
import { nextRand } from '../birds.js';

const TAU = Math.PI * 2;
export const BUB = { DOTS: 1, NOTE: 2, BANG: 3, HEART: 4, SMILE: 5 };
export const CEREMONY_HOURS = [10, 14];   // 수문장 교대 의식 시작 시각(실제 행사와 같은 10시·14시)
export const PAL_OPEN = [9, 18];           // 궁궐 관람 시간(시). 이 밖에는 궁 안 방문객·안내원·궁 안 장면이 없다.
export const CEREMONY_WINDOW = 0.5;
export const RUN_GROUPS = 44;             // 궁 둘레 러너 무리 수(혼자 62 %, 2~5명 크루 38 %). 아침·저녁에 전부, 낮에는 45 %.
export const RUN_GROUPS_CITY = 64;        // 여의도 강변 러너 무리 수(강변 띠 길이에 비례해 나눈다)
export const BIKE_GROUPS = 120;           // 여의도 자전거 무리 수(자전거 띠 길이에 비례)
// 자전거 탄 사람의 옷(팔레트 번호): 보통 옷 8 + 운동복 4. emotes.js 가 같은 목록 순서로 모형 칸을 만든다(look.pal = 이 목록의 번호).
export const riderPals = (cast) => [...cast.normal.slice(0, 8), ...cast.runner.slice(0, 4)];
const BIT = { PAVE: 1, GRASS: 2, DIRT: 4 };
const fr = (v) => v - Math.floor(v);
const sm = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
export const dayOf = (tod) => { const t = ((tod % 24) + 24) % 24; return sm(5.6, 7.4, t) * (1 - sm(17.6, 19.6, t)); };   // main.js updateEnv 와 같은 식

export const SIM_DT = 1 / 30;
// 조정용 상수
export const HANBOK = { palace: 0.27, near: 0.10, city: 0.02 };   // 걷는 방문객 가운데 한복 비율(궁 안 / 광화문 앞·서촌·북촌 / 도심). 궁 안 실측(일행·피사체 포함)은 test 가 25~35 % 로 잡는다.
export const T = { NORMAL: 0, OFFICE: 1, STUDENT: 2, ELDER: 3, TOURIST: 4, HIKER: 5, CLEANER: 6, STAFF: 7, HANBOK: 8, PARENT: 9, STROLLER: 10, WHEEL: 11, DOG: 12, JOGGER: 13 };
const SPEED = [1, 1.12, 1, 0.62, 0.8, 0.95, 0.5, 0.85, 0.78, 0.82, 0.8, 0.72, 0.9, 2.1];

// 어른 모양(기본 4×9 사람)으로 그리는 유형의 옷 색을 scene.walker_palette 뒤에 덧붙인다. 기존 번호는 그대로. 아틀라스를 만들기 전에 불러야 한다.
// [윗옷, 아래옷, 머리]. 한복·수문장·어린이·동물은 팔레트가 아니라 emotes.js 의 전용 모형이다.
export function addCast(scene) {
  if (scene._cast) return scene._cast;
  const pal = scene.walker_palette, n0 = pal.length;
  const add = (list) => list.map((p) => pal.push(p) - 1);
  const cast = {
    n0,
    normal: Array.from({ length: 24 }, (_, i) => Math.floor((i + 0.5) * n0 / 24)),
    elder: add([['#8a9a7a', '#5a5248', '#c9c9c9'], ['#b08a8a', '#3f3f4a', '#e4e4e4'], ['#6f7f9a', '#4a4a52', '#b8b8b8'], ['#c9b48e', '#5a4a3c', '#d8d8d8'],
      ['#7a6a8a', '#3b3b46', '#a8a8a8'], ['#a05a4a', '#4a4038', '#e0e0e0'], ['#5f8a8a', '#3f3f4a', '#cfcfcf'], ['#d8cfc0', '#6a6258', '#bdbdbd']]),
    office: add([['#27365c', '#27365c', '#141210'], ['#3d3d48', '#3d3d48', '#1e1a18'], ['#1f1f26', '#1f1f26', '#2b2320'], ['#f1f1f1', '#27365c', '#141210'],
      ['#dfe7f2', '#3d3d48', '#1e1a18'], ['#6a7388', '#2b2f3a', '#141210'], ['#c9b48e', '#2b2f3a', '#3b2f2a'], ['#f1f1f1', '#1f1f26', '#2b2320']]),
    student: add([['#f4f4f4', '#27365c', '#141210'], ['#f4f4f4', '#4a4e5a', '#1e1a18'], ['#27365c', '#4a4e5a', '#141210'], ['#9aa7c4', '#27365c', '#1e1a18'], ['#e8e2c8', '#5a3a3a', '#141210']]),
    hiker: add([['#e03a2e', '#1f1f26', '#141210'], ['#ff7a1a', '#2b2f3a', '#1e1a18'], ['#12a6a0', '#1f1f26', '#c9c9c9'], ['#c81e78', '#2b2f3a', '#141210'], ['#7ac51e', '#1f1f26', '#b8b8b8'], ['#2a6ae0', '#2b2f3a', '#2b2320']]),
    // 러너: 형광·검정 운동복 / 겨울용 긴 옷(어두운 색)
    runner: add([['#d7ff3a', '#1f1f26', '#141210'], ['#ff4fa3', '#1f1f26', '#1e1a18'], ['#19e0c8', '#2b2f3a', '#141210'], ['#1f1f26', '#1f1f26', '#2b2320'], ['#ff7a1a', '#1f1f26', '#141210'],
      ['#f4f4f4', '#2a6ae0', '#1e1a18'], ['#2b2f3a', '#c8ff3a', '#141210'], ['#7a5cff', '#1f1f26', '#3b2f2a'], ['#ff3b30', '#2b2f3a', '#141210'], ['#1f1f26', '#ff4fa3', '#1e1a18']]),
    runnerW: add([['#2b2f3a', '#1f1f26', '#141210'], ['#3a4a6a', '#1f1f26', '#1e1a18'], ['#5a2a3a', '#1f1f26', '#141210'], ['#1f1f26', '#1f1f26', '#2b2320'], ['#4a5a2a', '#1f1f26', '#141210']]),
    cleaner: add([['#c8e03a', '#4a5a2a', '#1e1a18'], ['#c8e03a', '#3d3d48', '#141210']]),
    staff: add([['#3f6a5a', '#2b2f3a', '#141210'], ['#3f6a5a', '#3d3d48', '#1e1a18']]),
    guide: add([['#ffd23f', '#3b4a66', '#3b2f2a'], ['#ff7a3d', '#2b2f3a', '#1e1a18']]),
    busker: add([['#2f2f38', '#6b7a99', '#3b2f2a']]),
  };
  cast.sitters = [...cast.normal, ...cast.elder];   // 앉은 자세를 굽는 팔레트
  cast.kneelers = cast.normal.slice(0, 4);
  Object.defineProperty(scene, '_cast', { value: cast, enumerable: false });
  return cast;
}

// 장면 데이터 보정(scene.json 은 해시로 고정이라 여기서 고친다). 근거 = OSM 담(barrier=wall)과 겹치는 점(자산 점검 기록의 후속 2).
// standing: 담 중심선에서 0.45 m 안(담 속)에 선 사람 → 원래 있던 쪽으로 담에서 1.2 m. cut: 문(OSM gate)에서 26 m 넘게 떨어진 곳에서 담을 뚫고 지나는 경로 → 그 점 1 m 앞에서 끊고 긴 쪽만 걷는다.
// 그림(자산)과 무관한 장면 번호 기준이라 자산을 다시 구워도 그대로 맞는다.
const SCENE_FIX = { standing: { 8: [-25.75, 593.74], 94: [-40.40, 501.53] }, cut: { 487: [97.7, 509.4], 576: [46.2, 510.0] } };
function cutPath(pts, c) {
  let bk = 0, bt = 0, bd = Infinity;
  for (let k = 0; k < pts.length - 1; k++) {
    const a = pts[k], b = pts[k + 1], dx = b[0] - a[0], dy = b[1] - a[1], t = Math.max(0, Math.min(1, ((c[0] - a[0]) * dx + (c[1] - a[1]) * dy) / (dx * dx + dy * dy || 1)));
    const d = Math.hypot(a[0] + dx * t - c[0], a[1] + dy * t - c[1]);
    if (d < bd) { bd = d; bk = k; bt = t; }
  }
  const a = pts[bk], b = pts[bk + 1], sl = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
  const at = (u) => { const t = Math.max(0, Math.min(1, u)); return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, (a[2] || 0) + ((b[2] || 0) - (a[2] || 0)) * t]; };
  const head = [...pts.slice(0, bk + 1), at(bt - 1 / sl)], tail = [at(bt + 1 / sl), ...pts.slice(bk + 1)];
  const len = (p) => p.reduce((sum, q, i) => (i ? sum + Math.hypot(q[0] - p[i - 1][0], q[1] - p[i - 1][1]) : 0), 0);
  return len(head) >= len(tail) ? head : tail;
}

// grid = { w, h, cls } (지도 px, 0.5 m). opts: { seed, birds(새 시스템, 아이·비둘기 장면용), heightAt(px, py) → 지면(z=0) 대비 높이 m(브라우저에서만) }
export function createPeople(scene, grid, opts = {}) {
  const seed = opts.seed ?? 5;
  const cast = addCast(scene);
  const proj = opts.proj || makeProjection(scene.camera);
  // profile: 'palace'(경복궁: 궁궐 의식·관람 시간·한복) | 'city'(여의도: 공원·한강·업무지구, 자전거). 장소는 둘 다 classes.png 와 시드로 고른다.
  const city = opts.profile === 'city';
  const { ex, ey, m } = proj;
  const det = ex[0] * ey[1] - ex[1] * ey[0];
  const S = [0, 0, 0], P3 = [0, 0, 0], Q3 = [0, 0, 0], Q2 = [0, 0];
  const toWorld = (px, py, out) => {
    const a = (px - proj.W / 2) * m + proj.cx, b = (proj.H / 2 - py) * m + proj.cy;
    out[0] = (a * ey[1] - b * ex[1]) / det; out[1] = (b * ex[0] - a * ey[0]) / det;
    return out;
  };
  const R0 = { rs: (seed * 9973 + 17) | 0 }, R1 = { rs: (seed * 7919 + 101) | 0 };
  let RR = R0;                                   // 배치 단계는 R0, 실행 단계는 R1
  const rnd = () => nextRand(RR), rr = (a, b) => a + (b - a) * rnd(), ri = (n) => Math.floor(rnd() * n), pick = (arr) => arr[ri(arr.length)];
  // 겉모습(emotes.js fig 가 읽는다). fam: a 어른(팔레트 번호), hf·hm 한복, hk 어린이 한복, k 어린이, g 수문장, dog·cat·wheel·stroller. h = 차림(우산·외투 등)을 고르는 고정 난수.
  const LK = (fam, pal, h, o) => ({ fam, pal, hat: 0, bag: 0, cane: 0, h, ...o });
  const LA = (pal, o) => LK('a', pal, rnd(), o);
  const LH = () => (rnd() < 0.72 ? LK('hf', ri(14), rnd()) : LK('hm', ri(6), rnd()));
  const LKid = () => LK('k', ri(8), rnd());
  const LG = (k) => LK('g', k, rnd());
  const isHanbok = (L) => L.fam === 'hf' || L.fam === 'hm' || L.fam === 'hk';

  // ── 걸을 수 있는 곳(1 m 칸). 칸 안의 지도 px 넷이 모두 같은 종류이고(브라우저에선) 평평해야 한다.
  // 높은 단(광화문 월대·전각 앞 월대처럼 넓고 평평한 포장면, 지면 위 0.3~2.6 m)도 걷는 곳으로 받는다. hz = 그 칸에 선 사람의 높이(m, 지면 0).
  // sim 좌표는 그대로 '화면 픽셀과 맞는 지면(z=0) 점'이고, 단 위 사람은 같은 픽셀에 그 면의 깊이로 그린다(UX·UY, emotes.js).
  // 단 가장자리(이웃 칸과 높이 차가 큰 곳)는 걷는 곳에서 빠지므로, 오르내림은 완만하게 이어진 곳(계단·경사)으로만 된다 — okLine 이 높이가 튀는 선을 막는다.
  // 걷는 칸 1 m = 지도 px 2×2(0.5 m/px 지도) 또는 1(1 m/px 지도). SH = 지도 px → 칸 자리 옮김 수.
  const SH = proj.m < 0.75 ? 1 : 0;
  const mw = grid.w >> SH, mh = grid.h >> SH, walk = new Uint8Array(mw * mh), hz = new Float32Array(mw * mh), hr = new Float32Array(mw * mh);
  // 단 높이 범위(m), 이웃 1 m 칸 사이 높이 차 한도(m), 평지로 칠 높이(m). 여의도 깊이 맵은 1 m 칸 최솟값이고 지면을 펴지 않아 평지도 ±0.6 m 흔들린다.
  const PLAT = [0.3, 2.6], SLOPE = city ? 0.8 : 0.3, FLAT = city ? 1.0 : 0.3;
  let platCells = 0;
  {
    const { w, cls } = grid, hAt = opts.heightAt;
    const kind = (c) => (c === 5 || c === 11 ? BIT.PAVE : c === 3 ? BIT.GRASS : c === 1 ? BIT.DIRT : 0);
    const cand = new Uint8Array(mw * mh), gh = [];
    for (let cy = 4; cy < mh - 4; cy++) for (let cx = 4; cx < mw - 4; cx++) {
      const o = (cy << SH) * w + (cx << SH), i = cy * mw + cx;
      const k = kind(cls[o]);
      if (!k || (SH && (kind(cls[o + 1]) !== k || kind(cls[o + w]) !== k || kind(cls[o + w + 1]) !== k))) continue;
      if (hAt) {
        const h0 = hAt(cx << SH, cy << SH), h1 = SH ? hAt(cx * 2 + 1, cy * 2 + 1) : h0;
        hr[i] = (h0 + h1) / 2;
        if (Math.abs(h0) > FLAT || Math.abs(h1) > FLAT) {
          if (!city && k === BIT.PAVE && h0 > PLAT[0] && h0 < PLAT[1] && h1 > PLAT[0] && h1 < PLAT[1] && Math.abs(h0 - h1) < 0.15) cand[i] = 1;
          continue;
        }
        if ((cx & 7) === 0 && (cy & 7) === 0) gh.push(hr[i]);
        // 도시 지도: 굽기에서 땅(잔디·광장)이 z 0 보다 0.3~0.6 m 높다 → 선 사람을 그 면 깊이로(같은 픽셀) 그려 발이 땅에 묻히지 않게
        if (city) hz[i] = Math.max(0, Math.min(1, hr[i]));
      }
      walk[i] = k;
    }
    // 단 칸: 둘레 8칸이 모두 걷는 곳(지면 또는 단 후보)이고 높이가 완만하게 이어져야 한다(가장자리·난간 옆은 빠진다)
    if (hAt && !city) {
      gh.sort((a, b) => a - b);
      const g0 = gh.length ? gh[gh.length >> 1] : 0;   // 지면이 깊이 맵에서 보이는 높이(칸 최솟값 깊이의 치우침)
      for (let cy = 5; cy < mh - 5; cy++) for (let cx = 5; cx < mw - 5; cx++) {
        const i = cy * mw + cx;
        if (!cand[i]) continue;
        let ok = true;
        for (let j = -1; j <= 1 && ok; j++) for (let k = -1; k <= 1; k++) { const n = i + j * mw + k; if (!(walk[n] || cand[n]) || Math.abs(hr[n] - hr[i]) > SLOPE) { ok = false; break; } }
        if (!ok) continue;
        walk[i] = BIT.PAVE; hz[i] = Math.max(0, hr[i] - g0); platCells++;
      }
    }
  }
  const cellAt = (x, y) => { proj.project(x, y, 0, S); const cx = S[0] >> SH, cy = S[1] >> SH; return cx < 0 || cy < 0 || cx >= mw || cy >= mh ? 0 : walk[cy * mw + cx]; };
  // 그 자리에 선 사람의 높이(m). 단 칸이 아니면 0. 걷는 곳 높이(hr)는 높이가 튀는지 볼 때 쓴다.
  //   도시 지도에서 걷는 칸이 아닌 자리(자전거·러너가 옆으로 비켜 지나가는 곳)는 둘레 ±2 칸 걷는 칸 높이 가운데 큰 값
  const zAt = (x, y) => {
    proj.project(x, y, 0, S); const cx = S[0] >> SH, cy = S[1] >> SH;
    if (cx < 2 || cy < 2 || cx >= mw - 2 || cy >= mh - 2) return 0;
    const i = cy * mw + cx;
    if (!city || walk[i]) return hz[i];
    let z = 0; for (let j = -2; j <= 2; j++) for (let k = -2; k <= 2; k++) { const o = i + j * mw + k; if (walk[o] && hz[o] > z) z = hz[o]; }
    return z;
  };
  const hrAt = (x, y) => { proj.project(x, y, 0, S); const cx = S[0] >> SH, cy = S[1] >> SH; return cx < 0 || cy < 0 || cx >= mw || cy >= mh ? 0 : hr[cy * mw + cx]; };
  const UX = proj.vd[0] / proj.vd[2], UY = proj.vd[1] / proj.vd[2];   // (x,y,0) 과 같은 픽셀에 보이는 높이 1 m 점까지의 수평 이동
  const clsAt = (x, y) => { proj.project(x, y, 0, S); const px = Math.floor(S[0]), py = Math.floor(S[1]); return px < 0 || py < 0 || px >= grid.w || py >= grid.h ? 0 : grid.cls[py * grid.w + px]; };
  // 발 픽셀이 건물·나무에 가려진 자리(말풍선을 띄우지 않는다)
  const hidden = (x, y) => { const c = clsAt(x, y); return c === 6 || c === 7 || c === 8 || c === 9 || c === 10; };
  // 설 수 있는 자리: 주변 3×3 칸(±1 m)이 모두 허용 종류
  const okPoint = (x, y, bits = BIT.PAVE) => {
    proj.project(x, y, 0, S);
    const cx = S[0] >> SH, cy = S[1] >> SH;
    if (cx < 1 || cy < 1 || cx >= mw - 1 || cy >= mh - 1) return false;
    for (let j = -1; j <= 1; j++) for (let i = -1; i <= 1; i++) if (!(walk[(cy + j) * mw + cx + i] & bits)) return false;
    return true;
  };
  const okLine = (x0, y0, x1, y1, bits = BIT.PAVE) => {
    const n = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0) / 0.4));
    let hp = hrAt(x0, y0);
    for (let k = 0; k <= n; k++) {
      const x = x0 + (x1 - x0) * k / n, y = y0 + (y1 - y0) * k / n;
      if (!(cellAt(x, y) & bits)) return false;
      const h = hrAt(x, y); if (Math.abs(h - hp) > SLOPE + 0.05) return false; hp = h;   // 단 가장자리를 뛰어넘지 않는다
    }
    return true;
  };
  const okDisk = (x, y, r, bits = BIT.PAVE) => {
    if (!okPoint(x, y, bits)) return false;
    for (let q = r; q > 0.5; q -= 1.5) for (let a = 0; a < 12; a++) if (!(cellAt(x + Math.cos(a * TAU / 12) * q, y + Math.sin(a * TAU / 12) * q) & bits)) return false;
    return true;
  };

  // ── 자리 예약(멈춰 서는 자리끼리 겹치지 않게). 2 m 칸 해시.
  const slotMap = new Map();
  const skey = (x, y) => (Math.floor(x / 2) + 4096) * 8192 + Math.floor(y / 2) + 4096;
  const claim = (x, y) => { const k = skey(x, y); let a = slotMap.get(k); if (!a) slotMap.set(k, a = []); a.push(x, y); };
  const free = (x, y, r = 1.0) => {
    for (let j = -1; j <= 1; j++) for (let i = -1; i <= 1; i++) {
      const a = slotMap.get(skey(x + i * 2, y + j * 2));
      if (a) for (let k = 0; k < a.length; k += 2) if (Math.hypot(a[k] - x, a[k + 1] - y) < r) return false;
    }
    return true;
  };
  const tryPt = (x, y, bits = BIT.PAVE) => okPoint(x, y, bits) && free(x, y);
  const freeLine = (x0, y0, x1, y1, r = 1.1) => {
    const n = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0) / 0.7));
    for (let k = 0; k <= n; k++) if (!free(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n, r)) return false;
    return true;
  };
  // 한 묶음의 점이 서로 gap(m) 이상 떨어져 있고 모두 설 수 있으면 통과
  // 한 묶음은 같은 높이(단 위끼리, 또는 지면끼리)에 선다
  const groupOk = (pts, bits = BIT.PAVE, gap = 1.0) => { const z0 = pts.length ? zAt(pts[0][0], pts[0][1]) : 0; return pts.every((p, i) => tryPt(p[0], p[1], bits) && Math.abs(zAt(p[0], p[1]) - z0) < 0.35 && pts.every((q, j) => j <= i || Math.hypot(p[0] - q[0], p[1] - q[1]) >= gap)); };
  const anchor = (px, py) => toWorld(px, py, [0, 0]);
  // 도시 지도: 장면 데이터의 랜드마크(지면 자리, 지도 px) → 로컬 m
  function cityAnchors() { const o = {}; for (const [k, p] of Object.entries(scene.anchors_ground || scene.anchors || {})) o[k] = anchor(p[0], p[1]); return o; }
  // 좌표는 tour.js PLACES 의 지도 px(건물 가운데쯤). 실제 자리는 이 둘레에서 클래스 맵으로 찾는다.
  const A = city ? cityAnchors() : { gate: anchor(850, 1225), geun: anchor(1215, 985), gyeong: anchor(1275, 800), hyang: anchor(1830, 650), seochon: anchor(640, 520), bukchon: anchor(2250, 980), sejong: anchor(330, 1230) };
  const PALACE = city ? null : [-258.6, 12.2, 297.3, 878.1];   // 궁궐 담 안쪽을 덮는 상자(로컬 m, main.js env.palace 와 같은 값). 도시 지도는 없음.
  const inBox = (x, y) => !!PALACE && x >= PALACE[0] && x <= PALACE[2] && y >= PALACE[1] && y <= PALACE[3];
  const inPalace = (x, y) => { if (!PALACE || x < PALACE[0] || x > PALACE[2] || y < PALACE[1] || y > PALACE[3]) return false; const c = clsAt(x, y); return c === 5 || c === 8 || c === 9; };

  // ── 도시 지도(여의도) 지형: 큰 물(한강·샛강)까지 거리, 강변 띠(달리기·자전거 길), 차로 옆 보도. classes.png·깊이·차로에서 고른다(좌표를 손으로 찍지 않는다).
  let dW = null, DG = 2, dgw = 0, dgh = 0;   // 거리 격자: 걷는 칸 DG×DG 하나에 한 값(m, 400 에서 자름)
  const dWater = (x, y) => { if (!dW) return 1e9; proj.project(x, y, 0, S); const gx = (S[0] >> SH) >> 1, gy = (S[1] >> SH) >> 1; return gx < 0 || gy < 0 || gx >= dgw || gy >= dgh ? 1e9 : dW[gy * dgw + gx]; };
  const AW = [];   // 사람을 두지 않는 곳(밤섬): [x, y, r]
  let isleN = 0, isle = null;   // 밤섬(물로 둘러싸인 땅): 거리 격자 칸마다 1
  const banned = (x, y) => {
    if (isle) { proj.project(x, y, 0, S); const gx = (S[0] >> SH) >> 1, gy = (S[1] >> SH) >> 1; if (gx >= 0 && gy >= 0 && gx < dgw && gy < dgh && isle[gy * dgw + gx]) return true; }
    return AW.some((b) => Math.hypot(x - b[0], y - b[1]) < b[2]);
  };
  const ANY = BIT.PAVE | BIT.GRASS | BIT.DIRT;
  // 강변 달리기 띠(물에서 6~11 m), 자전거 띠(13~19 m), 산책 띠(21~32 m, 걷는 사람만), 차로 옆 보도: [{ pts, cum, L }]
  const cityRun = [], cityBike = [], citySide = [], cityProm = [];
  if (city) {
    // 1) 큰 물: 물 칸(4) 덩어리 가운데 2만 칸(약 7 ha)이 넘는 것. 연못·분수·수영장은 빠진다.
    const { w, cls } = grid;
    dgw = mw >> 1; dgh = mh >> 1;
    const N = dgw * dgh, wet = new Uint8Array(N), comp = new Int32Array(N).fill(-1), st = new Int32Array(N), sizes = [];
    for (let gy = 0; gy < dgh; gy++) for (let gx = 0; gx < dgw; gx++) if (cls[((gy * DG) << SH) * w + ((gx * DG) << SH)] === 4) wet[gy * dgw + gx] = 1;
    for (let i = 0; i < N; i++) {
      if (!wet[i] || comp[i] >= 0) continue;
      let sp = 0, cnt = 0; st[sp++] = i; comp[i] = sizes.length;
      while (sp) {
        const j = st[--sp], x = j % dgw; cnt++;
        for (const n of [x > 0 ? j - 1 : -1, x < dgw - 1 ? j + 1 : -1, j - dgw, j + dgw]) if (n >= 0 && n < N && wet[n] && comp[n] < 0) { comp[n] = sizes.length; st[sp++] = n; }
      }
      sizes.push(cnt);
    }
    // 2) 거리 변환(체임퍼, 지면 m): 가로 한 칸 = DG·m, 세로 한 칸 = DG·m / |ey 지면 성분|
    const a = DG * (1 << SH) * proj.m, b = a / Math.hypot(ey[0], ey[1]), c = Math.hypot(a, b);
    dW = new Float32Array(N);
    for (let i = 0; i < N; i++) dW[i] = wet[i] && sizes[comp[i]] * DG * DG > 20000 ? 0 : 1e9;
    for (let y = 0; y < dgh; y++) for (let x = 0; x < dgw; x++) {
      const i = y * dgw + x; let v = dW[i];
      if (x > 0) v = Math.min(v, dW[i - 1] + a);
      if (y > 0) { v = Math.min(v, dW[i - dgw] + b); if (x > 0) v = Math.min(v, dW[i - dgw - 1] + c); if (x < dgw - 1) v = Math.min(v, dW[i - dgw + 1] + c); }
      dW[i] = v;
    }
    for (let y = dgh - 1; y >= 0; y--) for (let x = dgw - 1; x >= 0; x--) {
      const i = y * dgw + x; let v = dW[i];
      if (x < dgw - 1) v = Math.min(v, dW[i + 1] + a);
      if (y < dgh - 1) { v = Math.min(v, dW[i + dgw] + b); if (x < dgw - 1) v = Math.min(v, dW[i + dgw + 1] + c); if (x > 0) v = Math.min(v, dW[i + dgw - 1] + c); }
      dW[i] = Math.min(400, v);
    }
    // 밤섬: 땅(물 4 도, 높은 다리 상판 — 높이 3 m 넘는 차도 2 — 도 아닌 칸)의 덩어리 가운데 격자의 1/10 보다 작고 앵커에서 900 m 안에 닿는 것 모두(두 섬).
    if (A.bamseom) {
      const hA = opts.heightAt || (() => 0);
      const land = new Uint8Array(N);
      for (let j = 0; j < N; j++) { const x = (j % dgw) * DG << SH, y = Math.floor(j / dgw) * DG << SH, c2 = cls[y * w + x]; land[j] = c2 !== 4 && !(c2 === 2 && hA(x, y) > 3) ? 1 : 0; }
      proj.project(A.bamseom[0], A.bamseom[1], 0, S);
      const ax = (S[0] >> SH) >> 1, ay = (S[1] >> SH) >> 1, seen = new Uint8Array(N), mark = new Uint8Array(N);
      for (let i = 0; i < N; i++) {
        if (!land[i] || seen[i]) continue;
        let sp = 0, cnt = 0, near = false; const mem = [];
        st[sp++] = i; seen[i] = 1;
        while (sp) {
          const j = st[--sp], x = j % dgw, y = (j - x) / dgw; cnt++; if (cnt <= N / 10) mem.push(j);
          if (!near && Math.hypot((x - ax) * a, (y - ay) * b) < 900) near = true;
          for (const n of [x > 0 ? j - 1 : -1, x < dgw - 1 ? j + 1 : -1, j - dgw, j + dgw]) if (n >= 0 && n < N && land[n] && !seen[n]) { seen[n] = 1; st[sp++] = n; }
        }
        if (near && cnt <= N / 10) { for (const j of mem) mark[j] = 1; isleN += cnt; }
      }
      if (isleN) isle = mark; else AW.push([A.bamseom[0], A.bamseom[1], 430]);
    }
    // 3) 강변 띠: 물에서 d0~d1 m 떨어진 걷는 칸을 점으로 모아, 앞으로 이어지는 가까운 점을 차례로 잇는다(욕심쟁이).
    //    다리 밑(높은 상판에 가린 곳)·가로수 수관(10)은 지나가도 된다(그려질 때 깊이로 가려진다). 지면 차도(2)는 12 m 까지만 건넌다.
    const hAt = opts.heightAt || (() => 0);
    const passLine = (p, q) => {
      const n = Math.max(1, Math.ceil(Math.hypot(q[0] - p[0], q[1] - p[1]) / 0.5)), st2 = Math.hypot(q[0] - p[0], q[1] - p[1]) / n;
      let off = 0, road = 0;
      for (let k = 0; k <= n; k++) {
        const x = p[0] + (q[0] - p[0]) * k / n, y = p[1] + (q[1] - p[1]) * k / n;
        if (banned(x, y)) return false;
        if (cellAt(x, y) & ANY) continue;
        const cc = clsAt(x, y);
        if (cc === 4) return false;
        proj.project(x, y, 0, S);
        const hh = hAt(Math.min(grid.w - 1, Math.max(0, Math.floor(S[0]))), Math.min(grid.h - 1, Math.max(0, Math.floor(S[1]))));
        if (cc === 10 || hh > 3) off += st2;
        else if (cc === 2) { road += st2; off += st2; }
        else return false;
        if (off > 40 || road > 12) return false;
      }
      return true;
    };
    const chains = (d0, d1, minL, out) => {
      const pts = [];
      for (let gy = 2; gy < dgh - 2; gy++) for (let gx = 2; gx < dgw - 2; gx++) {
        const d = dW[gy * dgw + gx];
        if (d < d0 || d > d1) continue;
        const cx = gx * DG + 1, cy = gy * DG + 1;
        if (!(walk[cy * mw + cx] & ANY)) continue;
        const p = toWorld((cx << SH) + 0.5 * (1 << SH), (cy << SH) + 0.5 * (1 << SH), [0, 0]);
        if (!banned(p[0], p[1])) pts.push(p);
      }
      const used = new Uint8Array(pts.length), hsh = new Map(), HK = (x, y) => (Math.floor(x / 8) + 8192) * 16384 + Math.floor(y / 8) + 8192;
      pts.forEach((p, i) => { const k = HK(p[0], p[1]); let l = hsh.get(k); if (!l) hsh.set(k, l = []); l.push(i); });
      const around = (p, r, fn) => { const k0 = Math.floor(p[0] / 8), k1 = Math.floor(p[1] / 8), R = Math.ceil(r / 8); for (let j = -R; j <= R; j++) for (let i = -R; i <= R; i++) { const l = hsh.get((k0 + i + 8192) * 16384 + k1 + j + 8192); if (l) for (const q of l) fn(q); } };
      const thin = (p) => around(p, 4, (q) => { if (!used[q] && Math.hypot(pts[q][0] - p[0], pts[q][1] - p[1]) < 4.2) used[q] = 1; });
      const extend = (i0, hx, hy) => {
        const line = []; let cur = pts[i0];
        for (let guard = 0; guard < 5000; guard++) {
          let best = -1, bs = 1e9;
          for (const [r, far] of [[11, false], [46, true]]) {
            around(cur, r, (q) => {
              if (used[q]) return;
              const dx = pts[q][0] - cur[0], dy = pts[q][1] - cur[1], d = Math.hypot(dx, dy);
              if (d < 1 || d > r) return;
              const dot = hx || hy ? (dx * hx + dy * hy) / d : 1;
              if (dot < (far ? 0.6 : -0.1)) return;
              const sc = d - 3 * dot;
              if (sc < bs && (far ? passLine(cur, pts[q]) : okLine(cur[0], cur[1], pts[q][0], pts[q][1], ANY))) { bs = sc; best = q; }
            });
            if (best >= 0) break;
          }
          if (best < 0) break;
          const q = pts[best], d = Math.hypot(q[0] - cur[0], q[1] - cur[1]);
          const nx = (q[0] - cur[0]) / d, ny = (q[1] - cur[1]) / d;
          hx = hx || hy ? hx * 0.5 + nx * 0.5 : nx; hy = hx || hy ? hy * 0.5 + ny * 0.5 : ny;
          const hl = Math.hypot(hx, hy) || 1; hx /= hl; hy /= hl;
          used[best] = 1; thin(q); line.push(q); cur = q;
        }
        return line;
      };
      for (let i = 0; i < pts.length; i++) {
        if (used[i]) continue;
        used[i] = 1; thin(pts[i]);
        const fw = extend(i, 0, 0);
        let hx = 0, hy = 0;
        if (fw.length) { hx = pts[i][0] - fw[0][0]; hy = pts[i][1] - fw[0][1]; const l = Math.hypot(hx, hy) || 1; hx /= l; hy /= l; }
        const bw = fw.length ? extend(i, hx, hy) : [];
        const line = [...bw.reverse(), pts[i], ...fw].map((p) => [p[0], p[1], 0]);
        // 펴기: 이웃과 평균 낸 자리가 걷는 칸이고 양옆이 이어질 때만
        for (let pass = 0; pass < 3; pass++) for (let k = 1; k < line.length - 1; k++) {
          const p0 = line[k - 1], p1 = line[k], p2 = line[k + 1], m2 = [(p0[0] + 2 * p1[0] + p2[0]) / 4, (p0[1] + 2 * p1[1] + p2[1]) / 4, 0];
          if (cellAt(m2[0], m2[1]) & ANY && passLine(p0, m2) && passLine(m2, p2)) line[k] = m2;
        }
        const cum = cumLengths(line), L = cum[cum.length - 1];
        if (L >= minL) out.push({ pts: line, cum, L });
      }
    };
    chains(6, 11, 150, cityRun);
    chains(13, 19, 250, cityBike);
    chains(21, 32, 150, cityProm);
    // 4) 차로 옆 보도: 일반 도로(간선·보조·국지, 지면) 차로의 오른쪽으로 차도가 끝나는 곳을 찾아 1.5 m 안쪽(보도·광장 11, 맨땅 1)
    for (const ln of scene.lanes) {
      const hw = String(ln.highway || '');
      if (!/^(primary|secondary|tertiary)$/.test(hw) || ln.pts.some((p) => (p[2] || 0) > 1)) continue;
      const cum = cumLengths(ln.pts), L = cum[cum.length - 1];
      let cur = [];
      const flush = () => { if (cur.length >= 2) { const c2 = cumLengths(cur); if (c2[c2.length - 1] >= 40) citySide.push({ pts: cur, cum: c2, L: c2[c2.length - 1] }); } cur = []; };
      for (let d = 2; d <= L - 2; d += 5) {
        pointAt(ln.pts, cum, d, P3); const px = P3[0], py = P3[1];
        pointAt(ln.pts, cum, Math.min(L, d + 2), Q3);
        let tx = Q3[0] - px, ty = Q3[1] - py; const tl = Math.hypot(tx, ty) || 1; tx /= tl; ty /= tl;
        const nx = ty, ny = -tx;   // 진행 방향의 오른쪽(x 동, y 북)
        let hit = null, q = 1.5, past = 0;
        for (; q < 34; q += 0.5) {
          const c2 = clsAt(px + nx * q, py + ny * q);
          if (c2 === 2 && !past) continue;
          if (c2 === 10 || c2 === 2) { past += 0.5; if (past > 6) break; continue; }
          if ((c2 === 11 || c2 === 1) && (cellAt(px + nx * (q + 1.5), py + ny * (q + 1.5)) & (BIT.PAVE | BIT.DIRT))) hit = [px + nx * (q + 1.5), py + ny * (q + 1.5), 0];
          break;
        }
        if (hit && cur.length && !okLine(cur[cur.length - 1][0], cur[cur.length - 1][1], hit[0], hit[1], BIT.PAVE | BIT.DIRT | BIT.GRASS)) flush();
        if (hit) cur.push(hit); else flush();
      }
      flush();
    }
  }
  // 도시 지도의 동네: k 공원(잔디·숲), r 강변, b 업무지구 보도, a 국회 앞, s 그 밖의 거리
  const BIZ = ['parc1', 'parc2', 'ifc', 'conrad', 'hyundai', 'lg', 'fki', 'krx'].filter((k) => A[k]).map((k) => A[k]);
  const PARKS = [['park', 360], ['park_plaza', 160], ['saetgang_park', 420]].filter(([k]) => A[k]).map(([k, r]) => [A[k][0], A[k][1], r]);
  const zoneOf = (pts, cum, L, side) => {
    let g = 0, n = 0, dw = 0, bz = 1e9, as = 1e9, pk = 0;
    for (let k = 0; k <= 8; k++) {
      pointAt(pts, cum, L * k / 8, P3); n++;
      const c2 = clsAt(P3[0], P3[1]); if (c2 === 3 || c2 === 10) g++;
      dw += Math.min(400, dWater(P3[0], P3[1]));
      for (const q of BIZ) bz = Math.min(bz, Math.hypot(P3[0] - q[0], P3[1] - q[1]));
      if (A.assembly) as = Math.min(as, Math.hypot(P3[0] - A.assembly[0], P3[1] - A.assembly[1]));
      if (PARKS.some((q) => Math.hypot(P3[0] - q[0], P3[1] - q[1]) < q[2])) pk++;
    }
    if (as < 260) return 'a';
    if (dw / n < 130) return 'r';
    if (pk >= 5 || (!side && g >= 5)) return 'k';
    if (bz < 480) return 'b';
    return 's';
  };

  // ── 걷는 사람: 경로를 왕복(닫힌 식: 위상 + 시간 × 속도 − 누적 정지 시간). 유형·동행은 번호 해시와 경로 위치로 정한다(고정).
  const walkers = [];
  const mkWalker = (i, w, cum, L, zone, type, pal0, speed) => {
    const h2 = hash01(i * 23 + 7), h3 = hash01(i * 29 + 13), h4 = hash01(i * 31 + 3);
    const pk = (arr, h) => arr[Math.floor(h * arr.length)];
    const hat = (p) => (h3 < p ? 1 + Math.floor(h4 * 8) : 0), bag = (p) => (fr(h3 * 7) < p ? 1 + Math.floor(h4 * 4) : 0);
    const hb = () => (h2 < 0.72 ? LK('hf', Math.floor(h3 * 14), h4) : LK('hm', Math.floor(h3 * 6), h4));
    let look = LK('a', pal0, h4);
    const fol = [];
    const F = (dd, lk) => fol.push({ dd, ox: 0, oy: 0, look: lk, hop: 0, bub: 0 });
    if (type === T.HANBOK) { look = hb(); if (fr(h2 * 9) < 0.4) F(-1.0, fr(h2 * 31) < 0.7 ? LK('hf', Math.floor(fr(h3 * 17) * 14), fr(h4 * 3)) : LK('hm', Math.floor(fr(h3 * 17) * 6), fr(h4 * 3))); }
    else if (type === T.OFFICE) look = city ? LK('a', pk(cast.office, h2), h4, { cup: fr(h3 * 5) < 0.4 ? 1 : 0, bag: fr(h3 * 11) < 0.15 ? 4 : 0 }) : LK('a', pk(cast.office, h2), h4);
    else if (type === T.STUDENT) { look = LK('a', pk(cast.student, h2), h4, { bag: bag(0.6) }); if (h3 < 0.5) for (let k = 1; k <= 1 + Math.floor(h4 * 3); k++) F(-0.95 * k, LK('a', pk(cast.student, fr(h2 * (k + 3))), fr(h4 * (k + 2)), { bag: k & 1 ? 1 + (k % 4) : 0 })); }
    else if (type === T.ELDER) look = LK('a', pk(cast.elder, h2), h4, { cane: h3 < 0.6 ? 1 : 0, hat: h3 > 0.8 ? 6 : 0 });
    else if (type === T.TOURIST) { look = LK('a', pal0, h4, { hat: hat(0.6), bag: bag(0.45) }); if (fr(h2 * 9) < (city ? 0.45 : 0.25)) F(-1.0, LK('a', pk(cast.normal, fr(h2 * 5)), fr(h4 * 5), { hat: fr(h3 * 3) < 0.5 ? 1 + Math.floor(fr(h4 * 9) * 8) : 0 })); }
    else if (type === T.HIKER) look = LK('a', pk(cast.hiker, h2), h4, { hat: 1 + Math.floor(h3 * 8), bag: 1 + Math.floor(h4 * 4), cane: h3 < 0.35 ? 1 : 0 });
    else if (type === T.CLEANER) look = LK('a', pk(cast.cleaner, h2), h4, { hat: 1 + Math.floor(h3 * 5), cane: 2, uniform: true, noUmb: true });
    else if (type === T.STAFF) look = LK('a', pk(cast.staff, h2), h4, { hat: 4, uniform: true });
    else if (type === T.PARENT) {
      // 아이는 보호자 바로 뒤(같은 경로)를 따라 걷는다
      if (zone === 'p' && h2 < 0.3) { look = hb(); F(-0.9, LK('hk', Math.floor(h3 * 4), h4)); } else F(-0.9, LK('k', Math.floor(h3 * 8), h4));
    } else if (type === T.STROLLER) F(0.95, LK('stroller', Math.floor(h3 * 3), h4));
    else if (type === T.WHEEL) F(1.0, LK('wheel', Math.floor(h3 * 3), h4));
    else if (type === T.DOG) F(h2 < 0.6 ? 1.15 : -1.1, LK('dog', Math.floor(h3 * 4), h4));
    else if (type === T.JOGGER) look = LK('a', pk(cast.hiker, h2), h4, { noUmb: true });
    const a = w.pts[0], b = w.pts[w.pts.length - 1];
    walkers.push({ pts: w.pts, cum, L, speed: speed * (0.85 + 0.3 * hash01(i * 7 + 1)) * SPEED[type], phase: hash01(i * 13 + 5) * 2 * L, pal: look.pal, night: hash01(i * 3 + 11),
      type, zone, look, fol, vis: true, key: hash01(i * 37 + 9), run: type === T.JOGGER, bub: 0, sx: (b[0] - a[0]) * ex[0] + (b[1] - a[1]) * ex[1] >= 0 ? 1 : -1, dir: 1 });
  };
  const cum2 = (h1, list) => { let a = 0; for (const [p, t] of list) { a += p; if (h1 < a) return t; } return T.NORMAL; };
  if (!city) scene.walkers.forEach((w0, i) => {
    const w = SCENE_FIX.cut[i] ? { ...w0, pts: cutPath(w0.pts, SCENE_FIX.cut[i]) } : w0;
    const cum = cumLengths(w.pts), L = cum[cum.length - 1];
    if (!(L > 1)) return;
    const h1 = hash01(i * 19 + 2);
    let nPal = 0;
    for (let k = 0; k <= 4; k++) { pointAt(w.pts, cum, L * k / 4, P3); if (inPalace(P3[0], P3[1])) nPal++; }
    pointAt(w.pts, cum, L / 2, P3);
    const mx = P3[0], my = P3[1], zone = nPal >= 3 ? 'p' : 's';
    const dTo = (a) => Math.hypot(mx - a[0], my - a[1]);
    const near = Math.min(dTo(A.gate), dTo(A.seochon), dTo(A.bukchon)) < 230, biz = dTo(A.sejong) < 320;
    const type = zone === 'p'
      ? cum2(h1, [[HANBOK.palace, T.HANBOK], [0.30, T.TOURIST], [0.09, T.PARENT], [0.05, T.ELDER], [0.03, T.STUDENT], [0.02, T.STROLLER], [0.02, T.WHEEL], [0.02, T.STAFF]])
      : cum2(h1, [[near ? HANBOK.near : HANBOK.city, T.HANBOK], [biz ? 0.3 : 0.15, T.OFFICE], [0.07, T.STUDENT], [0.08, T.ELDER], [near ? 0.14 : 0.06, T.TOURIST], [0.04, T.HIKER], [0.06, T.DOG], [0.05, T.PARENT], [0.02, T.STROLLER], [0.012, T.WHEEL], [0.015, T.CLEANER], [0.025, T.JOGGER]]);
    mkWalker(i, w, cum, L, zone, type, scene.walker_pal_idx[i], w.speed_mps);
  });
  else {
    // 도시: 보행로(map.json walk_paths, 걷는 사람끼리 같은 경로를 나눠 쓴다) + 차로 옆 보도 + 강변 띠. 동네마다 100 m 당 사람 수를 정한다.
    const paths = [], seen = new Set();
    for (const w of scene.walkers) if (!seen.has(w.pts)) { seen.add(w.pts); paths.push({ pts: w.pts, side: false }); }
    for (const c of citySide) paths.push({ pts: c.pts, side: true });
    for (const c of cityRun) paths.push({ pts: c.pts, side: false, river: true });
    for (const c of cityProm) paths.push({ pts: c.pts, side: false, river: true });
    const DENS = { k: 9, r: 8, b: 7, a: 3, s: 2.4 };
    const MIX = {
      k: [[0.30, T.NORMAL], [0.12, T.ELDER], [0.12, T.PARENT], [0.05, T.STROLLER], [0.13, T.DOG], [0.07, T.JOGGER], [0.01, T.WHEEL], [0.06, T.OFFICE], [0.05, T.STUDENT], [0.08, T.TOURIST]],
      r: [[0.28, T.NORMAL], [0.08, T.ELDER], [0.09, T.PARENT], [0.04, T.STROLLER], [0.15, T.DOG], [0.14, T.JOGGER], [0.01, T.WHEEL], [0.04, T.STUDENT], [0.15, T.TOURIST]],
      b: [[0.24, T.NORMAL], [0.56, T.OFFICE], [0.03, T.STUDENT], [0.04, T.ELDER], [0.04, T.TOURIST], [0.03, T.DOG], [0.02, T.PARENT], [0.01, T.STROLLER], [0.015, T.CLEANER], [0.015, T.JOGGER]],
      a: [[0.25, T.NORMAL], [0.4, T.TOURIST], [0.25, T.OFFICE], [0.05, T.ELDER], [0.05, T.STUDENT]],
      s: [[0.45, T.NORMAL], [0.16, T.OFFICE], [0.1, T.ELDER], [0.08, T.STUDENT], [0.06, T.DOG], [0.06, T.PARENT], [0.02, T.STROLLER], [0.02, T.CLEANER], [0.03, T.JOGGER], [0.02, T.TOURIST]],
    };
    // 같은 경로를 여럿이 한 줄로 걷지 않게: 경로를 옆으로 비낀 평행 경로(차로 옆 보도 ±0.7 m, 그 밖 ±1.6 m, 5 줄)를 만들어 나눠 준다.
    //   비낀 점이 걷는 칸이 아니면 원래 점을 쓴다.
    const offset = (pts, o) => pts.map((p, i) => {
      const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
      let tx = b[0] - a[0], ty = b[1] - a[1]; const tl = Math.hypot(tx, ty) || 1; tx /= tl; ty /= tl;
      const x = p[0] + ty * o, y = p[1] - tx * o;
      return cellAt(x, y) & ANY && !banned(x, y) ? [x, y, p[2] || 0] : p;
    });
    let id = 0;
    for (const p of paths) {
      const cum = cumLengths(p.pts), L = cum[cum.length - 1];
      if (!(L > 1)) continue;
      pointAt(p.pts, cum, L / 2, P3);
      if (banned(P3[0], P3[1])) continue;
      const zone = p.river ? 'r' : zoneOf(p.pts, cum, L, p.side);
      const n = Math.min(80, Math.max(1, Math.round(L / 100 * DENS[zone])));
      const lanes = [], wid = p.side ? 0.7 : 1.6;
      for (let k = 0; k < n; k++, id++) {
        const li = Math.floor(hash01(id * 89 + 7) * 5);
        if (!lanes[li]) { const pts = li === 2 ? p.pts : offset(p.pts, (li - 2) / 2 * wid), c2 = cumLengths(pts); lanes[li] = { pts, cum: c2, L: c2[c2.length - 1] }; }
        const ln = lanes[li];
        mkWalker(id, ln, ln.cum, ln.L, zone, cum2(hash01(id * 19 + 2), MIX[zone]), cast.normal[Math.floor(hash01(id * 97 + 13) * cast.normal.length)], 1.15 + 0.3 * hash01(id * 31 + 5));
      }
    }
  }
  const nW = walkers.length;
  const ov = { skip: new Uint8Array(nW), off: new Float64Array(nW), skipS: new Uint8Array(scene.standing.length) };
  const cool = new Float32Array(nW);
  // 위치(out)와 걸은 거리(걸음 프레임용)를 돌려준다. dd = 같은 경로 위의 앞(+)·뒤(−) 간격(동행). 접기 전에 더하므로 반환점에서도 이어진다.
  const wpos = (i, t, out, dd = 0) => {
    const w = walkers[i], raw = w.phase + (t - ov.off[i]) * w.speed + dd;
    let d = raw % (2 * w.L);
    if (d < 0) d += 2 * w.L;
    w.dir = d > w.L ? -1 : 1;
    if (d > w.L) d = 2 * w.L - d;
    pointAt(w.pts, w.cum, d, out);
    return raw;
  };
  // 서 있는 사람(장면 데이터): 자리를 예약해 두고, 차도 위에 놓인 사람은 그리지 않게 한다(장면 데이터의 흠)
  const standing = scene.standing.map((s0, i) => {
    const s = SCENE_FIX.standing[i] ? { ...s0, x: SCENE_FIX.standing[i][0], y: SCENE_FIX.standing[i][1] } : s0;
    const h1 = hash01(i * 41 + 5), h2 = hash01(i * 43 + 1), h3 = hash01(i * 47 + 9), pal = inPalace(s.x, s.y);
    const bad = clsAt(s.x, s.y) === 2;
    if (bad) ov.skipS[i] = 1; else claim(s.x, s.y);
    const look = pal && h1 < HANBOK.palace ? (h2 < 0.72 ? LK('hf', Math.floor(h3 * 14), h2) : LK('hm', Math.floor(h3 * 6), h2))
      : LK('a', s.pal, h2, h1 < 0.6 ? { hat: h3 < 0.5 ? 1 + Math.floor(h2 * 8) : 0, bag: h3 > 0.7 ? 1 + Math.floor(h2 * 4) : 0 } : {});
    return { x: s.x, y: s.y, z: s.z || 0, zp: zAt(s.x, s.y), look, pose: 'stand', face: h3 < 0.5 ? 1 : -1, bub: 0, vis: !bad, bad, zone: pal ? 'p' : 's', night: hash01(i * 5 + 3), key: h1, tourist: look.fam === 'a' && h1 < 0.6 };
  });

  // 마주칠 수 있는 쌍: 경로끼리 1.3 m 안으로 지나가는 곳이 있는 두 사람. 시작할 때 한 번만 센다.
  const pairs = [];
  {
    const bb = walkers.map((w) => { let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9; for (const p of w.pts) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]); } return [x0, x1, y0, y1]; });
    const segD = (px, py, a, b) => { const dx = b[0] - a[0], dy = b[1] - a[1], t = Math.max(0, Math.min(1, ((px - a[0]) * dx + (py - a[1]) * dy) / (dx * dx + dy * dy || 1))); return Math.hypot(px - a[0] - dx * t, py - a[1] - dy * t); };
    const order = walkers.map((_, i) => i).sort((a, b) => bb[a][0] - bb[b][0]);
    // 판정(경로 i 의 0.6 m 간격 점 가운데 하나가 경로 j 의 선분에서 1.3 m 안)은 경로 쌍마다 한 번만 한다: 같은 경로를 여럿이 나눠 걷는 도시 지도에서 빠르게.
    // 선분은 1.3 m 부풀린 상자가 걸치는 4 m 칸마다 적어 두고, 점은 제 칸의 선분만 본다(결과는 모든 선분을 보는 것과 같다).
    const pathId = new Map(), pathOf = walkers.map((w) => { let id = pathId.get(w.pts); if (id === undefined) pathId.set(w.pts, id = pathId.size); return id; });
    const byPath = []; walkers.forEach((w, i) => { byPath[pathOf[i]] ??= w; });
    const GS = 4, gk = (cx, cy) => (cx + 32768) * 65536 + cy + 32768, segGrid = new Map();
    byPath.forEach((w, p) => {
      for (let k = 1; k < w.pts.length; k++) {
        const a = w.pts[k - 1], b = w.pts[k];
        for (let cy = Math.floor((Math.min(a[1], b[1]) - 1.3) / GS); cy <= Math.floor((Math.max(a[1], b[1]) + 1.3) / GS); cy++)
          for (let cx = Math.floor((Math.min(a[0], b[0]) - 1.3) / GS); cx <= Math.floor((Math.max(a[0], b[0]) + 1.3) / GS); cx++) { const key = gk(cx, cy); let l = segGrid.get(key); if (!l) segGrid.set(key, l = []); l.push(p, k); }
      }
    });
    const nearCache = new Map();
    const nearOf = (p) => {
      let set = nearCache.get(p);
      if (set) return set;
      set = new Set(); nearCache.set(p, set);
      const w = byPath[p];
      for (let d = 0; d <= w.L; d += 0.6) {
        pointAt(w.pts, w.cum, d, P3);
        const l = segGrid.get(gk(Math.floor(P3[0] / GS), Math.floor(P3[1] / GS)));
        if (l) for (let k = 0; k < l.length; k += 2) { const q = l[k]; if (set.has(q)) continue; const pts = byPath[q].pts; if (segD(P3[0], P3[1], pts[l[k + 1] - 1], pts[l[k + 1]]) < 1.3) set.add(q); }
      }
      return set;
    };
    for (let oi = 0; oi < nW; oi++) {
      const i = order[oi], A2 = bb[i];
      for (let oj = oi + 1; oj < nW; oj++) {
        const j = order[oj], B = bb[j];
        if (B[0] > A2[1] + 1.3) break;
        if (B[2] > A2[3] + 1.3 || B[3] < A2[2] - 1.3) continue;
        if (nearOf(pathOf[i]).has(pathOf[j])) pairs.push(Math.min(i, j), Math.max(i, j));
      }
    }
  }

  // ── 출연진
  const actors = [], guests = [], scenes = [], props = [], fx = [], floaters = [];
  const stats = { chat: 0, ask: 0, askphoto: 0, dogmeet: 0, kiddog: 0, tap: 0, photo: 0, nightphoto: 0, classphoto: 0, guide: 0, hanbok: 0, couple: 0, share: 0, pigeon: 0, picnic: 0, bench: 0, jog: 0, ceremony: 0, snow: 0, cat: 0, busk: 0, proposal: 0, kite: 0, soap: 0, lawn: 0, ball: 0, fish: 0, splash: 0, lunch: 0, friends: 0 };
  // look = 겉모습(LK). pose: stand·wave·cam·cheer·point·sit·kneel·run. prop: flag·banner·spear·guitar.
  const mk = (x, y, look, o = {}) => {
    const a = { id: actors.length, x, y, z: 0, ox: x, oy: y, hx: x, hy: y, look, pose: 'stand', prop: null, bubble: 0, bT: 0, hopT: 0, waveT: 0, on: true,
      mayHide: false, path: null, pi: 0, wait: 0, speed: 1.2, dist: 0, moving: false, face: 1, wi: -1, ...o };
    a.zo = o.z || 0; lift(a);
    actors.push(a);
    return a;
  };
  // 선 자리의 높이(단 위면 그 면 높이). zp = 단 높이(그릴 때 같은 픽셀로 옮기는 몫), z = zp + 앉은 높이 등
  const lift = (a) => { a.zp = zAt(a.x, a.y); a.z = a.zo + a.zp; };
  const say = (a, icon, dur = 1.8) => { a.bubble = icon; a.bT = dur; };
  const hop = (a, dur = 1) => { a.hopT = dur; };
  const go = (a, pts, speed, delay = 0) => { a.path = pts; a.pi = 0; a.speed = speed; a.wait = delay; };
  const idle = (a) => !a.path && a.wait <= 0;
  const flash = (a) => { const zp = a.zp || 0; fx.push({ type: 'flash', x: a.x + zp * UX, y: a.y + zp * UY, z: 1.55 + zp, t: 0, T: 0.16 }); };
  const stepActor = (a, dt) => {
    a.ox = a.x; a.oy = a.y; a.moving = false;
    if (a.bT > 0 && (a.bT -= dt) <= 0) a.bubble = 0;
    if (a.hopT > 0) a.hopT -= dt;
    if (a.waveT > 0) a.waveT -= dt;
    if (a.wait > 0) { a.wait -= dt; return; }
    if (!a.path) return;
    let rem = a.speed * dt;
    while (rem > 0 && a.pi < a.path.length) {
      const t = a.path[a.pi], dx = t[0] - a.x, dy = t[1] - a.y, d = Math.hypot(dx, dy);
      if (d <= rem) { a.x = t[0]; a.y = t[1]; rem -= d; a.dist += d; a.pi++; } else { a.x += dx / d * rem; a.y += dy / d * rem; a.dist += rem; rem = 0; }
    }
    a.moving = a.x !== a.ox || a.y !== a.oy;
    if (a.moving && a.zo !== undefined) lift(a);
    if (a.moving) { const sx = (a.x - a.ox) * ex[0] + (a.y - a.oy) * ex[1]; if (Math.abs(sx) > 1e-4) a.face = sx > 0 ? 1 : -1; }
    if (a.pi >= a.path.length) a.path = null;
  };
  const polar = (c, r0, r1) => { const a = rnd() * TAU, r = Math.sqrt(rr(r0 * r0, r1 * r1)); return [c[0] + Math.cos(a) * r, c[1] + Math.sin(a) * r]; };
  const randomPt = () => toWorld(8 + rnd() * (grid.w - 16), 8 + rnd() * (grid.h - 16), [0, 0]);
  const palNormal = () => LA(pick(cast.normal));
  const E = { tod: 12, day: 1, keep: 1, season: 1, rain: false, view: null, rate: 0, prevTod: null };   // rate = 시뮬레이션 1초에 흐르는 시각(시). 멈춰 두면 0, 자동 흐름은 0.16
  // 장면을 켜고 끄는 것은 화면 밖이거나(또는 사람이 2~3 px 로 보일 만큼 멀리서 볼 때)만 한다 → 시야 안에서 생기거나 사라지지 않는다
  const inView = (px, py, pad = 24) => { const v = E.view; return !!v && v[2] - v[0] <= 1100 && px > v[0] - pad && px < v[2] + pad && py > v[1] - pad && py < v[3] + pad + 16; };
  const canFlip = (sc) => {
    const v = E.view;
    if (!v || v[2] - v[0] > 1100) return true;
    for (const a of sc.actors) { proj.project(a.x, a.y, 0, S); if (S[0] > v[0] - 24 && S[0] < v[2] + 24 && S[1] > v[1] - 24 && S[1] < v[3] + 40) return false; }
    return true;
  };
  const addScene = (kind, c, sc) => {
    proj.project(c[0], c[1], 0, S);
    Object.assign(sc, { kind, x: c[0], y: c[1], px: S[0], py: S[1], on: true, t: 0, st: 'idle', nightKey: sc.pin ? 0 : rnd(),
      inPal: kind !== 'ceremony' && inBox(c[0], c[1]) });
    scenes.push(sc);
    return sc;
  };
  // 궁 안 장면은 관람 시간(9~18시)에만. 수문장 교대(pin)는 제 시각 규칙을 따른다.
  const palOpen = () => E.tod >= PAL_OPEN[0] && E.tod < PAL_OPEN[1];
  const wants = (sc) => sc.want() && (!sc.inPal || palOpen());
  const setOn = (sc, on) => {
    sc.on = on;
    for (const a of sc.actors) {
      a.on = on; a.x = a.ox = a.hx; a.y = a.oy = a.hy; a.path = null; a.wait = 0; a.bubble = 0; a.bT = 0; a.hopT = 0; a.pose = a.pose0 || 'stand'; lift(a);
    }
    sc.t = 0; sc.st = 'idle'; sc.reset?.();
  };

  // ── 수문장 교대 의식(광화문 안마당). 맨 먼저 자리를 잡는다.
  const mkCeremony = () => {
    // 의식 자리 C: 광화문에서 가장 가까운, 사방 9 m 가 트인 마당. 격자로 훑는다.
    let C = null, best = 1e9;
    for (let dy = -90; dy <= 90; dy += 3) for (let dx = -90; dx <= 90; dx += 3) {
      const x = A.gate[0] + dx, y = A.gate[1] + dy, d = Math.hypot(dx, dy);
      if (d < 18 || d >= best || clsAt(x, y) !== 5 || !okDisk(x, y, 9)) continue;
      C = [x, y]; best = d;
    }
    if (!C) return;
    // 숨는 자리 H: C 에서 곧게 가면 궁궐 지붕·벽(가려진 곳)으로 들어가는 방향 중 광화문 쪽에 가장 가까운 것
    // 돌려주는 값: [마당이 끝나는 거리, 그 뒤로 가려진 곳(궁궐 지붕·벽)이 이어지는 끝 거리]. 없으면 null.
    const ray = (ang, ox, oy) => {
      const c = Math.cos(ang), s = Math.sin(ang);
      for (let t = 0; t < 70; t += 0.4) {
        const x = C[0] + ox + c * t, y = C[1] + oy + s * t;
        if (cellAt(x, y) & BIT.PAVE) continue;
        let u = 0;
        for (; u <= 9; u += 0.4) { const k = clsAt(x + c * u, y + s * u); if (k !== 8 && k !== 9 && !(u < 1.2 && k === 5)) break; }
        return u < 3 ? null : [t, t + u - 0.4];
      }
      return null;
    };
    // 대열 간격 [옆, 앞뒤, 늘어선 줄]: 넓은 것부터 시도해 자리가 나오는 첫 간격을 쓴다(사람끼리 겹쳐 보이지 않게)
    let cols, H, dir, d, l, at, colC, colH, row, form = null, okForm = false;
    for (const [LAT, GAP, ROW] of [[0.95, 1.7, 1.9], [0.85, 1.5, 1.6], [0.7, 1.3, 1.3]]) {
    cols = [[0, 0]];   // 우두머리 + 두 줄 넷씩(행진 방향 d, 옆 방향 l 은 아래에서 정한다)
    H = null; dir = null;
    let bestH = 1e9;
    for (let k = 0; k < 96; k++) {
      const ang = k * TAU / 96, c = Math.cos(ang), s = Math.sin(ang);
      // 가운데와 두 줄(옆으로 ±0.7 m) 모두 같은 거리에서 숨을 수 있어야 한다
      const rays = [[0, 0], [-s * LAT, c * LAT], [s * LAT, -c * LAT]].map(([ox, oy]) => ray(ang, ox, oy));
      if (rays.some((r) => !r)) continue;
      const t = Math.max(...rays.map((r) => r[0])) + 1.8;
      if (t < 12 || t > Math.min(...rays.map((r) => r[1]))) continue;
      const hx = C[0] + c * t, hy = C[1] + s * t, dG = Math.hypot(hx - A.gate[0], hy - A.gate[1]);
      // 가까운 숨는 자리를 고른다(행진이 길면 의식이 늘어진다). 광화문 쪽이면 조금 더 쳐준다.
      const score = t + dG * 0.15;
      if (score < bestH) { bestH = score; H = [hx, hy]; dir = [-c, -s]; }
    }
    if (!H) continue;
    d = dir; l = [-d[1], d[0]];
    for (let r = 0; r < 4; r++) for (const sd of [-LAT, LAT]) cols.push([sd, -(r + 1) * GAP]);
    const D = d, L = l;
    at = (base, lat, along) => [base[0] + L[0] * lat + D[0] * along, base[1] + L[1] * lat + D[1] * along];
    colH = cols.map(([lat]) => at(H, lat, 0));   // 숨은 자리에서는 한 점에 포개 두고(보이지 않는다) 차례로 내보낸다
    // 의식 자리는 숨는 자리에서 16 m 넘게 떨어진 가장 가까운 곳(행진이 길면 의식이 늘어진다). 늘어선 줄은 옆으로 조금 밀어 보며 설 수 있는 자리를 찾는다.
    const far = Math.hypot(H[0] - C[0], H[1] - C[1]);
    let Cn = null;
    for (let tt = Math.min(16, far); tt <= far + 0.01 && !Cn; tt += 1.5) {
      const c0 = tt + 1.5 > far ? C : [H[0] + D[0] * tt, H[1] + D[1] * tt];
      if (!okDisk(c0[0], c0[1], 7)) continue;
      const cc = cols.map(([lat, al]) => at(c0, lat, al + 3));
      if (!groupOk(cc)) continue;
      for (const sh of [0, 1, -1, 2, -2, 3, -3]) {
        const rw = cols.map((_, k) => (k === 0 ? at(c0, sh, 5) : at(c0, (k - 4.5) * ROW + sh, 2.4)));
        if (groupOk(rw)) { Cn = c0; colC = cc; row = rw; break; }
      }
    }
    if (Cn) { C = Cn; okForm = true; form = [LAT, GAP, ROW]; break; }
    }
    if (!okForm) return;
    const guards = cols.map((_, k) => mk(colH[k][0], colH[k][1], LG(k === 0 ? 3 : (k - 1) % 3), { mayHide: true, prop: k === 0 ? 'banner' : 'spear', on: false }));
    for (const p of [...colC, ...row]) claim(p[0], p[1]);
    for (let t = 0; t < Math.hypot(H[0] - C[0], H[1] - C[1]); t += 1.2) for (const sd of [-0.7, 0.7]) { const p = at(C, sd, 3 - t); if (cellAt(p[0], p[1])) claim(p[0], p[1]); }
    // 구경꾼: 평소엔 마당 여기저기, 의식이 시작되면 둘레로 모인다
    const watchers = [];
    for (let k = 0, tries = 0; watchers.length < 8 && tries < 400; tries++) {
      const home = polar(C, 12, 30), ang = rnd() * TAU, slot = [C[0] + Math.cos(ang) * rr(8.5, 10.5), C[1] + Math.sin(ang) * rr(8.5, 10.5)];
      if (!tryPt(home[0], home[1]) || !tryPt(slot[0], slot[1]) || !okLine(home[0], home[1], slot[0], slot[1])) continue;
      // 행렬이 지나는 길 위에는 서지 않는다
      const al = (slot[0] - C[0]) * d[0] + (slot[1] - C[1]) * d[1], lat = Math.abs((slot[0] - C[0]) * l[0] + (slot[1] - C[1]) * l[1]);
      if (al < 0 && lat < 3) continue;
      claim(home[0], home[1]); claim(slot[0], slot[1]);
      watchers.push(mk(home[0], home[1], rnd() < 0.3 ? LH() : palNormal(), { slot, k: k++ }));
    }
    // 수문군 넷: 광화문 바깥쪽(C 반대편) 문 앞에 낮 동안 서 있다
    const sentries = [];
    {
      const cand = [];
      for (let dy = -40; dy <= 40; dy += 1.5) for (let dx = -40; dx <= 40; dx += 1.5) {
        const x = A.gate[0] + dx, y = A.gate[1] + dy;
        if ((x - A.gate[0]) * (C[0] - A.gate[0]) + (y - A.gate[1]) * (C[1] - A.gate[1]) < 0 && tryPt(x, y)) cand.push([Math.hypot(dx, dy), x, y]);
      }
      cand.sort((a, b) => a[0] - b[0]);
      for (const [, x, y] of cand) {
        if (sentries.length >= 4) break;
        if (sentries.every((s) => Math.hypot(s.x - x, s.y - y) >= 3)) { claim(x, y); sentries.push(mk(x, y, LG(sentries.length % 3), { prop: 'spear' })); }
      }
    }
    if (sentries.length) addScene('sentry', [sentries[0].x, sentries[0].y], { actors: sentries, want: () => E.day > 0.3, step() {} });
    const inWindow = () => E.day > 0.3 && CEREMONY_HOURS.some((h) => E.tod >= h && E.tod < h + CEREMONY_WINDOW);
    // 시각이 빨리 흐를 때(자동 흐름: 하루 150초 → 10시와 14시 사이가 25초)는 의식을 22초쯤으로 줄여 두 번 다 열리게 한다.
    // 그 사이 14시를 지나쳤으면 끝난 직후 바로 이어서 연다(due). 시각을 멈춰 두면 느긋한 원래 길이.
    let due = -1;
    const fast = () => E.rate > 0.02;
    const sc = addScene('ceremony', C, {
      pin: true, actors: [...guards, ...watchers], guards, watchers, C, H, form, len: Math.hypot(H[0] - C[0], H[1] - C[1]), quick: false, v: 1.25, cool: 0, lastStart: null, lastEnd: null,
      want: () => true,
      reset() { for (const g of guards) g.on = false; for (const w of watchers) w.on = palOpen(); },
      start() {
        sc.st = 'out'; sc.t = 0; stats.ceremony++; sc.lastStart = { time: sys.time, tod: E.tod }; sc.lastEnd = null;
        sc.quick = fast(); sc.v = sc.quick ? Math.max(2.4, sc.len / 5) : 1.25; due = -1;
        guards.forEach((g, k) => { g.on = true; g.x = g.ox = colH[k][0]; g.y = g.oy = colH[k][1]; lift(g); go(g, [colC[k]], sc.v, -cols[k][1] / sc.v); });
        // 돌아가던 길이면 그 자리에서 바로 되돌아온다(길 위에 멈춰 서지 않게)
        watchers.forEach((w) => { const d = rr(0.5, sc.quick ? 1.5 : 5); go(w, [w.slot], sc.quick ? 2.2 : 1.3, w.x === w.hx && w.y === w.hy ? d : 0); say(w, BUB.BANG, 1.5); });
      },
      step(dt) {
        sc.t += dt; sc.cool -= dt;
        const g0 = guards[0];
        // 구경꾼은 관람 시간에만 마당에 있다. 화면 밖에서(또는 멀리서 볼 때) 한 명씩 나오고 들어간다.
        if (sc.st === 'idle') for (const w of watchers) if (w.on !== palOpen()) { proj.project(w.x, w.y, 0, S); if (!inView(S[0], S[1])) w.on = !w.on; }
        if (E.prevTod !== null && E.day > 0.3) for (const h of CEREMONY_HOURS) if (E.prevTod < h && E.tod >= h) due = h;
        if (due >= 0 && (E.tod < due || E.tod >= due + 1.2)) due = -1;
        if (sc.st === 'idle') { if ((sc.cool <= 0 && inWindow()) || (due >= 0 && sc.cool <= 0)) sc.start(); return; }
        const dv = sc.quick ? 3.2 : 1.1, HOLD = sc.quick ? 6 : 16;
        if (sc.st === 'out' && guards.every(idle)) { sc.st = 'deploy'; sc.t = 0; guards.forEach((g, k) => go(g, [row[k]], dv, k * (sc.quick ? 0.05 : 0.15))); }
        else if (sc.st === 'deploy' && guards.every(idle)) { sc.st = 'hold'; sc.t = 0; sc.beat = 0; }
        else if (sc.st === 'hold') {
          if (sc.t >= sc.beat) {
            sc.beat += sc.quick ? 1.6 : 2.4; say(g0, BUB.NOTE, 1.4);
            const w = pick(watchers);
            if (w && idle(w)) { if (rnd() < 0.5) { w.pose = 'cam'; w.camT = 1.2; } else say(w, pick([BUB.SMILE, BUB.HEART, BUB.BANG]), 1.6); }
          }
          for (const w of watchers) if (w.camT > 0 && (w.camT -= dt) <= 0) { flash(w); w.pose = 'stand'; }
          if (sc.t >= HOLD) { sc.st = 'undeploy'; sc.t = 0; guards.forEach((g, k) => go(g, [colC[k]], dv, k * (sc.quick ? 0.05 : 0.15))); for (const w of watchers) { w.pose = 'stand'; w.camT = 0; } }
        } else if (sc.st === 'undeploy' && guards.every(idle)) { sc.st = 'back'; sc.t = 0; guards.forEach((g, k) => go(g, [colH[k]], sc.v)); watchers.forEach((w) => go(w, [[w.hx, w.hy]], 1.2, rr(1, 6))); }
        else if (sc.st === 'back' && guards.every(idle)) { sc.st = 'idle'; sc.cool = sc.quick ? 2 : 45; sc.lastEnd = { time: sys.time, tod: E.tod }; for (const g of guards) g.on = false; }
      },
    });
    return sc;
  };

  // ── 사진 찍기: 찍는 사람 하나, 찍히는 사람 1~3
  // out = 궁 밖(광화문 앞)에서만 자리를 잡는다 → 관람 시간이 끝난 밤에도 남는 야경 사진
  const mkPhoto = (c, r0, r1, pin, cls, out) => {
    for (let tries = 0; tries < 120; tries++) {
      const p = c ? polar(c, r0, r1) : randomPt(), ang = rnd() * TAU, u = [Math.cos(ang), Math.sin(ang)], v = [-u[1], u[0]], dist = rr(4, 5.6) + (cls ? 1.5 : 0), n = cls ? 6 : 1 + ri(3);
      const B = [p[0] + u[0] * dist, p[1] + u[1] * dist], Rv = [B[0] - u[0] * 1.25, B[1] - u[1] * 1.25];
      // 학생 단체 사진은 두 줄(앞줄 셋, 뒷줄 셋이 엇갈려 선다)
      const subs = Array.from({ length: n }, (_, k) => (cls ? [B[0] + v[0] * ((k % 3) - 1 + (k > 2 ? 0.5 : 0)) * 1.15 + u[0] * (k > 2 ? 1.1 : 0), B[1] + v[1] * ((k % 3) - 1 + (k > 2 ? 0.5 : 0)) * 1.15 + u[1] * (k > 2 ? 1.1 : 0)] : [B[0] + v[0] * (k - (n - 1) / 2) * 1.1, B[1] + v[1] * (k - (n - 1) / 2) * 1.1]));
      if (out && [p, B, ...subs].some((q) => inBox(q[0], q[1]))) continue;
      if (!groupOk([p, Rv, ...subs]) || !okLine(p[0], p[1], Rv[0], Rv[1])) continue;
      for (const q of [p, Rv, ...subs]) claim(q[0], q[1]);
      const hb = rnd() < 0.3;
      const ph = mk(p[0], p[1], cls ? LA(pick(cast.office)) : LA(pick(cast.normal), { hat: rnd() < 0.5 ? 1 + ri(8) : 0 })), ss = subs.map((q) => mk(q[0], q[1], cls ? LA(pick(cast.student), { bag: rnd() < 0.4 ? 1 + ri(4) : 0 }) : hb ? LH() : palNormal()));
      const sc = addScene(cls ? 'classphoto' : 'photo', B, {
        pin, actors: [ph, ...ss], T: rr(3, 20), shots: 0,
        want: () => (cls ? E.tod >= 9.5 && E.tod < 17 && !E.rain : sc.nightKey <= E.keep),
        reset() { sc.T = rr(3, 20); },
        nudge() { sc.T = Math.min(sc.T, sc.t + 0.4); },
        shoot() { sc.st = 'aim'; sc.t = 0; sc.shots = 1 + (rnd() < 0.4 ? 1 : 0); sc.posed = false; ph.pose = 'cam'; },
        step(dt) {
          sc.t += dt;
          if (sc.st === 'idle') { if (sc.t >= sc.T) sc.shoot(); }
          else if (sc.st === 'aim') {
            if (!sc.posed && sc.t > 0.6) { sc.posed = true; ss.forEach((s, k) => { s.pose = k % 2 ? 'wave' : 'cheer'; }); }
            if (sc.t >= 2) {
              flash(ph); stats[cls ? 'classphoto' : 'photo']++; if (!cls && E.day < 0.3) stats.nightphoto++;
              if (--sc.shots > 0) sc.t = 0.9;
              else { sc.st = 'look'; sc.t = 0; sc.said = false; ph.pose = 'stand'; for (const s of ss) s.pose = 'stand'; go(ph, [Rv], 1.2, 0.5); }
            }
          } else if (sc.st === 'look') {
            if (!sc.said && idle(ph)) { sc.said = true; sc.t = 0; say(ph, BUB.DOTS, 1.4); ss.forEach((s, k) => { s.wait = 0.6 + k * 0.3; say(s, pick([BUB.HEART, BUB.SMILE, BUB.BANG]), 2.2); }); }
            if (sc.said && sc.t > 2.8) { sc.st = 'back'; go(ph, [[ph.hx, ph.hy]], 1.2); }
          } else if (sc.st === 'back' && idle(ph)) { sc.st = 'idle'; sc.t = 0; sc.T = cls ? rr(40, 90) : rr(14, 40); }
        },
      });
      return sc;
    }
    return null;
  };

  // ── 무리(가이드와 관광객, 한복 일행): 미리 검사한 직선 구간을 왕복한다. offs = 무리 안에서의 고정 자리(회전하지 않는 묶음).
  const mkTroupe = (kind, c, r0, r1, members, o) => {
    const offs = members.map((mb) => mb.off), gap = o.gap || 1.0, TB = o.bits || BIT.PAVE;
    const shifted = (p) => offs.map((f) => [p[0] + f[0], p[1] + f[1]]);
    for (let tries = 0; tries < 60; tries++) {
      const p0 = polar(c, r0, r1);
      if (!groupOk(shifted(p0), TB, gap)) continue;
      const route = [p0];
      for (let leg = 0; leg < o.legs; leg++) {
        const p = route[route.length - 1];
        for (let t = 0; t < 50; t++) {
          const q = polar(p, o.minLeg, o.maxLeg);
          if (route.some((w, wi) => wi < route.length - 1 && Math.hypot(w[0] - q[0], w[1] - q[1]) < o.minLeg * 0.8)) continue;
          if (!groupOk(shifted(q), TB, gap) || !offs.every((f) => okLine(p[0] + f[0], p[1] + f[1], q[0] + f[0], q[1] + f[1], TB) && freeLine(p[0] + f[0], p[1] + f[1], q[0] + f[0], q[1] + f[1]))) continue;
          route.push(q); break;
        }
      }
      if (route.length < 3) continue;
      // 멈춰 서는 자리: 기본은 묶음 그대로. 가이드 무리는 가이드 둘레로 모여 든다(자리마다 미리 검사).
      const stand = route.map((w) => shifted(w));
      for (const row of stand) for (const q of row) claim(q[0], q[1]);
      if (o.gather) route.forEach((w, wi) => {
        const lead = stand[wi][0];
        for (let k = 1; k < members.length; k++) {
          const base = stand[wi][k];
          for (let t = 0; t < 30; t++) {
            const q = polar(lead, 1.5, 3.6);
            if (!tryPt(q[0], q[1]) || !okLine(base[0], base[1], q[0], q[1])) continue;
            claim(q[0], q[1]); stand[wi][k] = q; break;
          }
        }
      });
      const as = members.map((mb, k) => mk(stand[0][k][0], stand[0][k][1], mb.pal, { prop: mb.prop || null, pose0: mb.pose || 'stand', pose: mb.pose || 'stand' }));
      const sc = addScene(kind, route[0], {
        actors: as, route, wi: 0, dirn: 1, T: rr(2, 8), ev: 0,
        want: o.want ? () => o.want(sc) : () => sc.nightKey <= E.keep,
        reset() { sc.wi = 0; sc.dirn = 1; sc.T = rr(2, 8); },
        step(dt) {
          sc.t += dt;
          if (sc.st === 'idle') {
            o.stop?.(sc, as, dt);
            if (sc.t < sc.T) return;
            for (const a of as) { a.pose = a.pose0 || 'stand'; a.camT = 0; }
            const from = sc.wi;
            if (sc.wi + sc.dirn < 0 || sc.wi + sc.dirn >= route.length) sc.dirn = -sc.dirn;
            sc.wi += sc.dirn; sc.st = 'walk';
            as.forEach((a, k) => go(a, [[route[from][0] + offs[k][0], route[from][1] + offs[k][1]], [route[sc.wi][0] + offs[k][0], route[sc.wi][1] + offs[k][1]], stand[sc.wi][k]], o.speed, (members[k].lag || 0)));
          } else if (as.every(idle)) { sc.st = 'idle'; sc.t = 0; sc.T = rr(o.stopT[0], o.stopT[1]); sc.ev = 0; stats[kind]++; }
        },
      });
      return sc;
    }
    return null;
  };
  const guideStop = (sc, as, dt) => {
    // 가이드가 설명하고(…), 관광객은 감탄하거나 사진을 찍는다
    if (sc.t >= sc.ev) {
      sc.ev = sc.t + rr(1.6, 3);
      say(as[0], BUB.DOTS, 1.5);
      const a = as[1 + ri(as.length - 1)];
      if (idle(a) && a.pose === 'stand') { if (rnd() < 0.35) { a.pose = 'cam'; a.camT = 1.3; } else say(a, pick([BUB.BANG, BUB.SMILE, BUB.DOTS]), 1.5); }
    }
    for (const a of as) if (a.camT > 0 && (a.camT -= dt) <= 0) { flash(a); a.pose = 'stand'; }
  };
  const coupleStop = (sc, as) => {
    if (sc.ev === 0) { sc.ev = 1; if (E.rain) stats.share++; say(pick(as), pick([BUB.HEART, BUB.HEART, BUB.SMILE, BUB.NOTE]), 2.2); }
  };
  const hanbokStop = (sc, as) => {
    // 셀카(한 명이 팔을 들고 나머지는 만세) 또는 수다
    if (sc.ev === 0) { sc.ev = 1; sc.selfie = rnd() < 0.55; if (!sc.selfie) say(pick(as), pick([BUB.NOTE, BUB.SMILE, BUB.DOTS]), 2); }
    if (sc.selfie && sc.ev === 1 && sc.t > 0.8) { sc.ev = 2; as.forEach((a, k) => { a.pose = k === 0 ? 'wave' : 'cheer'; }); }
    if (sc.selfie && sc.ev === 2 && sc.t > 2.3) { sc.ev = 3; flash(as[0]); for (const a of as) a.pose = 'stand'; say(pick(as), BUB.HEART, 1.6); }
  };

  // ── 아이가 비둘기 떼로 달려가고 보호자가 뒤따른다(birds.scare 재사용)
  const mkPigeon = (f) => {
    const F = toWorld(f.x, f.y, [0, 0]);
    for (let tries = 0; tries < 60; tries++) {
      const ang = rnd() * TAU, u = [Math.cos(ang), Math.sin(ang)], v = [-u[1], u[0]], dist = rr(11, 16);
      const Hm = [F[0] + u[0] * dist, F[1] + u[1] * dist], Kp = [F[0] + u[0] * 3.4, F[1] + u[1] * 3.4];
      const Gh = [Hm[0] + v[0] * 1.15, Hm[1] + v[1] * 1.15], Gp = [Kp[0] + u[0] * 1.5 + v[0] * 0.9, Kp[1] + u[1] * 1.5 + v[1] * 0.9];
      if (!groupOk([Hm, Kp, Gh, Gp]) || !okLine(Hm[0], Hm[1], Kp[0], Kp[1]) || !okLine(Gh[0], Gh[1], Gp[0], Gp[1])) continue;
      for (const q of [Hm, Kp, Gh, Gp]) claim(q[0], q[1]);
      const kid = mk(Hm[0], Hm[1], LKid()), par = mk(Gh[0], Gh[1], palNormal());
      const sc = addScene('pigeon', Hm, {
        actors: [kid, par], T: rr(6, 40), flock: f,
        want: () => E.day > 0.5,
        reset() { sc.T = rr(6, 40); },
        nudge() { sc.T = Math.min(sc.T, sc.t + 0.4); },
        run() { sc.st = 'run'; sc.t = 0; sc.scared = false; sc.parSaid = false; stats.pigeon++; kid.pose = 'run'; go(kid, [Kp], 2.8); say(kid, BUB.BANG, 0.9); go(par, [Gp], 1.4, 0.9); },
        step(dt) {
          sc.t += dt;
          if (sc.st === 'idle') {
            if (sc.t < sc.T) return;
            if (f.state === 'ground' && f.cool <= 0 && !E.rain) sc.run(); else sc.T = sc.t + 3;
          } else if (sc.st === 'run') {
            if (!sc.scared && Math.hypot(kid.x - F[0], kid.y - F[1]) < 6.5) { sc.scared = true; opts.birds?.scare(f.x, f.y, 3); }
            if (idle(kid)) { sc.st = 'cheer'; sc.t = 0; kid.pose = 'cheer'; hop(kid, 2.6); say(kid, BUB.NOTE, 2.2); }
          } else if (sc.st === 'cheer') {
            if (!sc.parSaid && sc.t > 1.2 && idle(par)) { sc.parSaid = true; say(par, pick([BUB.SMILE, BUB.DOTS]), 1.8); }
            if (sc.t > 3.6 && idle(par)) { sc.st = 'home'; kid.pose = 'stand'; go(kid, [Hm], 1.15); go(par, [Gh], 1.15, 0.3); }
          } else if (sc.st === 'home' && idle(kid) && idle(par)) { sc.st = 'idle'; sc.t = 0; sc.T = rr(30, 75); }
        },
      });
      return sc;
    }
    return null;
  };

  // ── 잔디 소풍(봄·가을 낮): 돗자리 + 앉은 사람 2~3
  // where(점) = 도시 지도에서 자리 조건(강변·공원 잔디), want = 나오는 조건(없으면 봄·가을 맑은 낮)
  const mkPicnic = (where, want) => {
    for (let tries = 0; tries < 4000; tries++) {
      const c = randomPt();
      if (where && !where(c)) continue;
      if (!okDisk(c[0], c[1], 2.5, BIT.GRASS) || !free(c[0], c[1], 2)) continue;
      const n = 2 + ri(2), pts = [[c[0] - 0.75, c[1]], [c[0] + 0.75, c[1] + 0.1], [c[0], c[1] + 1.1]].slice(0, n);
      if (!groupOk(pts, BIT.GRASS)) continue;
      for (const q of pts) claim(q[0], q[1]);
      const as = pts.map((q) => mk(q[0], q[1], palNormal(), { pose: 'sit', pose0: 'sit' }));
      const sc = addScene('picnic', c, {
        actors: as, T: rr(2, 9),
        want: want ? () => want(sc) : () => (E.season === 0 || E.season === 2) && E.day > 0.5 && !E.rain,
        step(dt) { sc.t += dt; if (sc.t >= sc.T) { sc.t = 0; sc.T = rr(5, 13); stats.picnic++; say(pick(as), pick([BUB.NOTE, BUB.SMILE, BUB.DOTS, BUB.HEART]), 2); } },
      });
      props.push({ type: 'mat', x: c[0], y: c[1] + 0.35, variant: ri(3), sc });
      return sc;
    }
    return null;
  };

  // ── 달리는 사람: 광장·보행로의 긴 직선 구간을 왕복
  const mkJogger = () => {
    for (let tries = 0; tries < 300; tries++) {
      const p0 = randomPt();
      if (clsAt(p0[0], p0[1]) !== 11 || !okPoint(p0[0], p0[1])) continue;
      const route = [p0];
      for (let leg = 0; leg < 4; leg++) {
        const p = route[route.length - 1];
        for (let t = 0; t < 40; t++) {
          const q = polar(p, 22, 70);
          if (route.some((w, wi) => wi < route.length - 1 && Math.hypot(w[0] - q[0], w[1] - q[1]) < 20)) continue;
          if (!okPoint(q[0], q[1]) || !okLine(p[0], p[1], q[0], q[1]) || !freeLine(p[0], p[1], q[0], q[1])) continue;
          route.push(q); break;
        }
      }
      if (route.length < 3) continue;
      const a = mk(p0[0], p0[1], palNormal(), { pose: 'run', pose0: 'run' });
      const sc = addScene('jog', p0, {
        actors: [a], route, wi: 0, dirn: 1,
        want: () => E.day > 0.3 && !E.rain && E.season !== 3 && sc.nightKey <= E.keep,
        reset() { sc.wi = 0; sc.dirn = 1; },
        step() {
          if (!idle(a)) return;
          if (sc.wi + sc.dirn < 0 || sc.wi + sc.dirn >= route.length) { sc.dirn = -sc.dirn; stats.jog++; }
          sc.wi += sc.dirn; go(a, [route[sc.wi]], 2.7);
        },
      });
      return sc;
    }
    return null;
  };

  // ── 겨울: 눈사람 옆의 아이 둘(눈싸움)과 보호자
  const mkSnow = (c, r0, r1, bits = BIT.PAVE) => {
    for (let tries = 0; tries < 200; tries++) {
      const p = c ? polar(c, r0, r1) : randomPt(), ang = rnd() * TAU, u = [Math.cos(ang), Math.sin(ang)], v = [-u[1], u[0]];
      const k1 = [p[0] + u[0] * 2.4, p[1] + u[1] * 2.4], k2 = [p[0] - u[0] * 2.4, p[1] - u[1] * 2.4], g = [p[0] + v[0] * 2.6, p[1] + v[1] * 2.6];
      if (!groupOk([p, k1, k2, g], bits) || !okLine(k1[0], k1[1], k2[0], k2[1], bits)) continue;
      for (const q of [p, k1, k2, g]) claim(q[0], q[1]);
      const kids = [mk(k1[0], k1[1], LKid()), mk(k2[0], k2[1], LKid())], par = mk(g[0], g[1], palNormal());
      const sc = addScene('snow', p, {
        actors: [...kids, par], T: rr(1, 4), turn: 0,
        nudge() { sc.T = Math.min(sc.T, sc.t + 0.4); },
        want: () => E.season === 3 && E.day > 0.3 && !E.rain,
        step(dt) {
          sc.t += dt;
          if (sc.hit > 0 && (sc.hit -= dt) <= 0) { const b = kids[1 - sc.turn]; hop(b, 0.8); say(b, pick([BUB.BANG, BUB.SMILE]), 1.2); kids[sc.turn].pose = 'stand'; }
          if (sc.t < sc.T) return;
          sc.t = 0; sc.T = rr(2.4, 5); sc.turn = 1 - sc.turn; stats.snow++;
          const a = kids[sc.turn], b = kids[1 - sc.turn];
          a.pose = 'cheer'; sc.hit = 0.8;
          fx.push({ type: 'ball', x: a.x, y: a.y, x1: b.x, y1: b.y, z: 1.0, t: 0, T: 0.8 });
          if (rnd() < 0.3) say(par, BUB.SMILE, 1.5);
        },
      });
      props.push({ type: 'snowman', x: p[0], y: p[1], variant: 0, sc });
      return sc;
    }
    return null;
  };

  // ── 숨은 장면
  // 고양이: 골목 맨땅·보행로의 짧은 구간을 오가다 앉아 쉰다
  const mkCat = (c) => {
    const bits = BIT.PAVE | BIT.DIRT;
    for (let tries = 0; tries < 400; tries++) {
      const p = polar(c, 5, 110), q = polar(p, 5, 12);
      if (!tryPt(p[0], p[1], bits) || !tryPt(q[0], q[1], bits) || !okLine(p[0], p[1], q[0], q[1], bits)) continue;
      claim(p[0], p[1]); claim(q[0], q[1]);
      const a = mk(p[0], p[1], LK('cat', ri(3), 0), { pose: 'sit', pose0: 'sit' });
      const sc = addScene('cat', p, {
        pin: true, actors: [a], T: rr(3, 12), end: 0,
        want: () => true,
        step(dt) {
          sc.t += dt;
          if (sc.st === 'idle' && sc.t >= sc.T) { sc.st = 'walk'; sc.end = 1 - sc.end; a.pose = 'stand'; go(a, [sc.end ? q : p], 0.9); }
          else if (sc.st === 'walk' && idle(a)) { sc.st = 'idle'; sc.t = 0; sc.T = rr(6, 18); a.pose = 'sit'; stats.cat++; }
        },
      });
      return sc;
    }
    return null;
  };
  // 거리 음악가: 넓은 광장에서 기타를 친다. 연주가 시작되면 근처를 거닐던 사람들이 둘러서고, 끝나면 흩어진다(낮~밤).
  const mkBusker = (c0) => {
    for (let tries = 0; tries < 3000; tries++) {
      const c = c0 ? polar(c0, 4, tries < 1500 ? 70 : 160) : tries < 1500 ? polar([A.gate[0], PALACE[1] - 30], 4, 90) : randomPt();
      if (inBox(c[0], c[1]) || clsAt(c[0], c[1]) !== 11 || !okDisk(c[0], c[1], tries < 1500 ? 4 : 6) || !free(c[0], c[1], 2)) continue;   // 궁 밖 보행로에서만(먼저 광화문 앞)
      if (!freeLine(c[0] - 4, c[1], c[0] + 4, c[1], 1.5) || !freeLine(c[0], c[1] - 4, c[0], c[1] + 4, 1.5)) continue;
      const b = mk(c[0], c[1], LA(cast.busker[0], { hat: 4, noUmb: true }), { prop: 'guitar' });
      claim(c[0], c[1]);
      const aud = [], a0 = rnd() * TAU;
      for (let k = 0, t = 0; aud.length < 7 && t < 200; t++) {
        const ang = a0 + (k - 3) * 0.42 + rr(-0.08, 0.08), r = rr(3.6, 4.8), q = [c[0] + Math.cos(ang) * r, c[1] + Math.sin(ang) * r], home = polar(c, 8, 17);
        if (!tryPt(q[0], q[1]) || !tryPt(home[0], home[1]) || !okLine(home[0], home[1], q[0], q[1]) || Math.hypot(home[0] - q[0], home[1] - q[1]) < 3) continue;
        claim(q[0], q[1]); claim(home[0], home[1]); k++;
        aud.push(mk(home[0], home[1], rnd() < 0.2 ? LA(pick(cast.elder)) : rnd() < 0.2 ? LKid() : palNormal(), { slot: q }));
      }
      const sc = addScene('busk', c, {
        pin: true, actors: [b, ...aud], T: rr(4, 12), ev: 0,
        want: () => E.tod >= 11 && E.tod < 22.5 && !E.rain,
        reset() { sc.T = rr(4, 12); },
        play() { sc.st = 'play'; sc.t = 0; sc.T = rr(40, 70); sc.ev = 1; stats.busk++; aud.forEach((a) => go(a, [a.slot], 1.25, rr(0.5, 9))); },
        step(dt) {
          sc.t += dt;
          if (sc.st === 'idle') { if (sc.t >= sc.T) sc.play(); return; }
          if (sc.t >= sc.T) { sc.st = 'idle'; sc.t = 0; sc.T = rr(25, 50); aud.forEach((a) => { a.pose = 'stand'; go(a, [[a.hx, a.hy]], 1.15, rr(0.3, 5)); }); return; }
          if (sc.t < sc.ev) return;
          sc.ev = sc.t + rr(1.8, 2.8); say(b, BUB.NOTE, 1.5);
          for (const a of aud) if (a.pose !== 'stand' && rnd() < 0.5) a.pose = 'stand';
          const a = aud.length ? pick(aud) : null;
          if (a && idle(a) && sc.t > 8) { const r = rnd(); if (r < 0.3) { a.pose = 'cheer'; hop(a, 1.2); } else if (r < 0.6) say(a, pick([BUB.HEART, BUB.SMILE, BUB.NOTE]), 1.6); else hop(a, 1); }
        },
      });
      return sc;
    }
    return null;
  };
  // 벤치의 어르신 둘(담소). 벤치는 화면 가로 방향으로 놓는다.
  const mkBench = (c0, r0, r1, bits = BIT.PAVE, young = false) => {
    for (let tries = 0; tries < 400; tries++) {
      const c = c0 ? polar(c0, r0, r1) : randomPt(), pts = [[c[0] - ex[0] * 0.75, c[1] - ex[1] * 0.75], [c[0] + ex[0] * 0.75, c[1] + ex[1] * 0.75]];
      if (!okDisk(c[0], c[1], 2.5, bits) || !groupOk(pts, bits) || !free(c[0], c[1], 2.2)) continue;
      for (const q of pts) claim(q[0], q[1]);
      claim(c[0], c[1]);
      const as = pts.map((q, k) => mk(q[0], q[1], LA(young && k ? pick(cast.normal) : pick(cast.elder), { noUmb: true }), { pose: 'sit', pose0: 'sit', z: 0.45 }));
      const sc = addScene('bench', c, {
        actors: as, T: rr(2, 8),
        want: () => E.day > 0.4 && !E.rain && E.tod < 19 && sc.nightKey <= E.keep + 0.3,
        step(dt) { sc.t += dt; if (sc.t >= sc.T) { sc.t = 0; sc.T = rr(3, 7); stats.bench++; say(pick(as), pick([BUB.DOTS, BUB.DOTS, BUB.SMILE, BUB.NOTE]), 2); } },
      });
      props.push({ type: 'bench', x: c[0], y: c[1], variant: 0, sc });
      return sc;
    }
    return null;
  };
  // 비눗방울 부는 아이와 보호자
  const mkSoap = (c0, r0, r1, bits = BIT.PAVE) => {
    for (let tries = 0; tries < 400; tries++) {
      const c = polar(c0, r0, r1), g = [c[0] + 1.2, c[1] + 0.5];
      if (!okDisk(c[0], c[1], 4, bits) || !groupOk([c, g], bits)) continue;
      claim(c[0], c[1]); claim(g[0], g[1]);
      const kid = mk(c[0], c[1], LKid()), par = mk(g[0], g[1], palNormal());
      const sc = addScene('soap', c, {
        actors: [kid, par], T: rr(3, 9), n: 0,
        want: () => E.day > 0.5 && !E.rain && E.season !== 3,
        nudge() { sc.T = Math.min(sc.T, sc.t + 0.4); },
        step(dt) {
          sc.t += dt;
          if (sc.n > 0 && sc.t >= sc.next) { sc.n--; sc.next = sc.t + 0.22; const a = rnd() * TAU; fx.push({ type: 'soap', x: kid.x, y: kid.y, z: 1.2, dx: Math.cos(a) * rr(1, 3), dy: Math.sin(a) * rr(1, 3), ph: rnd() * 6, t: 0, T: rr(2.2, 3.6) }); if (sc.n === 0) kid.pose = 'stand'; }
          if (sc.t < sc.T) return;
          sc.t = 0; sc.T = rr(7, 16); sc.n = 7 + ri(5); sc.next = 0.3; stats.soap++; kid.pose = 'cheer';
          if (rnd() < 0.4) say(par, BUB.SMILE, 1.8);
        },
      });
      return sc;
    }
    return null;
  };
  // 프러포즈: 해 질 녘 향원정 근처의 두 사람
  const mkProposal = () => {
    for (let tries = 0; tries < 300; tries++) {
      const p = polar(A.hyang, 10, 55), ang = rnd() * TAU, q = [p[0] + Math.cos(ang) * 1.2, p[1] + Math.sin(ang) * 1.2];
      if (!groupOk([p, q])) continue;
      claim(p[0], p[1]); claim(q[0], q[1]);
      const a = mk(p[0], p[1], palNormal()), b = mk(q[0], q[1], LH());
      const sc = addScene('proposal', p, {
        pin: true, actors: [a, b], cool: 0, T: rr(8, 20),
        want: () => true,
        ask() { sc.st = 'ask'; sc.t = 0; sc.ph = 0; stats.proposal++; a.pose = 'kneel'; say(a, BUB.HEART, 3); },
        step(dt) {
          sc.t += dt; sc.cool -= dt;
          if (sc.st === 'idle') {
            if (sc.cool <= 0 && E.tod >= 16.6 && E.tod < 17.8) sc.ask();   // 관람 시간이 끝나기 전, 해가 기울 무렵
            else if (sc.t >= sc.T) { sc.t = 0; sc.T = rr(8, 20); say(rnd() < 0.5 ? a : b, pick([BUB.DOTS, BUB.SMILE]), 1.8); }
          } else {
            if (sc.ph === 0 && sc.t > 1.6) { sc.ph = 1; b.pose = 'cheer'; hop(b, 1.4); say(b, BUB.BANG, 1.2); }
            if (sc.ph === 1 && sc.t > 3.2) { sc.ph = 2; say(b, BUB.HEART, 3.5); }
            if (sc.ph === 2 && sc.t > 5) { sc.ph = 3; a.pose = 'stand'; b.pose = 'stand'; say(a, BUB.HEART, 3); hop(a, 1.5); }
            if (sc.t > 8.5) { sc.st = 'idle'; sc.t = 0; sc.cool = 90; }
          }
        },
      });
      return sc;
    }
    return null;
  };
  // 연 날리는 아이와 보호자(트인 마당)
  const mkKite = (where, bits = BIT.PAVE) => {
    for (let tries = 0; tries < 2000; tries++) {
      const c = randomPt();
      if (where && !where(c)) continue;
      if (!okDisk(c[0], c[1], 7, bits) || !free(c[0], c[1], 2)) continue;
      const g = [c[0] + 1.3, c[1] + 0.4];
      if (!groupOk([c, g], bits)) continue;
      claim(c[0], c[1]); claim(g[0], g[1]);
      const kid = mk(c[0], c[1], LKid(), { pose: 'cheer', pose0: 'cheer' }), par = mk(g[0], g[1], palNormal());
      const sc = addScene('kite', c, {
        actors: [kid, par], T: rr(4, 12),
        want: () => E.day > 0.5 && !E.rain && E.season !== 3,
        step(dt) { sc.t += dt; if (sc.t >= sc.T) { sc.t = 0; sc.T = rr(12, 24); stats.kite++; hop(kid, 1.5); say(kid, BUB.NOTE, 1.8); if (rnd() < 0.5) say(par, BUB.SMILE, 1.6); } },
      });
      props.push({ type: 'kite', x: c[0], y: c[1], variant: ri(3), ph: rnd() * TAU, sc });
      return sc;
    }
    return null;
  };

  // ── 도시 지도(여의도) 장면. 자리는 classes.png 와 물까지 거리·랜드마크(지면 자리)로 고른다.
  const inPark = (p) => PARKS.some((q) => Math.hypot(p[0] - q[0], p[1] - q[1]) < q[2]);
  const riverLawn = (p) => !banned(p[0], p[1]) && dWater(p[0], p[1]) < 190;
  const lawn = (p) => !banned(p[0], p[1]) && (dWater(p[0], p[1]) < 190 || inPark(p)) && clsAt(p[0], p[1]) === 3;
  const nearBiz = (p, r = 420) => BIZ.some((q) => Math.hypot(p[0] - q[0], p[1] - q[1]) < r);
  // 공원에 사람이 있는 때: 낮, 그리고 여름 저녁(한강공원은 한여름 저녁에 가장 붐빈다)
  const outdoors = () => !E.rain && E.season !== 3 && (E.day > 0.5 || (E.season === 1 && E.tod >= 17 && E.tod < 21.7) || (E.season !== 3 && E.tod >= 17 && E.tod < 20));
  const eveBoost = (sc) => sc.nightKey <= (E.season === 1 && E.tod >= 17 && E.tod < 21.7 ? 1 : E.day > 0.5 ? (E.season === 1 && E.tod >= 12 && E.tod < 16 ? 0.55 : 0.9) : 0.45);
  // 잔디에 앉은 사람(혼자 또는 둘, 돗자리 없이)
  const mkLawnSit = (where) => {
    for (let tries = 0; tries < 3000; tries++) {
      const c = randomPt();
      if (!where(c) || !okDisk(c[0], c[1], 1.5, BIT.GRASS) || !free(c[0], c[1], 1.6)) continue;
      const n = 1 + (rnd() < 0.55 ? 1 : 0), pts = n === 1 ? [c] : [[c[0] - ex[0] * 0.55, c[1] - ex[1] * 0.55], [c[0] + ex[0] * 0.55, c[1] + ex[1] * 0.55]];
      if (!groupOk(pts, BIT.GRASS, 0.9)) continue;
      for (const q of pts) claim(q[0], q[1]);
      const as = pts.map((q) => mk(q[0], q[1], LA(pick(cast.sitters)), { pose: 'sit', pose0: 'sit' }));
      const sc = addScene('lawn', c, {
        actors: as, T: rr(3, 12),
        want: () => outdoors() && E.tod >= 8.5 && eveBoost(sc),
        step(dt) { sc.t += dt; if (sc.t >= sc.T) { sc.t = 0; sc.T = rr(6, 16); stats.lawn++; if (as.length > 1 || rnd() < 0.3) say(pick(as), pick([BUB.DOTS, BUB.NOTE, BUB.SMILE, BUB.HEART]), 2); } },
      });
      return sc;
    }
    return null;
  };
  // 공 던지기: 아이와 보호자(또는 어른 둘)가 5~7 m 떨어져 공을 주고받는다
  const mkBall = (where) => {
    for (let tries = 0; tries < 3000; tries++) {
      const c = randomPt();
      if (!where(c)) continue;
      const ang = rnd() * TAU, d = rr(2.5, 3.5), p = [c[0] + Math.cos(ang) * d, c[1] + Math.sin(ang) * d], q = [c[0] - Math.cos(ang) * d, c[1] - Math.sin(ang) * d];
      if (!okDisk(c[0], c[1], 4, BIT.GRASS) || !groupOk([p, q], BIT.GRASS, 3) || !free(c[0], c[1], 2)) continue;
      claim(p[0], p[1]); claim(q[0], q[1]); claim(c[0], c[1]);
      const kidish = rnd() < 0.65, a = mk(p[0], p[1], kidish ? LKid() : palNormal()), b = mk(q[0], q[1], palNormal());
      const sc = addScene('ball', c, {
        actors: [a, b], T: rr(1, 4), turn: 0,
        want: () => outdoors() && E.tod >= 9 && E.tod < 20.5 && eveBoost(sc),
        nudge() { sc.T = Math.min(sc.T, sc.t + 0.3); },
        step(dt) {
          sc.t += dt;
          if (sc.hit > 0 && (sc.hit -= dt) <= 0) { const r2 = [a, b][1 - sc.turn]; r2.pose = 'stand'; hop(r2, 0.5); if (rnd() < 0.25) say(r2, pick([BUB.SMILE, BUB.BANG, BUB.NOTE]), 1.2); [a, b][sc.turn].pose = 'stand'; }
          if (sc.t < sc.T) return;
          sc.t = 0; sc.T = rr(1.8, 3.2); sc.turn = 1 - sc.turn; stats.ball++;
          const th = [a, b][sc.turn], ca = [a, b][1 - sc.turn];
          th.pose = 'cheer'; ca.pose = 'cheer'; sc.hit = 1.1;
          fx.push({ type: 'ball', x: th.x, y: th.y, x1: ca.x, y1: ca.y, z: 1.2, t: 0, T: 1.1 });
        },
      });
      return sc;
    }
    return null;
  };
  // 낚시: 물가(물에서 2~9 m)에 서거나 의자에 앉아 물 쪽으로 낚싯대를 드리운다
  const mkFish = () => {
    for (let tries = 0; tries < 6000; tries++) {
      const c = randomPt();
      const dw = dWater(c[0], c[1]);
      if (dw < 2 || dw > 9 || banned(c[0], c[1]) || !tryPt(c[0], c[1], ANY)) continue;
      // 물 쪽 = 거리가 줄어드는 방향(화면 가로 성분으로 왼쪽·오른쪽을 정한다)
      let bx = 0, by = 0;
      for (let k = 0; k < 8; k++) { const a2 = k * TAU / 8, d2 = dWater(c[0] + Math.cos(a2) * 6, c[1] + Math.sin(a2) * 6); bx -= Math.cos(a2) * d2; by -= Math.sin(a2) * d2; }
      const sxw = bx * ex[0] + by * ex[1];
      if (Math.abs(sxw) < 1e-3 || !free(c[0], c[1], 6)) continue;
      claim(c[0], c[1]);
      const sit = rnd() < 0.6, a = mk(c[0], c[1], LA(rnd() < 0.5 ? pick(cast.elder) : pick(cast.normal), { noUmb: rnd() < 0.5, hat: rnd() < 0.6 ? 1 + ri(8) : 0 }), { pose: sit ? 'sit' : 'stand', pose0: sit ? 'sit' : 'stand', prop: 'rod', z: sit ? 0.35 : 0, face: sxw > 0 ? 1 : -1 });
      a.pose0 = a.pose; a.face0 = a.face;
      const sc = addScene('fish', c, {
        actors: [a], T: rr(8, 30),
        want: () => !E.rain && ((E.tod >= 5 && E.tod < 21) || sc.nightKey < 0.3) && (E.season !== 3 || sc.nightKey < 0.35),
        reset() { a.face = a.face0; },
        step(dt) { sc.t += dt; a.face = a.face0; if (sc.t >= sc.T) { sc.t = 0; sc.T = rr(20, 60); stats.fish++; if (rnd() < 0.35) { say(a, pick([BUB.BANG, BUB.NOTE]), 1.6); hop(a, 0.6); } else say(a, BUB.DOTS, 1.4); } },
      });
      return sc;
    }
    return null;
  };
  // 물놀이(여름): 물빛광장 바닥분수에서 아이들이 뛰어다니고 보호자가 지켜본다
  const mkSplash = (c0) => {
    for (let tries = 0; tries < 2000; tries++) {
      const c = polar(c0, 0, tries < 1000 ? 45 : 110);
      if (clsAt(c[0], c[1]) !== 11 || !okDisk(c[0], c[1], 6) || !free(c[0], c[1], 3)) continue;
      const kids = [], g = polar(c, 6.5, 8);
      if (!tryPt(g[0], g[1])) continue;
      for (let k = 0, t = 0; kids.length < 3 + (rnd() < 0.5 ? 1 : 0) && t < 80; t++) { const q = polar(c, 0.5, 4.5); if (tryPt(q[0], q[1]) && kids.every((o) => Math.hypot(o.x - q[0], o.y - q[1]) > 1.1)) { kids.push(mk(q[0], q[1], LKid())); k++; } }
      if (kids.length < 3) { actors.length -= kids.length; continue; }
      claim(c[0], c[1]); claim(g[0], g[1]);
      const par = mk(g[0], g[1], palNormal());
      const sc = addScene('splash', c, {
        actors: [...kids, par], T: 0.5, C: c,
        want: () => E.season === 1 && E.tod >= 10.5 && E.tod < 20.5 && !E.rain,
        nudge() { sc.T = Math.min(sc.T, sc.t + 0.2); },
        step(dt) {
          sc.t += dt;
          if (rnd() < dt * 9) { const a2 = rnd() * TAU, r2 = rnd() * 3.5; fx.push({ type: 'drop', x: c[0] + Math.cos(a2) * r2, y: c[1] + Math.sin(a2) * r2, z: 0, h: rr(1.2, 2.4), t: 0, T: rr(0.5, 0.8) }); }
          if (sc.t < sc.T) return;
          sc.t = 0; sc.T = rr(0.6, 1.6); stats.splash++;
          const kd = pick(kids);
          if (idle(kd)) {
            const q = polar(c, 0.4, 4.6);
            if (okLine(kd.x, kd.y, q[0], q[1]) && kids.every((o) => o === kd || Math.hypot(o.x - q[0], o.y - q[1]) > 1.0)) { kd.pose = 'run'; go(kd, [q], 2.6); }
            else { kd.pose = 'cheer'; hop(kd, 0.8); say(kd, pick([BUB.NOTE, BUB.SMILE, BUB.BANG]), 1.2); }
          }
          for (const k2 of kids) if (idle(k2) && k2.pose === 'run') k2.pose = 'stand';
          if (rnd() < 0.15) say(par, pick([BUB.SMILE, BUB.DOTS]), 1.5);
        },
      });
      return sc;
    }
    return null;
  };
  const chatStop = (sc, as) => { if (sc.ev === 0) { sc.ev = 1; say(pick(as), pick([BUB.DOTS, BUB.SMILE, BUB.NOTE, BUB.DOTS]), 2); } };
  const officeLook = () => LA(pick(cast.office), { cup: rnd() < 0.5 ? 1 : 0 });
  function placeCity() {
    const riverPts = [];   // 강변 달리기 띠의 점(약 60 m 간격): 강변 장면의 중심 후보
    for (const c of cityRun) for (let d = 20; d < c.L - 20; d += 60) { pointAt(c.pts, c.cum, d, P3); riverPts.push([P3[0], P3[1]]); }
    const rp = () => pick(riverPts);
    const P = (k) => A[k] || null;
    // 사진: 물빛광장·문화의마당·국회 앞·63빌딩 앞
    for (const [k, n] of [['mulbit', 3], ['park_plaza', 2], ['assembly', 3], ['63', 1], ['hangang', 2]]) if (P(k)) for (let i = 0; i < n; i++) mkPhoto(P(k), 10, k === 'assembly' ? 140 : 90, i === 0);
    // 국회 앞 안내 관광(작은 무리)
    if (P('assembly')) {
      const offs = block(6);
      mkTroupe('guide', P('assembly'), 20, 170, offs.map((off, k) => (k === 0 ? { off, pal: LA(pick(cast.guide), { uniform: true }), prop: 'flag', lag: 0 } : { off, pal: LA(pick(cast.normal), { hat: rnd() < 0.5 ? 1 + ri(8) : 0 }), lag: 0.4 + k * 0.25 })),
        { legs: 4, minLeg: 16, maxLeg: 42, gather: true, speed: 1.0, stopT: [9, 16], stop: guideStop, want: (sc) => E.tod >= 9.5 && E.tod < 17.5 && !E.rain && sc.nightKey < 0.9 });
    }
    // 업무지구 점심 무리(11:30~13:00): 직장인 3~5명, 커피 든 사람
    for (let k = 0; k < 14 && BIZ.length; k++) {
      const n = 3 + ri(3);   // 둘씩 나란히(0.9 m) 2~3 줄: 좁은 보도에도 들어간다
      mkTroupe('lunch', BIZ[k % BIZ.length], 20, 320, Array.from({ length: n }, (_, j) => ({ off: [(j % 2) * 0.9, -Math.floor(j / 2) * 0.95], pal: officeLook(), lag: j * 0.15 })),
        { legs: 4, minLeg: 10, maxLeg: 36, speed: 1.05, stopT: [3, 8], stop: chatStop, gap: 0.8, bits: BIT.PAVE | BIT.DIRT, want: (sc) => E.tod >= 11.45 + sc.nightKey * 0.25 && E.tod < 13.05 - sc.nightKey * 0.1 && !E.rain });
    }
    // 광장의 친구 무리(셀카·수다)와 강변 연인
    for (const c of [P('mulbit'), P('park_plaza'), P('mulbit'), P('hangang'), P('park'), rp(), rp(), rp()]) {
      if (!c) continue;
      const n = 3 + ri(2), ang = sideAng();
      mkTroupe('friends', c, 6, 120, Array.from({ length: n }, (_, k) => ({ off: [Math.cos(ang) * k * 1.05, Math.sin(ang) * k * 1.05], pal: palNormal(), lag: k * 0.2 })),
        { legs: 4, minLeg: 12, maxLeg: 36, speed: 0.9, stopT: [4, 9], stop: hanbokStop, bits: BIT.PAVE | BIT.DIRT, want: (sc) => outdoors() && eveBoost(sc) });
    }
    for (let k = 0; k < 10; k++) {
      const c = k < 2 && P('park') ? P('park') : rp();
      if (!c) continue;
      const ang = sideAng(), dry = LA(pick(cast.normal)), wet = LA(pick(cast.normal), { noUmb: true });
      dry.h = 0.1;
      mkTroupe('couple', c, 4, 90, [{ off: [0, 0], pal: dry, lag: 0 }, { off: [Math.cos(ang) * 0.8, Math.sin(ang) * 0.8], pal: wet, lag: 0 }],
        { legs: 4, minLeg: 14, maxLeg: 40, speed: 0.85, stopT: [4, 10], stop: coupleStop, gap: 0.75, bits: BIT.PAVE | BIT.DIRT, want: (sc) => sc.nightKey <= Math.max(E.keep, E.tod >= 17 && E.tod < 22.5 ? 0.9 : 0) });
    }
    if (P('mulbit')) for (let k = 0; k < 3; k++) mkSplash(P('mulbit'));
    for (const c of [P('mulbit'), P('park_plaza')]) if (c) mkBusker(c);
    // 벤치(그늘 아래): 공원·강변 보행로 옆
    for (let k = 0; k < 18; k++) { const c = k < 8 && P('park') ? P('park') : rp(); if (c) mkBench(c, 5, k < 8 ? 330 : 120, BIT.PAVE | BIT.DIRT, k % 3 === 2); }
    for (let k = 0; k < 4; k++) { const c = P('park') || rp(); mkSoap(c, 10, 320, BIT.PAVE | BIT.DIRT | BIT.GRASS); }
    for (let k = 0; k < 4; k++) mkSnow(k < 2 && P('park') ? P('park') : rp(), 5, 200, BIT.PAVE | BIT.DIRT | BIT.GRASS);
    for (let k = 0; k < 12; k++) mkFish();
    // 잔디: 소풍(돗자리)·앉은 사람·공놀이·연
    const pw = (sc) => outdoors() && E.tod >= 10.5 && eveBoost(sc);   // 돗자리 소풍: 늦은 아침부터
    for (let k = 0; k < 130; k++) mkPicnic(k < 100 ? (p) => riverLawn(p) && lawn(p) : lawn, pw);
    for (let k = 0; k < 110; k++) mkLawnSit(k < 75 ? (p) => riverLawn(p) && lawn(p) : lawn);
    for (let k = 0; k < 24; k++) mkBall(lawn);
    for (let k = 0; k < 5; k++) mkKite((p) => riverLawn(p) && lawn(p), BIT.GRASS);
    for (let k = 0; k < 4; k++) mkJogger();
    // 소품이 놓인 땅 높이(굽기에서 잔디·광장이 z 0 보다 조금 높다): 그릴 때 그 높이로 올려 깊이 검사를 통과한다
    const hA = opts.heightAt || (() => 0);
    for (const p of props) { proj.project(p.x, p.y, 0, S); p.zg = Math.max(0, Math.min(1.2, hA(Math.floor(S[0]), Math.floor(S[1])))); }   // 그릴 때 같은 픽셀·그 면 깊이
  }

  // ── 배치(고정 시드). 순서가 곧 자리 우선순위.

  // ── 광화문 앞 해치 한 쌍(고정 소품). 그림 타일에는 없어서 스프라이트로 세운다.
  // 좌표 근거: 광화문 정면 가운데의 지면 = 지도 px (783, 1218)(세 홍예 가운데 아래, 화면에서 읽은 값). 월드 축은 +x 가 문의 가로(동쪽), −y 가 남쪽(세종대로 쪽).
  // 실제 해치는 월대 남쪽 끝 좌우에 남쪽을 보고 앉아 있다 → 월대 남쪽 끝(깊이 맵에 월대가 없으면 정면에서 남쪽으로 24 m), 좌우로 14 m 를 목표로 하고,
  // 둘이 대칭을 유지한 채 가장 가까운 「보도·광장(클래스 11·1) + 걷는 경로에서 1.8 m 이상 + 예약 자리와 안 겹침」 자리를 클래스 맵으로 찾는다.
  const haechi = [];
  if (!city) {
    const G0 = toWorld(783, 1218, [0, 0]);
    const paths = [];   // 근처를 지나는 걷는 경로의 점(1 m 간격)
    for (const w of walkers) for (let d = 0; d <= w.L; d += 1) { pointAt(w.pts, w.cum, d, P3); if (Math.abs(P3[0] - G0[0]) < 40 && Math.abs(P3[1] - G0[1] + 24) < 30) paths.push(P3[0], P3[1]); }
    const okSpot = (x, y) => {
      // 해치는 월대 앞 지면에 선다(월대·난간 위가 아니다): 둘레가 보도·광장이고 지면 높이
      for (const [dx, dy] of [[0, 0], [1.2, 0], [-1.2, 0], [0, 1.2], [0, -1.2]]) { const c = clsAt(x + dx, y + dy); if ((c !== 11 && c !== 1) || Math.abs(hrAt(x + dx, y + dy)) > 0.3) return false; }
      if (!free(x, y, 2.2)) return false;
      for (let k = 0; k < paths.length; k += 2) if (Math.hypot(paths[k] - x, paths[k + 1] - y) < 1.8) return false;
      return true;
    };
    // 월대(걷는 단 칸)가 깊이 맵에 있으면 그 축과 남쪽 끝을 기준으로 삼는다: 해치 = 월대 남쪽 끝 좌우의 지면. 없으면(평평한 옛 그림) 정면 기준 24 m.
    let cx0 = G0[0], depT = 24;
    {
      let lo = 1e9, hi = -1e9, south = -1;
      for (let dep = 0; dep <= 70; dep += 0.5) for (let lat = -30; lat <= 30; lat += 0.5) if (zAt(G0[0] + lat, G0[1] - dep) > 0) { lo = Math.min(lo, lat); hi = Math.max(hi, lat); south = Math.max(south, dep); }
      if (south > 0 && hi - lo > 8) { cx0 = G0[0] + (lo + hi) / 2; depT = south; }
    }
    let best = null, bd = 1e9;
    for (let lat = 9; lat <= 20; lat += 0.5) for (let dep = 14; dep <= depT + 12; dep += 0.5) {
      const d = Math.hypot(lat - 14, dep - depT);
      if (d >= bd || !okSpot(cx0 - lat, G0[1] - dep) || !okSpot(cx0 + lat, G0[1] - dep)) continue;
      bd = d; best = [lat, dep];
    }
    if (best) for (const sd of [-1, 1]) {
      const x = cx0 + sd * best[0], y = G0[1] - best[1];
      haechi.push({ x, y, side: sd });
      props.push({ type: 'haechi', x, y, variant: 0, zp: zAt(x, y) });
      claim(x, y); for (let a = 0; a < 6; a++) claim(x + Math.cos(a * TAU / 6) * 1.2, y + Math.sin(a * TAU / 6) * 1.2);   // 사람이 서거나 지나가지 않는 자리
    }
  }

  // ── 궁 둘레 러너: 담장 바깥 보도를 따라 달린다(담을 상자로 보고 바깥쪽으로 가장 가까운 보도 띠를 클래스 맵에서 찾아 잇는다).
  // 차도(횡단보도 포함)는 건너지 않는다 → 보도가 끊기는 곳에서 구간이 나뉘고, 러너는 한 구간을 오간다.
  const RUNB = BIT.PAVE | BIT.DIRT;
  const runChains = [];
  if (city) runChains.push(...cityRun);   // 도시: 강변 달리기 띠
  else {
    // 궁은 차도로 둘러싸여 있고, 그 차도 안쪽 가장자리에 담길(보도, 클래스 1·11)이 가는 띠로 붙어 있다.
    // 궁 한가운데에서 사방으로 선을 쏘아 처음 만나는 차도를 찾고, 거기서 1.5~9 m 안쪽으로 물러나 보도 칸을 고른다 → 각도 순서대로 이으면 담길 한 바퀴.
    // 건물에 가려 차도가 안 보이는 방향은 엉뚱하게 먼 차도를 만나므로(반지름이 튄다) 그 자리에서 구간을 끊는다.
    const [X0, Y0, X1, Y1] = PALACE, cx = (X0 + X1) / 2, cy = (Y0 + Y1) / 2, N = 900;
    // 담길은 폭 2~4 m 라 3×3 칸(okPoint)까지는 요구하지 않는다. 그 칸과 좌우 0.5 m 가 보도이면 된다.
    const okRun = (x, y) => { const c = clsAt(x, y); return (c === 11 || c === 1) && !!(cellAt(x, y) & RUNB); };
    const ray = [];
    for (let k = 0; k < N; k++) {
      const a = k * TAU / N, ux = Math.cos(a), uy = Math.sin(a);
      let hit = null;
      for (let r = 120; r < 640 && !hit; r += 0.5) {
        const x = cx + ux * r, y = cy + uy * r;
        if (x < X0 - 70 || x > X1 + 70 || y < Y0 - 80 || y > Y1 + 70) break;
        if (clsAt(x, y) !== 2) continue;
        for (let b = 1.5; b <= 9; b += 0.5) if (okRun(cx + ux * (r - b), cy + uy * (r - b))) { const rr2 = okRun(cx + ux * (r - b - 1), cy + uy * (r - b - 1)) ? r - b - 1 : r - b; hit = [cx + ux * rr2, cy + uy * rr2, 0, rr2]; break; }
        if (!hit) break;
      }
      ray.push(hit);
    }
    let cur = null;
    // 이웃한 점끼리 잇는다. 사이(0.12 m 간격)가 모두 보도(클래스 1·11)일 때만 — 차도·건물·궁 안 마당을 지나면 거기서 구간을 끊는다.
    const okSeg = (q, p) => { const n = Math.max(1, Math.ceil(Math.hypot(p[0] - q[0], p[1] - q[1]) / 0.12)); for (let k = 1; k < n; k++) { const c = clsAt(q[0] + (p[0] - q[0]) * k / n, q[1] + (p[1] - q[1]) * k / n); if (c !== 1 && c !== 11) return false; } return true; };
    // 선을 쏘아 얻은 점은 들쭉날쭉하다 → 이웃과 평균 내어 펴되, 편 자리와 양옆 선분이 보도일 때만 받아들인다(세 번 반복)
    const smooth = (pts) => { for (let pass = 0; pass < 3; pass++) for (let i = 1; i < pts.length - 1; i++) { const a = pts[i - 1], b = pts[i], c = pts[i + 1], m = [(a[0] + 2 * b[0] + c[0]) / 4, (a[1] + 2 * b[1] + c[1]) / 4, 0, b[3]]; if (okRun(m[0], m[1]) && okSeg(a, m) && okSeg(m, c)) pts[i] = m; } return pts; };
    const flush = () => { if (cur && cur.length >= 2) { smooth(cur); const cum = cumLengths(cur); if (cum[cum.length - 1] >= 60) runChains.push({ pts: cur, cum, L: cum[cum.length - 1] }); } cur = null; };
    let start = 0;
    for (let k = 0; k < N; k++) { const p = ray[k], q = ray[(k + N - 1) % N]; if (p && (!q || Math.hypot(p[0] - q[0], p[1] - q[1]) > 20 || !okSeg(q, p))) { start = k; break; } }
    for (let n = 0; n < N; n++) {
      const p = ray[(start + n) % N];
      if (!p) continue;
      if (cur) { const q = cur[cur.length - 1]; if (Math.hypot(p[0] - q[0], p[1] - q[1]) > 20 || !okSeg(q, p)) flush(); }
      (cur ||= []).push(p);
    }
    flush();
    // 구간 잇기: 이웃한 두 구간의 끝이 보도로 이어지면 한 구간으로 합친다 → 러너가 짧은 구간에서 자꾸 되돌지 않고 길게 달린다.
    // 클래스 맵은 화면 공간이라 가로수 수관(10)이 담길을 가린 곳에서 구간이 끊겨 있다. 잇는 길은 보도(1·11)와 수관에 가린 곳(10)만 지난다.
    // 차도(2, 진입로·횡단보도 포함)·잔디·건물·궁 안은 지나지 않는다 → 차도가 가로지르는 곳에서는 여전히 끊긴다.
    // 곧게 이을 수 없으면 1 m 격자에서 가장 짧은 보도 길을 찾는다(곧은 거리의 1.8배 + 20 m 까지). 해치 둘레 3 m 는 피한다.
    // 광화문 정면은 잇지 않는다: 서쪽 담길에서 광장으로 가는 보도는 문 바로 앞(수문장 자리)뿐이라 러너가 의식 한가운데를 가로지르게 된다.
    const hy = haechi.length ? haechi[0].y - 3 : -1e9, hx = haechi.length ? (haechi[0].x + haechi[1].x) / 2 : 0;   // 해치보다 문 쪽(월대·수문장 자리)으로는 달리지 않는다
    const passC = (x, y) => { const c = clsAt(x, y); return (c === 1 || c === 11 || c === 10) && !inPalace(x, y) && !(y > hy && Math.abs(x - hx) < 45 && y < PALACE[1] + 5); };
    const okLink = (q, p) => { const n = Math.max(1, Math.ceil(Math.hypot(p[0] - q[0], p[1] - q[1]) / 0.12)); for (let k = 0; k <= n; k++) { const x = q[0] + (p[0] - q[0]) * k / n, y = q[1] + (p[1] - q[1]) * k / n; if (!passC(x, y)) return false; for (const h of haechi) if (Math.hypot(x - h.x, y - h.y) < 3) return false; } return true; };
    const link = (a, b) => {
      const d = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (d > 100) return null;
      if (okLink(a, b)) return [];
      for (const cl of [0.7, 0.35, 0]) { const r = route(a, b, d, cl); if (r) return r; }
      return null;
    };
    const route = (a, b, d, cl) => {
      const M = 60, gx0 = Math.min(a[0], b[0]) - M, gy0 = Math.min(a[1], b[1]) - M, gw = Math.ceil(Math.abs(a[0] - b[0]) + 2 * M) + 1, gh = Math.ceil(Math.abs(a[1] - b[1]) + 2 * M) + 1;
      const idx = (p) => Math.round(p[1] - gy0) * gw + Math.round(p[0] - gx0), si = idx(a), gi = idx(b);
      const open = (i) => { const x = gx0 + (i % gw), y = gy0 + Math.floor(i / gw); if (i === si || i === gi) return true; for (const [dx, dy] of [[0, 0], [cl, 0], [-cl, 0], [0, cl], [0, -cl]]) if (!passC(x + dx, y + dy)) return false; for (const h of haechi) if (Math.hypot(x - h.x, y - h.y) < 3.5) return false; return true; };
      const from = new Int32Array(gw * gh).fill(-1), q = [si]; from[si] = si;
      for (let qi = 0; qi < q.length && from[gi] < 0; qi++) {
        const i = q[qi], x = i % gw, y = Math.floor(i / gw);
        for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { const nx = x + dx, ny = y + dy; if (nx < 0 || ny < 0 || nx >= gw || ny >= gh) continue; const j = ny * gw + nx; if (from[j] >= 0 || !open(j)) continue; from[j] = i; q.push(j); }
      }
      if (from[gi] < 0) return null;
      const cells = []; for (let i = from[gi]; i !== si; i = from[i]) cells.push([gx0 + (i % gw), gy0 + Math.floor(i / gw), 0, 0]);
      cells.reverse();
      // 격자 길을 편다: 지금 점에서 곧게 갈 수 있는 가장 먼 점으로 건너뛴다
      const all = [a, ...cells, b], out = [];
      for (let i = 0; i < all.length - 1;) { let j = all.length - 1; while (j > i + 1 && !okLink(all[i], all[j])) j--; if (j === i + 1 && !okLink(all[i], all[j])) return null; if (j < all.length - 1) out.push(all[j]); i = j; }
      let len = 0; { let p = a; for (const c of [...out, b]) { len += Math.hypot(c[0] - p[0], c[1] - p[1]); p = c; } }
      return len <= d * 1.8 + 20 ? out : null;
    };
    if (runChains.length > 1) {
      const src = runChains.splice(0), groups = [];
      let g = src[0].pts.slice();
      for (let i = 0; i < src.length; i++) {
        const nx = src[(i + 1) % src.length], mid = link(g[g.length - 1], nx.pts[0]);
        if (i + 1 < src.length) { if (mid) g = g.concat(mid, nx.pts); else { groups.push(g); g = nx.pts.slice(); } }
        else if (mid && groups.length) groups[0] = g.concat(mid, groups[0]);   // 마지막 구간이 첫 구간으로 이어진다
        else groups.push(g);
      }
      for (const pts of groups) { const cum = cumLengths(pts); runChains.push({ pts, cum, L: cum[cum.length - 1] }); }
    }
  }
  // 러너 무리: 혼자 또는 2~5명이 한 줄(러닝 크루). u = 구간 위를 접지 않고 잰 거리(왕복), lat = 옆으로 비킨 거리.
  const runners = [];
  {
    const RL = (h) => LK('a', cast.runner[Math.floor(h * cast.runner.length)], fr(h * 17), { noUmb: true, runner: true, palW: cast.runnerW[Math.floor(fr(h * 5) * cast.runnerW.length)], hat: fr(h * 3) < 0.25 ? 1 + Math.floor(fr(h * 29) * 5) : 0 });
    const total = runChains.reduce((a, c) => a + c.L, 0);
    let id = 0;
    for (const c of runChains) {
      const n = Math.max(1, Math.round((city ? RUN_GROUPS_CITY : RUN_GROUPS) * c.L / total));
      for (let k = 0; k < n; k++, id++) {
        const h = hash01(id * 53 + 7), crew = hash01(id * 59 + 3) < 0.38 ? 1 + Math.floor(hash01(id * 61 + 11) * 4) : 0;   // 뒤따르는 사람 수 0 또는 1~4
        const fol = Array.from({ length: crew }, (_, j) => ({ dd: -(j + 1) * 1.7, look: RL(hash01(id * 67 + j * 13 + 1)) }));
        runners.push({ id, c, u: h * 2 * c.L, ou: 0, v: 2.9 + 0.9 * hash01(id * 71 + 5) - (crew ? 0.25 : 0), cv: 3, lat: 0, olat: 0, latT: 0, hold: 0, look: RL(hash01(id * 73 + 9)), fol, key: crew ? 0.06 + 0.94 * hash01(id * 79 + 2) : hash01(id * 79 + 2),   // 크루는 한밤(비율 0.03)에는 나오지 않는다
          vis: true, face: 1 });
      }
    }
    for (const r of runners) r.ou = r.u;
  }
  // 러너 근처에 올 수 있는 걷는 사람(경로가 러너 구간 6 m 안을 지나는 사람)만 비켜 가기 검사에 쓴다
  const runNear = [];
  {
    const cells = new Set(), key = (x, y) => Math.floor(x / 6) * 100003 + Math.floor(y / 6);
    for (const c of runChains) for (let d = 0; d <= c.L; d += 3) { pointAt(c.pts, c.cum, d, P3); for (let j = -1; j <= 1; j++) for (let i = -1; i <= 1; i++) cells.add(key(P3[0] + i * 6, P3[1] + j * 6)); }
    walkers.forEach((w, i) => { for (let d = 0; d <= w.L; d += 3) { pointAt(w.pts, w.cum, d, P3); if (cells.has(key(P3[0], P3[1]))) { runNear.push(i); return; } } });
  }
  const rfold = (c, u) => { let d = u % (2 * c.L); if (d < 0) d += 2 * c.L; return d > c.L ? 2 * c.L - d : d; };
  const rdir = (c, u) => { let d = u % (2 * c.L); if (d < 0) d += 2 * c.L; return d > c.L ? -1 : 1; };
  const RT = [0, 0, 0], RN = [0, 0, 0];
  // 러너(또는 dd 만큼 뒤의 동행)의 자리. al = 보간(0 이전 스텝 … 1 지금). 돌려주는 값 = 화면에서 오른쪽(+1)·왼쪽(−1)을 보는지.
  const rpos = (r, al, out, dd = 0) => {
    const c = r.c, u = r.ou + (r.u - r.ou) * al + dd, d = rfold(c, u), dir = rdir(c, u), lat = r.olat + (r.lat - r.olat) * al;
    pointAt(c.pts, c.cum, d, out);
    pointAt(c.pts, c.cum, Math.min(c.L, d + 2), RT); pointAt(c.pts, c.cum, Math.max(0, d - 2), RN);
    let tx = RT[0] - RN[0], ty = RT[1] - RN[1]; const tl = Math.hypot(tx, ty) || 1; tx /= tl; ty /= tl;   // 구간의 앞 방향(달리는 방향과 무관 → 반환점에서 옆자리가 튀지 않는다)
    // 옆으로 비킨 자리가 보도가 아니면(담길이 좁은 곳) 절반만, 그래도 아니면 가운데 줄로
    if (lat) { const bx = out[0], by = out[1]; for (const k of [1, 0.5, 0]) { out[0] = bx - ty * lat * k; out[1] = by + tx * lat * k; if (!k) break; const c = clsAt(out[0], out[1]); if (c === 1 || c === 11) break; } }
    RT[0] = tx * dir; RT[1] = ty * dir; RT[2] = dir;   // 달리는 방향과 부호(호출한 쪽이 바로 읽는다)
    return RT[0] * ex[0] + RT[1] * ex[1] >= 0 ? 1 : -1;
  };
  const RP = [0, 0, 0];
  const latOk = (r) => {
    const c = r.c, d = rfold(c, r.u);
    pointAt(c.pts, c.cum, d, RN); const bx = RN[0], by = RN[1];
    pointAt(c.pts, c.cum, Math.min(c.L, d + 2), RT); const tx0 = RT[0], ty0 = RT[1];
    pointAt(c.pts, c.cum, Math.max(0, d - 2), RT);
    let tx = tx0 - RT[0], ty = ty0 - RT[1]; const tl = Math.hypot(tx, ty) || 1; tx /= tl; ty /= tl;
    const k = clsAt(bx - ty * r.lat, by + tx * r.lat); return k === 1 || k === 11;
  };
  const runFrac = (t) => ((t >= 6 && t < 9) || (t >= 18 && t < 21) ? 1 : t >= 9 && t < 18 ? 0.45 : t >= 21 && t < 23.5 ? 0.22 : t >= 5 && t < 6 ? 0.3 : 0.03);
  const wantR = (r) => r.key < runFrac(E.tod) * (E.rain ? 0.3 : 1) * (E.season === 3 ? 0.65 : 1);
  const stepRunners = (dt, first) => {
    for (const r of runners) {
      r.ou = r.u; r.olat = r.lat;
      const want = wantR(r);
      if (want !== r.vis) { rpos(r, 1, RP); proj.project(RP[0], RP[1], 0, S); if (first || !inView(S[0], S[1], 40)) r.vis = want; }
      if ((stepN + r.id) % 3 === 0) {
        // 앞 3 m 안에 사람이 있으면 옆으로 비키고, 비킬 자리가 보도가 아니면 속도를 줄인다
        r.face = rpos(r, 1, RP);
        const tx = RT[0], ty = RT[1], dn = RT[2], nx = -ty * dn, ny = tx * dn;   // (nx, ny) = 구간 기준 옆 방향(lat 의 + 쪽)
        let side = 0, slow = false;
        const see = (x, y) => { const ax = (x - RP[0]) * tx + (y - RP[1]) * ty; if (ax < 0.3 || ax > 3.2) return; const lx = (x - RP[0]) * nx + (y - RP[1]) * ny; if (Math.abs(lx) < 0.8) side = lx >= 0 ? -1 : 1; };
        for (const i of runNear) if (walkers[i].vis && !walkers[i].run) see(posW[i * 2], posW[i * 2 + 1]);
        for (const g of guests) { see(g.x, g.y); for (const f of g.fol) see(f.x, f.y); }
        // 서 있는 사람·장면 자리(예약된 자리)가 앞길에 있으면 비킨다
        if (!side) for (const ah of [1.2, 2.4]) { const bx = RP[0] + tx * ah, by = RP[1] + ty * ah; if (!free(bx, by, 0.8)) { side = free(bx - nx, by - ny, 0.8) ? -1 : 1; break; } }
        for (const o of runners) if (o !== r && o.vis && o.c === r.c && Math.abs(rfold(o.c, o.u) - rfold(r.c, r.u)) < 3.4 && rdir(o.c, o.u) === dn && o.cv < r.cv) { rpos(o, 1, P3); see(P3[0], P3[1]); }
        const lane = dn * 0.45;   // 오가는 러너끼리는 서로 다른 쪽으로 달린다
        let tgt = lane;
        if (side) { tgt = Math.max(-1.4, Math.min(1.4, r.lat + side * 0.95)); const x = RP[0] + (tgt - r.lat) * nx, y = RP[1] + (tgt - r.lat) * ny, c = clsAt(x, y); if ((c !== 1 && c !== 11) || !free(x, y, 0.9)) { tgt = r.lat; slow = true; } }
        // 담길이 좁은 곳: 무리의 맨 뒤부터 4.6 m 앞까지 그 옆줄이 보도가 아니면 가운데 줄로 모인다
        if (tgt) { const cx0 = RP[0] - r.lat * nx, cy0 = RP[1] - r.lat * ny; for (let ah = -1.7 * r.fol.length - 1; ah <= 4.6; ah += 0.8) { const c = clsAt(cx0 + tx * ah + tgt * nx, cy0 + ty * ah + tgt * ny); if (c !== 1 && c !== 11) { tgt = 0; if (side) slow = true; break; } } }
        if (side) r.hold = 30; else if (r.hold > 0) { r.hold -= 3; tgt = r.latT; }   // 비킨 줄을 1초쯤 지킨다(좌우로 떨지 않게)
        r.latT = tgt; r.slow = slow;
      }
      r.lat += Math.max(-1.1 * dt, Math.min(1.1 * dt, (r.latT - r.lat) * Math.min(1, dt * 3)));   // 옆걸음은 초속 1.1 m 까지
      r.cv += ((r.slow ? r.v * 0.5 : r.v) - r.cv) * Math.min(1, dt * 3);
      r.u += r.cv * dt;
      // 옆자리가 보도 밖이면(담길이 좁아지는 곳) lat 를 스텝당 0.25 m 까지 줄여 보도 안으로 들인다 — rpos 의 대체 규칙(절반·가운데)이 자리를 튀게 하지 않게
      for (let n = 0; n < 5 && r.lat && !latOk(r); n++) r.lat -= Math.sign(r.lat) * Math.min(Math.abs(r.lat), 0.05);
    }
  };
  // ── 자전거(도시 지도): 강변 자전거 띠와 이름 붙은 자전거길(map.json walk_paths 의 「…자전거길」)을 따라 달린다.
  //    혼자 또는 2~3대 무리, 3대 중 1대쯤은 공공자전거(초록 차체). 오른쪽 통행(진행 방향 오른쪽 0.9 m). u = 접지 않고 잰 거리(왕복).
  const bikes = [], bikeChains = [];
  if (city) {
    bikeChains.push(...cityBike);
    for (const w of scene.walkers) if (/자전거/.test(w.name || '') && !bikeChains.some((c) => c.src === w.pts)) { const cum = cumLengths(w.pts); if (cum[cum.length - 1] > 60) bikeChains.push({ pts: w.pts, cum, L: cum[cum.length - 1], src: w.pts }); }
    const total = bikeChains.reduce((a, c) => a + c.L, 0), RIDER = riderPals(cast);
    let id = 0;
    for (const c of bikeChains) {
      const n = Math.max(1, Math.round(BIKE_GROUPS * c.L / total));
      for (let k = 0; k < n; k++, id++) {
        const crew = hash01(id * 41 + 3) < 0.34 ? 1 + Math.floor(hash01(id * 43 + 5) * 2) : 0;
        const look = (h) => ({ fam: 'bike', pal: Math.floor(h * RIDER.length), frame: fr(h * 13) < 0.32 ? 0 : 1 + Math.floor(fr(h * 7) * 5), h, helmet: fr(h * 3) < 0.45 });
        const v = 4 + 2 * hash01(id * 53 + 7);
        bikes.push({ id, c, u: hash01(id * 47 + 1) * 2 * c.L, ou: 0, v, cv: v, lim: v, look: look(hash01(id * 59 + 11)), fol: Array.from({ length: crew }, (_, j) => ({ dd: -(j + 1) * 2.7, look: look(hash01(id * 61 + j * 17 + 3)) })),
          key: crew ? 0.05 + 0.95 * hash01(id * 67 + 2) : hash01(id * 67 + 2), vis: true, dir: 0 });
      }
    }
    for (const b of bikes) b.ou = b.u;
  }
  const BG = Math.hypot(ey[0], ey[1]);
  // 자전거(또는 dd 만큼 뒤의 동행) 자리와 화면 방향: 0 오른쪽, 1 왼쪽, 2 아래(다가옴), 3 위(멀어짐)
  const bpos = (b, al, out, dd = 0) => {
    const c = b.c, u = b.ou + (b.u - b.ou) * al + dd, d = rfold(c, u), dir = rdir(c, u);
    pointAt(c.pts, c.cum, d, out);
    pointAt(c.pts, c.cum, Math.min(c.L, d + 1.5), RT); pointAt(c.pts, c.cum, Math.max(0, d - 1.5), RN);
    let tx = RT[0] - RN[0], ty = RT[1] - RN[1]; const tl = Math.hypot(tx, ty) || 1; tx = tx / tl * dir; ty = ty / tl * dir;
    out[0] += ty * 0.9; out[1] -= tx * 0.9;
    const sx = tx * ex[0] + ty * ex[1], sy = -(tx * ey[0] + ty * ey[1]) / BG;
    return Math.abs(sx) >= Math.abs(sy) * 0.8 ? (sx >= 0 ? 0 : 1) : (sy > 0 ? 2 : 3);
  };
  // 시각별 자전거 비율: 해 질 녘~밤 9시 반에 가장 많고, 아침 출근길에도 조금
  const bikeFrac = (t) => (t >= 18 && t < 21.5 ? 0.95 : t >= 16 && t < 18 ? 0.65 : t >= 7 && t < 9.5 ? 0.45 : t >= 9.5 && t < 16 ? 0.4 : t >= 21.5 && t < 23 ? 0.4 : t >= 5.5 && t < 7 ? 0.2 : 0.05);
  const wantB = (b) => b.key < bikeFrac(E.tod) * (E.rain ? 0.12 : 1) * (E.season === 3 ? 0.35 : E.season === 1 ? 1 : 0.9);
  const BP = [0, 0, 0];
  const stepBikes = (dt, first) => {
    for (const b of bikes) {
      b.ou = b.u;
      const want = wantB(b);
      if (want !== b.vis) { bpos(b, 1, BP); proj.project(BP[0], BP[1], 0, S); if (first || !inView(S[0], S[1], 40)) b.vis = want; }
      if (b.vis && (stepN + b.id) % 3 === 0) {
        // 같은 띠·같은 방향으로 앞서가는 느린 자전거 무리가 가까우면 그 속도에 맞춘다(겹쳐 지나가지 않게)
        let lim = b.v; const d0 = rfold(b.c, b.u), dn = rdir(b.c, b.u);
        for (const o of bikes) {
          if (o === b || !o.vis || o.c !== b.c || rdir(o.c, o.u) !== dn) continue;
          const gap = (rfold(o.c, o.u) - d0) * dn - 2.7 * o.fol.length;
          if (gap > 0 && gap < 5) lim = Math.min(lim, o.cv);
        }
        b.lim = lim;
      }
      b.cv += ((b.vis ? b.lim : b.v) - b.cv) * Math.min(1, dt * 2);
      b.u += b.cv * dt;
    }
  };
  const sideAng = () => Math.atan2(ex[1], ex[0]) + rr(-0.35, 0.35) + (rnd() < 0.5 ? Math.PI : 0);
  const block = (n) => Array.from({ length: n }, (_, k) => (k === 0 ? [0, 0] : [((k - 1) % 2) * 1.2 - 0.6, -1.2 - Math.floor((k - 1) / 2) * 1.15]));
  const ceremony = city ? null : mkCeremony();
  if (city) placeCity();
  else {
  if (opts.birds) { let n = 0; for (const f of opts.birds.flocks) { if (n >= 5) break; if (mkPigeon(f)) n++; } }
  for (const [c, r0, r1, n] of [[A.gate, 14, 55, 3], [A.geun, 14, 50, 2], [A.gyeong, 18, 60, 2], [A.hyang, 8, 50, 2]]) for (let k = 0; k < n; k++) mkPhoto(c, r0, r1, k === 0);
  for (let k = 0; k < 3; k++) mkPhoto(null, 0, 0, false);
  // 광화문 앞(담 밖) 넷: 밤에도 남아 야경을 찍는다
  // 해치 앞 사진 명소: 석상마다 둘(석상 남쪽 앞)
  for (const h of haechi) for (let k = 0; k < 2; k++) { const sc = mkPhoto([h.x, h.y - 5], 1.5, 7, k === 0, false, true); if (sc) { sc.nightKey = rnd() * 0.4; sc.haechi = true; } }
  for (let k = 0; k < 4; k++) { const sc = mkPhoto([A.gate[0], PALACE[1] - 30], 4, 60, false, false, true); if (sc) sc.nightKey = rnd() * 0.25; }
  // 나란히 걷는 일행은 화면 가로 방향(±20°)으로 늘어선다 → 서로 가리지 않는다
  for (const c of [A.geun, A.gate]) {
    const offs = block(8);
    mkTroupe('guide', c, 10, 50, offs.map((off, k) => (k === 0 ? { off, pal: LA(pick(cast.guide), { uniform: true }), prop: 'flag', lag: 0 } : { off, pal: palNormal(), lag: 0.4 + k * 0.25 })),
      { legs: 4, minLeg: 16, maxLeg: 42, gather: true, speed: 1.0, stopT: [9, 16], stop: guideStop });
  }
  for (const c of [A.geun, A.gate, A.gyeong, A.hyang, A.geun, A.gyeong]) {
    const n = 2 + ri(2), ang = sideAng();
    mkTroupe('hanbok', c, 8, 70, Array.from({ length: n }, (_, k) => ({ off: [Math.cos(ang) * k * 1.1, Math.sin(ang) * k * 1.1], pal: LH(), lag: k * 0.2 })),
      { legs: 4, minLeg: 12, maxLeg: 36, speed: 0.9, stopT: [4, 9], stop: hanbokStop });
  }
  mkPhoto(A.geun, 16, 60, false, true); mkPhoto(A.gate, 18, 70, false, true);
  for (const c of [A.gate, A.gyeong, A.hyang, A.sejong, A.bukchon]) {
    const ang = sideAng(), dry = LA(pick(cast.normal)), wet = LA(pick(cast.normal), { noUmb: true });
    dry.h = 0.1;   // 비가 오면 이 사람이 우산을 들고 둘이 같이 쓴다
    mkTroupe('couple', c, 8, 90, [{ off: [0, 0], pal: dry, lag: 0 }, { off: [Math.cos(ang) * 0.8, Math.sin(ang) * 0.8], pal: wet, lag: 0 }],
      { legs: 4, minLeg: 14, maxLeg: 40, speed: 0.85, stopT: [4, 10], stop: coupleStop, gap: 0.75 });
  }
  mkBench(A.gate, 20, 90); mkBench(A.gyeong, 20, 80); mkBench(A.sejong, 5, 120); mkBench(null);
  mkSoap(A.geun, 14, 70); mkSoap(A.gate, 20, 90);
  mkSnow(A.geun, 14, 50); mkSnow(A.gate, 14, 60); mkSnow(null);
  for (let k = 0; k < 8; k++) mkPicnic();
  mkKite(); mkKite(); mkBusker(); mkProposal();
  mkCat(A.seochon); mkCat(A.bukchon); mkCat(A.sejong);
  for (let k = 0; k < 3; k++) mkJogger();
  }
  RR = R1;
  for (const sc of scenes) if (!wants(sc)) setOn(sc, false);
  if (ceremony) ceremony.reset();

  // ── 걷는 사람 세우기(인사·길 묻기·사진 부탁·반려견 만남·탭)
  const meets = [];   // { a, b(없을 수 있음), t, T, kind, tap }
  const posW = new Float32Array(nW * 2);
  const folFx = [];   // 동행(아이·개)의 폴짝·말풍선 타이머
  const folSay = (f, icon, dur = 2, hopT = 0) => { f.bub = icon; if (hopT) f.hop = hopT; folFx.push({ f, t: dur }); };
  const canStand = (x, y) => okPoint(x, y) && free(x, y, 0.95) && guests.every((g) => Math.hypot(g.x - x, g.y - y) >= 0.95);
  const hold = (i) => {
    const w = walkers[i], fol = w.fol.map((f) => { wpos(i, sys.time, P3, f.dd); return { x: P3[0], y: P3[1], look: f.look, hop: 0, bub: 0, sit: false }; });
    wpos(i, sys.time, P3);
    const g = { id: -1 - i, x: P3[0], y: P3[1], z: P3[2], ox: P3[0], oy: P3[1], look: w.look, pose: 'stand', prop: null, bubble: 0, bT: 0, hopT: 0, waveT: 0, on: true, mayHide: false, path: null, wait: 0, moving: false, dist: 0, face: w.dir * w.sx >= 0 ? 1 : -1, wi: i, fol };
    g.zo = P3[2]; lift(g);   // 단 위에서 멈췄으면 그 높이
    ov.skip[i] = 1; guests.push(g);
    return g;
  };
  // 세운 사람의 동행이 설 수 있는 자리인지(다른 사람·예약 자리와 겹치지 않고 보행로 위)
  const folOk = (g) => g.fol.every((f) => cellAt(f.x, f.y) & BIT.PAVE && free(f.x, f.y, 0.7)) && [g, ...g.fol].every((p) => guests.every((o) => o === g || o.fol.includes(p) || [o, ...o.fol].every((q) => q === p || Math.hypot(q.x - p.x, q.y - p.y) >= 0.8)));
  const release = (g) => { ov.skip[g.wi] = 0; cool[g.wi] = 50 + rnd() * 40; guests.splice(guests.indexOf(g), 1); };
  const lookAt = (a, b) => { const sx = (b.x - a.x) * ex[0] + (b.y - a.y) * ex[1]; a.face = sx >= 0 ? 1 : -1; b.face = -a.face; };
  const asker = (t) => t === T.TOURIST || t === T.HIKER;
  // 두 사람의 유형으로 만남의 종류를 고른다. 돌려주는 [종류, 먼저 말 거는 쪽이 i 인가]
  const meetKind = (wi, wj) => {
    const a = wi.type, b = wj.type;
    if (a === T.DOG && b === T.DOG) return ['dogmeet', true];
    if (a === T.DOG && b === T.PARENT && wj.fol[0].look.fam === 'k') return ['kiddog', true];
    if (b === T.DOG && a === T.PARENT && wi.fol[0].look.fam === 'k') return ['kiddog', false];
    if (a === T.TOURIST && b === T.HANBOK) return ['askphoto', true];
    if (b === T.TOURIST && a === T.HANBOK) return ['askphoto', false];
    if (asker(a) !== asker(b) && rnd() < 0.6) return ['ask', asker(a)];
    return ['chat', true];
  };
  const scanMeets = (always = false) => {
    for (let i = 0; i < nW; i++) { wpos(i, sys.time, P3); posW[i * 2] = P3[0]; posW[i * 2 + 1] = P3[1]; }
    if (meets.length >= 12) return;
    for (let k = 0; k < pairs.length; k += 2) {
      const i = pairs[k], j = pairs[k + 1];
      if (ov.skip[i] || ov.skip[j] || cool[i] > 0 || cool[j] > 0 || !walkers[i].vis || !walkers[j].vis || walkers[i].run || walkers[j].run) continue;
      const d = Math.hypot(posW[i * 2] - posW[j * 2], posW[i * 2 + 1] - posW[j * 2 + 1]);
      if (d < 1.0 || d > 1.7) continue;
      if (!okPoint(posW[i * 2], posW[i * 2 + 1]) || !okPoint(posW[j * 2], posW[j * 2 + 1]) || !free(posW[i * 2], posW[i * 2 + 1], 0.95) || !free(posW[j * 2], posW[j * 2 + 1], 0.95)) continue;
      if (guests.some((g) => Math.hypot(g.x - posW[i * 2], g.y - posW[i * 2 + 1]) < 2.6 || Math.hypot(g.x - posW[j * 2], g.y - posW[j * 2 + 1]) < 2.6)) continue;
      // 보이는 곳에서는 조금 더 자주 일어난다
      proj.project(posW[i * 2], posW[i * 2 + 1], 0, S);
      const [kind, first] = meetKind(walkers[i], walkers[j]);
      if (!always && kind !== 'dogmeet' && kind !== 'kiddog' && rnd() > (inView(S[0], S[1]) ? 0.55 : 0.3)) { cool[i] = cool[j] = 4; continue; }
      const a = hold(first ? i : j), b = hold(first ? j : i);
      // 동행끼리 겹치면(같은 자리로 모이는 경로) 그만둔다
      const all = [a, b, ...a.fol, ...b.fol];
      if (all.some((p, pi) => all.some((q, qi) => qi > pi && Math.hypot(p.x - q.x, p.y - q.y) < 0.7)) || !folOk(a) || !folOk(b)) { release(a); release(b); cool[i] = cool[j] = 6; continue; }
      lookAt(a, b);
      meets.push({ a, b, t: 0, T: kind === 'chat' ? rr(6, 13) : kind === 'dogmeet' ? rr(7, 11) : 6.5, ev: 0.9, turn: 0, kind, ph: 0 });
      stats[kind]++; say(a, kind === 'ask' ? BUB.DOTS : BUB.BANG, 0.9);
      if (kind === 'chat' || kind === 'dogmeet') a.waveT = b.waveT = 1.4;
      if (meets.length >= 12) return;
    }
  };
  const stepMeets = (dt) => {
    for (let k = meets.length - 1; k >= 0; k--) {
      const mt = meets[k], { a, b } = mt;
      mt.t += dt;
      if (mt.kind === 'chat' || mt.kind === 'dogmeet' || mt.kind === 'kiddog') {
        if (b && mt.t >= mt.ev && mt.t < mt.T - 1.6) {
          mt.ev = mt.t + rr(1.5, 2.2); mt.turn = 1 - mt.turn;
          say(mt.turn ? b : a, pick([BUB.DOTS, BUB.DOTS, BUB.NOTE, BUB.SMILE, BUB.BANG]), 1.4);
        }
        if (mt.kind === 'dogmeet' && mt.ph === 0 && mt.t > 0.7) { mt.ph = 1; folSay(a.fol[0], BUB.HEART, 2.2, 1.6); }
        if (mt.kind === 'dogmeet' && mt.ph === 1 && mt.t > 4) { mt.ph = 2; folSay(b.fol[0], BUB.NOTE, 1.8, 1.2); }
        if (mt.kind === 'kiddog' && mt.ph === 0 && mt.t > 0.8) { mt.ph = 1; a.fol[0].sit = true; folSay(b.fol[0], BUB.HEART, 2.4, 1.8); }
        if (mt.kind === 'kiddog' && mt.ph === 1 && mt.t > 3.4) { mt.ph = 2; folSay(a.fol[0], BUB.NOTE, 1.8, 1.2); }
        if (b && !mt.bye && mt.t >= mt.T - 1.4) { mt.bye = true; a.waveT = b.waveT = 1.4; a.fol.forEach((f) => { f.sit = false; }); }
      } else if (mt.kind === 'askphoto') {
        // 관광객(a)이 한복 방문객(b)에게 사진을 부탁한다
        if (mt.ph === 0 && mt.t > 1.4) { mt.ph = 1; a.pose = 'cam'; b.pose = 'cheer'; }
        if (mt.ph === 1 && mt.t > 3.1) { mt.ph = 2; flash(a); a.pose = 'stand'; b.pose = 'stand'; }
        if (mt.ph === 2 && mt.t > 3.6) { mt.ph = 3; say(b, BUB.HEART, 1.8); say(a, BUB.SMILE, 1.8); a.waveT = 1.6; }
      } else if (mt.kind === 'ask') {
        // 길 묻기: a 가 묻고(…) b 가 방향을 가리킨다
        if (mt.ph === 0 && mt.t > 1.6) { mt.ph = 1; b.pose = 'point'; b.face = rnd() < 0.5 ? 1 : -1; say(b, BUB.DOTS, 1.6); }
        if (mt.ph === 1 && mt.t > 3.8) { mt.ph = 2; b.pose = 'stand'; say(a, BUB.SMILE, 1.6); a.waveT = 1.4; }
      }
      if (mt.t >= mt.T) { release(a); if (b) release(b); meets.splice(k, 1); }
    }
  };
  // 반응: 손 흔들기 + 말풍선 + 폴짝
  const react = (a) => { const pet = a.look.fam === 'cat' || a.look.fam === 'dog'; a.waveT = 2.2; hop(a, 1.2); say(a, pet ? BUB.HEART : pick([BUB.HEART, BUB.NOTE, BUB.SMILE]), 2.2); };

  // ── 시간대·날씨에 따라 나오고 들어가기. 화면 밖(또는 사람이 점으로 보일 만큼 멀리서 볼 때)에서만 바뀐다.
  // 도시 지도: 동네별 시각 곡선(시작 시각, 비율 — 다음 시작까지) × 계절 × 비 × 유형. key < 비율이면 나온다.
  //   공원 k 는 낮에 많고 밤엔 한산, 강변 r 은 여름 저녁에 가장 붐비고, 업무지구 b 는 출근·점심·퇴근 때 몰린다.
  const ZF = {
    k: [[0, 0.03], [5.5, 0.2], [7, 0.35], [9, 0.5], [11, 0.75], [14, 0.85], [18, 0.75], [21, 0.32], [23, 0.07]],
    r: [[0, 0.05], [5, 0.3], [7, 0.4], [10, 0.45], [16, 0.65], [18, 0.92], [21.5, 0.5], [23.5, 0.08]],
    b: [[0, 0.04], [6, 0.2], [7.3, 0.95], [9.3, 0.35], [11.4, 0.92], [13.2, 0.35], [17.5, 0.92], [19.5, 0.35], [22, 0.08]],
    a: [[0, 0.03], [8, 0.3], [9.5, 0.6], [17.5, 0.3], [20, 0.05]],
    s: [[0, 0.06], [6, 0.35], [8, 0.65], [21, 0.3], [23, 0.08]],
  };
  const zf = (z, t) => { let v = ZF[z][0][1]; for (const [h, f] of ZF[z]) if (t >= h) v = f; return v; };
  const cityFrac = (w) => {
    const t = E.tod, z = w.zone, ty = w.type, s = E.season;
    let f = ty === T.OFFICE && z !== 'b' && z !== 'a' ? zf('b', t) * 0.6 : zf(z, t);
    if (s === 3) f *= { k: 0.45, r: 0.35, b: 0.95, a: 0.7, s: 0.8 }[z];
    else if (s === 1 && (z === 'r' || z === 'k')) f *= t >= 17 && t < 22 ? 1.1 : t >= 11 && t < 16 ? 0.6 : 1;
    else if (z === 'r' || z === 'k') f *= 1.05;
    if (E.rain) f *= ty === T.OFFICE ? 0.8 : 0.3;
    switch (ty) {
      case T.JOGGER: f *= E.rain ? 0 : ((t >= 5.5 && t < 9.5) || (t >= 17 && t < 22) ? 1 : t >= 9.5 && t < 17 ? 0.35 : 0.1) * (s === 3 ? 0.5 : 1); break;
      case T.PARENT: case T.STROLLER: if (t < 9 || t >= 20.5) f = 0; break;
      case T.ELDER: if (t < 6 || t >= 19.5) f = 0; break;
      case T.DOG: if (t < 6 || t >= 23) f *= 0.2; break;
      case T.STUDENT: if (t < 7 || t >= 22) f = 0; break;
      case T.CLEANER: f = t >= 5 && t < 10 ? 1 : 0.3; break;
      case T.TOURIST: if (t < 8.5 || t >= 22) f = 0; break;
      default: break;
    }
    return Math.min(1, f);
  };
  const wantCity = (w) => w.key < cityFrac(w);
  const wantW = (w) => {
    if (city) return wantCity(w);
    if (w.night > E.keep) return false;
    const t = E.tod, k = w.key;
    if (E.rain && k > 0.62 && w.type !== T.OFFICE) return false;
    if (E.season === 3 && k < 0.12) return false;
    if (w.zone === 'p' && (t < PAL_OPEN[0] || t >= PAL_OPEN[1])) return false;        // 궁궐 관람 시간 밖에는 궁 안에 아무도 없다
    switch (w.type) {
      case T.OFFICE: return (t >= 7 && t < 9.7) || (t >= 17.3 && t < 20.5) || k < 0.3;
      case T.STUDENT: return (t >= 7.3 && t < 9) || (t >= 14.5 && t < 18.5) || (k < 0.25 && t > 7 && t < 22);
      case T.HIKER: return t >= 6 && t < 17.5;
      case T.JOGGER: return !E.rain && E.season !== 3 && ((t >= 5.5 && t < 9.5) || (t >= 17 && t < 21.5) || k < 0.2);
      case T.ELDER: return t >= 6 && t < 19.5;
      case T.PARENT: case T.STROLLER: return t >= 8.5 && t < 20;
      case T.CLEANER: return (t >= 5 && t < 9) || k < 0.5;
      case T.DOG: return t >= 6 && t < 23;
      case T.STAFF: return t >= 8.5 && t < 18.5;
      default: return true;
    }
  };
  const wantS = (s) => !s.bad && s.night <= E.keep && !(E.rain && s.key > 0.6) && !(s.zone === 'p' && (E.tod < PAL_OPEN[0] || E.tod >= PAL_OPEN[1]));
  let cursor = 0;
  const flipSome = (n, free2) => {
    const tot = nW + standing.length;
    for (let c = 0; c < n; c++) {
      const i = cursor++ % tot;
      if (i < nW) {
        const w = walkers[i], want = wantW(w);
        if (want === w.vis || ov.skip[i]) continue;
        if (!free2) { wpos(i, sys.time, P3); proj.project(P3[0], P3[1], 0, S); if (inView(S[0], S[1])) continue; }
        w.vis = want;
      } else {
        const s = standing[i - nW], want = wantS(s);
        if (s.tourist) s.pose = hash01((i - nW) * 7 + Math.floor(sys.time / 5)) < 0.12 ? 'cam' : 'stand';
        if (want === s.vis) continue;
        if (!free2) { proj.project(s.x, s.y, 0, S); if (inView(S[0], S[1])) continue; }
        s.vis = want;
      }
    }
  };
  // ── 연출: 몇 초마다 쉬고 있는 장면 하나를 일으킨다. 보이는 곳에 있는 장면을 더 자주 고른다 → 「기다리면 뭔가 일어난다」
  let dirT = 5;
  const director = (dt) => {
    if ((dirT -= dt) > 0) return;
    dirT = rr(5, 9);
    let best = null, bw = 0;
    for (const sc of scenes) {
      if (!sc.on || sc.st !== 'idle' || !sc.nudge) continue;
      const a0 = sc.actors[0];
      proj.project(a0.x, a0.y, 0, S);
      const w = (inView(S[0], S[1], -10) ? 5 : 1) * rnd();
      if (w > bw) { bw = w; best = sc; }
    }
    if (best) best.nudge();
  };
  // 찾아보기 목록의 열쇠: 장면 종류 → 지금 「보인 것」으로 칠 조건
  const SPOT = {
    hanbok: () => 'hanbok', guide: () => 'guide', bench: () => 'bench', picnic: () => 'picnic', snow: () => 'snow', kite: () => 'kite', soap: () => 'soap', cat: () => 'cat',
    ceremony: (sc) => sc.st !== 'idle' && 'ceremony', classphoto: (sc) => sc.st !== 'idle' && 'classphoto', photo: (sc) => sc.st !== 'idle' && E.day < 0.3 && 'nightphoto',
    pigeon: (sc) => (sc.st === 'run' || sc.st === 'cheer') && 'pigeon', busk: (sc) => sc.st === 'play' && 'busk', proposal: (sc) => sc.st === 'ask' && 'proposal', couple: () => E.rain && 'share',
    ball: () => 'ball', fish: () => 'fish', splash: () => 'splash', lunch: () => 'lunch',
  };

  let stepN = 0;
  const sys = {
    haechi, runners, runChains, rpos, runFrac, bikes, bikeChains, bpos, city, cityGeo: city ? { run: cityRun, bike: cityBike, side: citySide, prom: cityProm } : null, isleN: () => isleN, dWater, toPx: (x, y) => { proj.project(x, y, 0, S); return [S[0], S[1]]; },
    time: 0, rainT: 0, actors, guests, scenes, props, fx, floaters, walkers, standing, ov, stats, wpos, toWorld, env: E, ceremony, cast, clsAt, zAt, hrAt, platCells, hidden, inPalace, pairCount: pairs.length / 2,
    wdir: (i) => walkers[i].dir,
    step(dt, env = {}) {
      sys.time += dt; stepN++;
      E.prevTod = E.tod; E.tod = (((env.tod ?? 12) % 24) + 24) % 24; { const dh = (E.tod - E.prevTod + 24) % 24; E.rate = dt > 0 && dh < 1 ? dh / dt : 0; }
      E.day = env.day ?? dayOf(E.tod); E.keep = 1 - (1 - E.day) * 0.72;
      E.season = env.season ?? 1; E.rain = (env.rain || 0) > 0.5; E.view = env.view || null;
      sys.rainT = E.rain ? sys.rainT + dt : 0;
      if (stepN === 1) flipSome(nW + standing.length, true); else flipSome(48, false);
      for (const g of guests) ov.off[g.wi] += dt;
      if (stepN % 9 === 0) { for (let i = 0; i < nW; i++) if (cool[i] > 0) cool[i] -= dt * 9; scanMeets(); }
      stepMeets(dt);
      director(dt);
      for (const sc of scenes) {
        const want = wants(sc);
        if (want !== sc.on && (stepN === 1 || canFlip(sc))) setOn(sc, want);
        if (sc.on) sc.step(dt);
      }
      stepRunners(dt, stepN === 1);
      if (city) stepBikes(dt, stepN === 1);
      for (const a of actors) if (a.on) stepActor(a, dt);
      for (const g of guests) stepActor(g, dt);
      for (let k = folFx.length - 1; k >= 0; k--) { const e = folFx[k]; if (e.f.hop > 0) e.f.hop = Math.max(0, e.f.hop - dt); if ((e.t -= dt) <= 0) { e.f.bub = 0; e.f.hop = 0; folFx.splice(k, 1); } }
      for (let k = fx.length - 1; k >= 0; k--) if ((fx[k].t += dt) >= fx[k].T) fx.splice(k, 1);
      for (let k = floaters.length - 1; k >= 0; k--) if ((floaters[k].t -= dt) <= 0) floaters.splice(k, 1);
    },
    // 탭: 지도 px (x, y) 근처(r px)의 사람이 손을 흔든다. 누가 반응했는지 돌려준다(없으면 null): { actor } 또는 { wi }(걷는 사람). locate 로 따라갈 수 있다.
    tap(x, y, r = 4) {
      let best = null, bd = r, bw = -1, bf = null;
      const test = (wx, wy, wz) => { proj.project(wx, wy, wz, S); return Math.hypot(S[0] - x, (S[1] - 2 - y) * 0.6); };
      for (const a of actors) { if (!a.on) continue; const d = test(a.x, a.y, a.z); if (d < bd) { bd = d; best = a; } }
      for (const g of guests) { const d = test(g.x, g.y, g.z); if (d < bd) { bd = d; best = g; } }
      for (let i = 0; i < nW; i++) {
        const w = walkers[i];
        if (ov.skip[i] || !w.vis) continue;
        wpos(i, sys.time, P3);
        let d = test(P3[0], P3[1], P3[2]);
        if (Math.abs(S[0] - x) > r + 6) continue;
        if (d < bd) { bd = d; best = null; bw = i; bf = null; }
        for (const f of w.fol) { wpos(i, sys.time, P3, f.dd); d = test(P3[0], P3[1], P3[2]) + 0.01; if (d < bd) { bd = d; best = null; bw = i; bf = f; } }
      }
      if (best) { react(best); stats.tap++; return best.wi >= 0 ? { wi: best.wi } : { actor: best }; }
      if (bw < 0) return null;
      stats.tap++;
      if (bf) { folSay(bf, bf.look.fam === 'dog' ? BUB.HEART : pick([BUB.HEART, BUB.NOTE, BUB.SMILE]), 2.2, 1.6); return { wi: bw }; }
      wpos(bw, sys.time, P3);
      if (canStand(P3[0], P3[1])) {
        const g = hold(bw);
        if (folOk(g)) { react(g); meets.push({ a: g, b: null, t: 0, T: 2.4, tap: true, kind: 'tap' }); return { wi: bw }; }
        release(g); cool[bw] = 0;
      }
      // 설 수 없는 자리(차도를 건너는 중 등)면 걸어가면서 말풍선만
      floaters.push({ wi: bw, icon: pick([BUB.HEART, BUB.NOTE, BUB.SMILE]), t: 2 });
      return { wi: bw, floating: true };
    },
    // 따라가기용: tap 이 돌려준 대상의 지금 위치(지도 px). 사라졌으면(밤에 들어감 등) null.
    locate(ref, t = sys.time, out = [0, 0]) {
      if (!ref) return null;
      if (ref.actor) { if (!ref.actor.on) return null; proj.project(ref.actor.x, ref.actor.y, 0, S); }
      else { if (!walkers[ref.wi] || !walkers[ref.wi].vis) return null; wpos(ref.wi, t, P3); proj.project(P3[0], P3[1], P3[2], S); }
      out[0] = S[0]; out[1] = S[1] - 2;
      return out;
    },
    // 찾아보기: 가까이서 보고 있는 화면(v = [x0, y0, x1, y1] 지도 px, 폭 460 px 이하)에 들어온 장면의 열쇠 목록
    spot(v, out = []) {
      if (!v || v[2] - v[0] > 460) return out;
      const inV = (wx, wy) => { proj.project(wx, wy, 0, S); return S[0] > v[0] + 8 && S[0] < v[2] - 8 && S[1] > v[1] + 8 && S[1] < v[3] - 8; };
      for (const sc of scenes) {
        if (!sc.on || !SPOT[sc.kind] || !inV(sc.actors[0].x, sc.actors[0].y) || hidden(sc.actors[0].x, sc.actors[0].y)) continue;
        const k = SPOT[sc.kind](sc);
        if (k && !out.includes(k)) out.push(k);
      }
      for (const h of haechi) if (inV(h.x, h.y) && !out.includes('haechi')) out.push('haechi');
      for (const mt of meets) { const k = mt.kind === 'kiddog' ? 'dogmeet' : mt.kind; if ((k === 'dogmeet' || k === 'askphoto') && inV(mt.a.x, mt.a.y) && !out.includes(k)) out.push(k); }
      if (city) {
        for (const b of bikes) if (b.vis && b.fol.length && !out.includes('bikecrew')) { bpos(b, 1, BP); if (inV(BP[0], BP[1]) && !hidden(BP[0], BP[1])) out.push('bikecrew'); }
        for (const r of runners) if (r.vis && r.fol.length >= 2 && !out.includes('runcrew')) { rpos(r, 1, BP); if (inV(BP[0], BP[1]) && !hidden(BP[0], BP[1])) out.push('runcrew'); }
      }
      return out;
    },
    // 궁 안 방문객 구성(수문장·안내원·동물 제외). test 와 조정용.
    census() {
      let v = 0, hb = 0;
      const add = (L) => { if (L.fam === 'g' || L.uniform || L.fam === 'cat' || L.fam === 'dog' || L.fam === 'stroller') return; v++; if (isHanbok(L)) hb++; };
      for (const w of walkers) if (w.vis && w.zone === 'p') { add(w.look); for (const f of w.fol) add(f.look); }
      for (const s of standing) if (s.vis && s.zone === 'p') add(s.look);
      for (const a of actors) if (a.on && !a.mayHide && inPalace(a.x, a.y)) add(a.look);
      return { visitors: v, hanbok: hb, ratio: v ? hb / v : 0 };
    },
    // 캡처·테스트용: 장면을 바로 일으킨다 / 장면 위치(지도 px)를 찾는다
    force(kind, n = 0) {
      const sc = scenes.filter((s) => s.kind === kind)[n];
      if (!sc) return null;
      if (!sc.on) setOn(sc, true);
      if (sc.st === 'idle') { if (kind === 'ceremony') { sc.cool = 0; sc.start(); } else if (sc.shoot) sc.shoot(); else if (sc.run) sc.run(); else if (sc.ask) sc.ask(); else if (sc.play) sc.play(); else sc.T = 0; }
      const c = sc.C || [sc.actors[0].x, sc.actors[0].y];
      proj.project(c[0], c[1], 0, S);
      return { x: S[0], y: S[1] };
    },
    forceChat(kind) {
      const n = meets.length; cool.fill(0);
      if (!kind) scanMeets(true);
      else {
        // 그 종류의 만남이 될 수 있는 쌍을 찾아 지금 마주 세운다(캡처용. 걷던 자리에서 옮기지는 않는다 → 가까운 쌍만)
        for (let k = 0; k < pairs.length && meets.length === n; k += 2) {
          const i = pairs[k], j = pairs[k + 1];
          if (ov.skip[i] || ov.skip[j] || meetKind(walkers[i], walkers[j])[0] !== kind) continue;
          wpos(i, sys.time, P3); const xi = P3[0], yi = P3[1]; wpos(j, sys.time, P3);
          const d = Math.hypot(xi - P3[0], yi - P3[1]);
          if (d < 1.0 || d > 2.4 || !okPoint(xi, yi) || !okPoint(P3[0], P3[1])) continue;
          const [, first] = meetKind(walkers[i], walkers[j]);
          walkers[i].vis = walkers[j].vis = true;
          const a = hold(first ? i : j), b = hold(first ? j : i);
          lookAt(a, b); meets.push({ a, b, t: 0, T: 7, ev: 0.9, turn: 0, kind, ph: 0 }); stats[kind]++; say(a, BUB.BANG, 0.9);
        }
      }
      return meets.slice(n).map((mt) => { proj.project(mt.a.x, mt.a.y, 0, S); return { x: S[0], y: S[1], kind: mt.kind }; });
    },
    // 지금 나와 있는 사람·자전거 수(동행 포함). v = [x0, y0, x1, y1] 지도 px 를 주면 그 안만(가려진 자리 포함). 측정·테스트용.
    counts(v = null) {
      const inV = (x, y, z = 0) => { if (!v) return true; proj.project(x, y, z, S); return S[0] >= v[0] && S[0] < v[2] && S[1] >= v[1] && S[1] < v[3]; };
      const o = { walkers: 0, actors: 0, runners: 0, bikes: 0 };
      walkers.forEach((w, i) => { if (!w.vis || ov.skip[i]) return; wpos(i, sys.time, P3); if (inV(P3[0], P3[1])) o.walkers += 1 + w.fol.length; });
      for (const a of actors) if (a.on && inV(a.x, a.y)) o.actors++;
      for (const g of guests) if (inV(g.x, g.y)) o.actors += 1 + g.fol.length;
      for (const r of runners) if (r.vis) { rpos(r, 1, P3); if (inV(P3[0], P3[1])) o.runners += 1 + r.fol.length; }
      for (const b of bikes) if (b.vis) { bpos(b, 1, P3); if (inV(P3[0], P3[1])) o.bikes += 1 + b.fol.length; }
      o.people = o.walkers + o.actors + o.runners;
      return o;
    },
    find(kind) { return scenes.filter((s) => s.kind === kind).map((s) => { proj.project(s.actors[0].x, s.actors[0].y, 0, S); return { x: S[0], y: S[1], on: s.on, st: s.st }; }); },
    // 유형별로 지금 보이는 걷는 사람의 위치(지도 px). 캡처용.
    findType(type, zone) { const out = []; walkers.forEach((w, i) => { if (w.type === type && w.vis && (!zone || w.zone === zone)) { wpos(i, sys.time, P3); if (!hidden(P3[0], P3[1])) { proj.project(P3[0], P3[1], 0, S); out.push({ x: S[0], y: S[1], wi: i }); } } }); return out; },
    meets,
    snapshot() {
      return { ...(city ? { bikes: bikes.map((b) => [b.vis ? 1 : 0, +b.u.toFixed(4)]) } : {}), runners: runners.map((r) => [r.vis ? 1 : 0, r.u, r.lat, r.hold]), time: sys.time, stats: { ...stats }, rs: R1.rs, off: Array.from(ov.off), vis: walkers.map((w) => (w.vis ? 1 : 0)).join(''), actors: actors.map((a) => [a.on ? 1 : 0, a.x, a.y, a.pose, a.bubble]), guests: guests.map((g) => [g.wi, g.x, g.y, g.bubble]), scenes: scenes.map((s) => [s.on ? 1 : 0, s.st]) };
    },
  };
  return sys;
}
