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

// grid = { w, h, cls } (지도 px, 0.5 m). opts: { seed, birds(새 시스템, 아이·비둘기 장면용), heightAt(px, py) → 지면(z=0) 대비 높이 m(브라우저에서만) }
export function createPeople(scene, grid, opts = {}) {
  const seed = opts.seed ?? 5;
  const cast = addCast(scene);
  const proj = opts.proj || makeProjection(scene.camera);
  const { ex, ey, m } = proj;
  const det = ex[0] * ey[1] - ex[1] * ey[0];
  const S = [0, 0, 0], P3 = [0, 0, 0], Q2 = [0, 0];
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
  const mw = grid.w >> 1, mh = grid.h >> 1, walk = new Uint8Array(mw * mh);
  {
    const { w, cls } = grid, hAt = opts.heightAt;
    const kind = (c) => (c === 5 || c === 11 ? BIT.PAVE : c === 3 ? BIT.GRASS : c === 1 ? BIT.DIRT : 0);
    for (let cy = 4; cy < mh - 4; cy++) for (let cx = 4; cx < mw - 4; cx++) {
      const o = cy * 2 * w + cx * 2;
      const k = kind(cls[o]);
      if (!k || kind(cls[o + 1]) !== k || kind(cls[o + w]) !== k || kind(cls[o + w + 1]) !== k) continue;
      if (hAt && (Math.abs(hAt(cx * 2, cy * 2)) > 0.3 || Math.abs(hAt(cx * 2 + 1, cy * 2 + 1)) > 0.3)) continue;
      walk[cy * mw + cx] = k;
    }
  }
  const cellAt = (x, y) => { proj.project(x, y, 0, S); const cx = S[0] >> 1, cy = S[1] >> 1; return cx < 0 || cy < 0 || cx >= mw || cy >= mh ? 0 : walk[cy * mw + cx]; };
  const clsAt = (x, y) => { proj.project(x, y, 0, S); const px = Math.floor(S[0]), py = Math.floor(S[1]); return px < 0 || py < 0 || px >= grid.w || py >= grid.h ? 0 : grid.cls[py * grid.w + px]; };
  // 발 픽셀이 건물·나무에 가려진 자리(말풍선을 띄우지 않는다)
  const hidden = (x, y) => { const c = clsAt(x, y); return c === 6 || c === 7 || c === 8 || c === 9 || c === 10; };
  // 설 수 있는 자리: 주변 3×3 칸(±1 m)이 모두 허용 종류
  const okPoint = (x, y, bits = BIT.PAVE) => {
    proj.project(x, y, 0, S);
    const cx = S[0] >> 1, cy = S[1] >> 1;
    if (cx < 1 || cy < 1 || cx >= mw - 1 || cy >= mh - 1) return false;
    for (let j = -1; j <= 1; j++) for (let i = -1; i <= 1; i++) if (!(walk[(cy + j) * mw + cx + i] & bits)) return false;
    return true;
  };
  const okLine = (x0, y0, x1, y1, bits = BIT.PAVE) => {
    const n = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0) / 0.4));
    for (let k = 0; k <= n; k++) if (!(cellAt(x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n) & bits)) return false;
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
  const groupOk = (pts, bits = BIT.PAVE, gap = 1.0) => pts.every((p, i) => tryPt(p[0], p[1], bits) && pts.every((q, j) => j <= i || Math.hypot(p[0] - q[0], p[1] - q[1]) >= gap));
  const anchor = (px, py) => toWorld(px, py, [0, 0]);
  // 좌표는 tour.js PLACES 의 지도 px(건물 가운데쯤). 실제 자리는 이 둘레에서 클래스 맵으로 찾는다.
  const A = { gate: anchor(850, 1225), geun: anchor(1215, 985), gyeong: anchor(1275, 800), hyang: anchor(1830, 650), seochon: anchor(640, 520), bukchon: anchor(2250, 980), sejong: anchor(330, 1230) };
  const PALACE = [-258.6, 12.2, 297.3, 878.1];   // 궁궐 담 안쪽을 덮는 상자(로컬 m, main.js env.palace 와 같은 값)
  const inBox = (x, y) => x >= PALACE[0] && x <= PALACE[2] && y >= PALACE[1] && y <= PALACE[3];
  const inPalace = (x, y) => { if (x < PALACE[0] || x > PALACE[2] || y < PALACE[1] || y > PALACE[3]) return false; const c = clsAt(x, y); return c === 5 || c === 8 || c === 9; };

  // ── 걷는 사람: 경로를 왕복(닫힌 식: 위상 + 시간 × 속도 − 누적 정지 시간). 유형·동행은 번호 해시와 경로 위치로 정한다(고정).
  const walkers = [];
  scene.walkers.forEach((w, i) => {
    const cum = cumLengths(w.pts), L = cum[cum.length - 1];
    if (!(L > 1)) return;
    const h1 = hash01(i * 19 + 2), h2 = hash01(i * 23 + 7), h3 = hash01(i * 29 + 13), h4 = hash01(i * 31 + 3);
    let nPal = 0;
    for (let k = 0; k <= 4; k++) { pointAt(w.pts, cum, L * k / 4, P3); if (inPalace(P3[0], P3[1])) nPal++; }
    pointAt(w.pts, cum, L / 2, P3);
    const mx = P3[0], my = P3[1], zone = nPal >= 3 ? 'p' : 's';
    const dTo = (a) => Math.hypot(mx - a[0], my - a[1]);
    const near = Math.min(dTo(A.gate), dTo(A.seochon), dTo(A.bukchon)) < 230, biz = dTo(A.sejong) < 320;
    const pal0 = scene.walker_pal_idx[i], pk = (arr, h) => arr[Math.floor(h * arr.length)];
    const hat = (p) => (h3 < p ? 1 + Math.floor(h4 * 8) : 0), bag = (p) => (fr(h3 * 7) < p ? 1 + Math.floor(h4 * 4) : 0);
    const hb = () => (h2 < 0.72 ? LK('hf', Math.floor(h3 * 14), h4) : LK('hm', Math.floor(h3 * 6), h4));
    let type = T.NORMAL, look = LK('a', pal0, h4), fol = [];
    const F = (dd, lk) => fol.push({ dd, ox: 0, oy: 0, look: lk, hop: 0, bub: 0 });
    const cum2 = (list) => { let a = 0; for (const [p, t] of list) { a += p; if (h1 < a) return t; } return T.NORMAL; };
    type = zone === 'p'
      ? cum2([[HANBOK.palace, T.HANBOK], [0.30, T.TOURIST], [0.09, T.PARENT], [0.05, T.ELDER], [0.03, T.STUDENT], [0.02, T.STROLLER], [0.02, T.WHEEL], [0.02, T.STAFF]])
      : cum2([[near ? HANBOK.near : HANBOK.city, T.HANBOK], [biz ? 0.3 : 0.15, T.OFFICE], [0.07, T.STUDENT], [0.08, T.ELDER], [near ? 0.14 : 0.06, T.TOURIST], [0.04, T.HIKER], [0.06, T.DOG], [0.05, T.PARENT], [0.02, T.STROLLER], [0.012, T.WHEEL], [0.015, T.CLEANER], [0.025, T.JOGGER]]);
    if (type === T.HANBOK) { look = hb(); if (fr(h2 * 9) < 0.4) F(-1.0, fr(h2 * 31) < 0.7 ? LK('hf', Math.floor(fr(h3 * 17) * 14), fr(h4 * 3)) : LK('hm', Math.floor(fr(h3 * 17) * 6), fr(h4 * 3))); }
    else if (type === T.OFFICE) look = LK('a', pk(cast.office, h2), h4);
    else if (type === T.STUDENT) { look = LK('a', pk(cast.student, h2), h4, { bag: bag(0.6) }); if (h3 < 0.5) for (let k = 1; k <= 1 + Math.floor(h4 * 3); k++) F(-0.95 * k, LK('a', pk(cast.student, fr(h2 * (k + 3))), fr(h4 * (k + 2)), { bag: k & 1 ? 1 + (k % 4) : 0 })); }
    else if (type === T.ELDER) look = LK('a', pk(cast.elder, h2), h4, { cane: h3 < 0.6 ? 1 : 0, hat: h3 > 0.8 ? 6 : 0 });
    else if (type === T.TOURIST) { look = LK('a', pal0, h4, { hat: hat(0.6), bag: bag(0.45) }); if (fr(h2 * 9) < 0.25) F(-1.0, LK('a', pk(cast.normal, fr(h2 * 5)), fr(h4 * 5), { hat: fr(h3 * 3) < 0.5 ? 1 + Math.floor(fr(h4 * 9) * 8) : 0 })); }
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
    walkers.push({ pts: w.pts, cum, L, speed: w.speed_mps * (0.85 + 0.3 * hash01(i * 7 + 1)) * SPEED[type], phase: hash01(i * 13 + 5) * 2 * L, pal: look.pal, night: hash01(i * 3 + 11),
      type, zone, look, fol, vis: true, key: hash01(i * 37 + 9), run: type === T.JOGGER, bub: 0, sx: (b[0] - a[0]) * ex[0] + (b[1] - a[1]) * ex[1] >= 0 ? 1 : -1, dir: 1 });
  });
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
  const standing = scene.standing.map((s, i) => {
    const h1 = hash01(i * 41 + 5), h2 = hash01(i * 43 + 1), h3 = hash01(i * 47 + 9), pal = inPalace(s.x, s.y);
    const bad = clsAt(s.x, s.y) === 2;
    if (bad) ov.skipS[i] = 1; else claim(s.x, s.y);
    const look = pal && h1 < HANBOK.palace ? (h2 < 0.72 ? LK('hf', Math.floor(h3 * 14), h2) : LK('hm', Math.floor(h3 * 6), h2))
      : LK('a', s.pal, h2, h1 < 0.6 ? { hat: h3 < 0.5 ? 1 + Math.floor(h2 * 8) : 0, bag: h3 > 0.7 ? 1 + Math.floor(h2 * 4) : 0 } : {});
    return { x: s.x, y: s.y, z: s.z || 0, look, pose: 'stand', face: h3 < 0.5 ? 1 : -1, bub: 0, vis: !bad, bad, zone: pal ? 'p' : 's', night: hash01(i * 5 + 3), key: h1, tourist: look.fam === 'a' && h1 < 0.6 };
  });

  // 마주칠 수 있는 쌍: 경로끼리 1.3 m 안으로 지나가는 곳이 있는 두 사람. 시작할 때 한 번만 센다.
  const pairs = [];
  {
    const bb = walkers.map((w) => { let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9; for (const p of w.pts) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]); } return [x0, x1, y0, y1]; });
    const segD = (px, py, a, b) => { const dx = b[0] - a[0], dy = b[1] - a[1], t = Math.max(0, Math.min(1, ((px - a[0]) * dx + (py - a[1]) * dy) / (dx * dx + dy * dy || 1))); return Math.hypot(px - a[0] - dx * t, py - a[1] - dy * t); };
    const order = walkers.map((_, i) => i).sort((a, b) => bb[a][0] - bb[b][0]);
    for (let oi = 0; oi < nW; oi++) {
      const i = order[oi], A2 = bb[i], wi = walkers[i];
      for (let oj = oi + 1; oj < nW; oj++) {
        const j = order[oj], B = bb[j];
        if (B[0] > A2[1] + 1.3) break;
        if (B[2] > A2[3] + 1.3 || B[3] < A2[2] - 1.3) continue;
        const wj = walkers[j];
        let nearP = false;
        for (let d = 0; d <= wi.L && !nearP; d += 0.6) {
          pointAt(wi.pts, wi.cum, d, P3);
          for (let k = 1; k < wj.pts.length; k++) if (segD(P3[0], P3[1], wj.pts[k - 1], wj.pts[k]) < 1.3) { nearP = true; break; }
        }
        if (nearP) pairs.push(Math.min(i, j), Math.max(i, j));
      }
    }
  }

  // ── 출연진
  const actors = [], guests = [], scenes = [], props = [], fx = [], floaters = [];
  const stats = { chat: 0, ask: 0, askphoto: 0, dogmeet: 0, kiddog: 0, tap: 0, photo: 0, nightphoto: 0, classphoto: 0, guide: 0, hanbok: 0, couple: 0, share: 0, pigeon: 0, picnic: 0, bench: 0, jog: 0, ceremony: 0, snow: 0, cat: 0, busk: 0, proposal: 0, kite: 0, soap: 0 };
  // look = 겉모습(LK). pose: stand·wave·cam·cheer·point·sit·kneel·run. prop: flag·banner·spear·guitar.
  const mk = (x, y, look, o = {}) => {
    const a = { id: actors.length, x, y, z: 0, ox: x, oy: y, hx: x, hy: y, look, pose: 'stand', prop: null, bubble: 0, bT: 0, hopT: 0, waveT: 0, on: true,
      mayHide: false, path: null, pi: 0, wait: 0, speed: 1.2, dist: 0, moving: false, face: 1, wi: -1, ...o };
    actors.push(a);
    return a;
  };
  const say = (a, icon, dur = 1.8) => { a.bubble = icon; a.bT = dur; };
  const hop = (a, dur = 1) => { a.hopT = dur; };
  const go = (a, pts, speed, delay = 0) => { a.path = pts; a.pi = 0; a.speed = speed; a.wait = delay; };
  const idle = (a) => !a.path && a.wait <= 0;
  const flash = (a) => fx.push({ type: 'flash', x: a.x, y: a.y, z: 1.55, t: 0, T: 0.16 });
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
      inPal: kind !== 'ceremony' && c[0] >= PALACE[0] && c[0] <= PALACE[2] && c[1] >= PALACE[1] && c[1] <= PALACE[3] });
    scenes.push(sc);
    return sc;
  };
  // 궁 안 장면은 관람 시간(9~18시)에만. 수문장 교대(pin)는 제 시각 규칙을 따른다.
  const palOpen = () => E.tod >= PAL_OPEN[0] && E.tod < PAL_OPEN[1];
  const wants = (sc) => sc.want() && (!sc.inPal || palOpen());
  const setOn = (sc, on) => {
    sc.on = on;
    for (const a of sc.actors) {
      a.on = on; a.x = a.ox = a.hx; a.y = a.oy = a.hy; a.path = null; a.wait = 0; a.bubble = 0; a.bT = 0; a.hopT = 0; a.pose = a.pose0 || 'stand';
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
        guards.forEach((g, k) => { g.on = true; g.x = g.ox = colH[k][0]; g.y = g.oy = colH[k][1]; go(g, [colC[k]], sc.v, -cols[k][1] / sc.v); });
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
    const offs = members.map((mb) => mb.off), gap = o.gap || 1.0;
    const shifted = (p) => offs.map((f) => [p[0] + f[0], p[1] + f[1]]);
    for (let tries = 0; tries < 60; tries++) {
      const p0 = polar(c, r0, r1);
      if (!groupOk(shifted(p0), BIT.PAVE, gap)) continue;
      const route = [p0];
      for (let leg = 0; leg < o.legs; leg++) {
        const p = route[route.length - 1];
        for (let t = 0; t < 50; t++) {
          const q = polar(p, o.minLeg, o.maxLeg);
          if (route.some((w, wi) => wi < route.length - 1 && Math.hypot(w[0] - q[0], w[1] - q[1]) < o.minLeg * 0.8)) continue;
          if (!groupOk(shifted(q), BIT.PAVE, gap) || !offs.every((f) => okLine(p[0] + f[0], p[1] + f[1], q[0] + f[0], q[1] + f[1]) && freeLine(p[0] + f[0], p[1] + f[1], q[0] + f[0], q[1] + f[1]))) continue;
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
        want: () => sc.nightKey <= E.keep,
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
  const mkPicnic = () => {
    for (let tries = 0; tries < 4000; tries++) {
      const c = randomPt();
      if (!okDisk(c[0], c[1], 2.5, BIT.GRASS) || !free(c[0], c[1], 2)) continue;
      const n = 2 + ri(2), pts = [[c[0] - 0.75, c[1]], [c[0] + 0.75, c[1] + 0.1], [c[0], c[1] + 1.1]].slice(0, n);
      if (!groupOk(pts, BIT.GRASS)) continue;
      for (const q of pts) claim(q[0], q[1]);
      const as = pts.map((q) => mk(q[0], q[1], palNormal(), { pose: 'sit', pose0: 'sit' }));
      const sc = addScene('picnic', c, {
        actors: as, T: rr(2, 9),
        want: () => (E.season === 0 || E.season === 2) && E.day > 0.5 && !E.rain,
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
  const mkSnow = (c, r0, r1) => {
    for (let tries = 0; tries < 200; tries++) {
      const p = c ? polar(c, r0, r1) : randomPt(), ang = rnd() * TAU, u = [Math.cos(ang), Math.sin(ang)], v = [-u[1], u[0]];
      const k1 = [p[0] + u[0] * 2.4, p[1] + u[1] * 2.4], k2 = [p[0] - u[0] * 2.4, p[1] - u[1] * 2.4], g = [p[0] + v[0] * 2.6, p[1] + v[1] * 2.6];
      if (!groupOk([p, k1, k2, g]) || !okLine(k1[0], k1[1], k2[0], k2[1])) continue;
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
  const mkBusker = () => {
    for (let tries = 0; tries < 3000; tries++) {
      const c = tries < 1500 ? polar([A.gate[0], PALACE[1] - 30], 4, 90) : randomPt();
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
  const mkBench = (c0, r0, r1) => {
    for (let tries = 0; tries < 400; tries++) {
      const c = c0 ? polar(c0, r0, r1) : randomPt(), pts = [[c[0] - ex[0] * 0.75, c[1] - ex[1] * 0.75], [c[0] + ex[0] * 0.75, c[1] + ex[1] * 0.75]];
      if (!okDisk(c[0], c[1], 2.5) || !groupOk(pts) || !free(c[0], c[1], 2.2)) continue;
      for (const q of pts) claim(q[0], q[1]);
      claim(c[0], c[1]);
      const as = pts.map((q) => mk(q[0], q[1], LA(pick(cast.elder), { noUmb: true }), { pose: 'sit', pose0: 'sit', z: 0.45 }));
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
  const mkSoap = (c0, r0, r1) => {
    for (let tries = 0; tries < 400; tries++) {
      const c = polar(c0, r0, r1), g = [c[0] + 1.2, c[1] + 0.5];
      if (!okDisk(c[0], c[1], 4) || !groupOk([c, g])) continue;
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
  const mkKite = () => {
    for (let tries = 0; tries < 2000; tries++) {
      const c = randomPt();
      if (!okDisk(c[0], c[1], 7) || !free(c[0], c[1], 2)) continue;
      const g = [c[0] + 1.3, c[1] + 0.4];
      if (!groupOk([c, g])) continue;
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

  // ── 배치(고정 시드). 순서가 곧 자리 우선순위.

  // ── 광화문 앞 해치 한 쌍(고정 소품). 그림 타일에는 없어서 스프라이트로 세운다.
  // 좌표 근거: 광화문 정면 가운데의 지면 = 지도 px (783, 1218)(세 홍예 가운데 아래, 화면에서 읽은 값). 월드 축은 +x 가 문의 가로(동쪽), −y 가 남쪽(세종대로 쪽).
  // 실제 해치는 월대 남쪽 끝 좌우에 남쪽을 보고 앉아 있다 → 정면에서 남쪽으로 24 m, 좌우로 14 m 를 목표로 하고,
  // 둘이 대칭을 유지한 채 가장 가까운 「보도·광장(클래스 11·1) + 걷는 경로에서 1.8 m 이상 + 예약 자리와 안 겹침」 자리를 클래스 맵으로 찾는다.
  const haechi = [];
  {
    const G0 = toWorld(783, 1218, [0, 0]);
    const paths = [];   // 근처를 지나는 걷는 경로의 점(1 m 간격)
    for (const w of walkers) for (let d = 0; d <= w.L; d += 1) { pointAt(w.pts, w.cum, d, P3); if (Math.abs(P3[0] - G0[0]) < 40 && Math.abs(P3[1] - G0[1] + 24) < 30) paths.push(P3[0], P3[1]); }
    const okSpot = (x, y) => {
      for (const [dx, dy] of [[0, 0], [1.2, 0], [-1.2, 0], [0, 1.2], [0, -1.2]]) { const c = clsAt(x + dx, y + dy); if (c !== 11 && c !== 1) return false; }
      if (!free(x, y, 2.2)) return false;
      for (let k = 0; k < paths.length; k += 2) if (Math.hypot(paths[k] - x, paths[k + 1] - y) < 1.8) return false;
      return true;
    };
    let best = null, bd = 1e9;
    for (let lat = 9; lat <= 20; lat += 0.5) for (let dep = 14; dep <= 36; dep += 0.5) {
      const d = Math.hypot(lat - 14, dep - 24);
      if (d >= bd || !okSpot(G0[0] - lat, G0[1] - dep) || !okSpot(G0[0] + lat, G0[1] - dep)) continue;
      bd = d; best = [lat, dep];
    }
    if (best) for (const sd of [-1, 1]) {
      const x = G0[0] + sd * best[0], y = G0[1] - best[1];
      haechi.push({ x, y, side: sd });
      props.push({ type: 'haechi', x, y, variant: 0 });
      claim(x, y); for (let a = 0; a < 6; a++) claim(x + Math.cos(a * TAU / 6) * 1.2, y + Math.sin(a * TAU / 6) * 1.2);   // 사람이 서거나 지나가지 않는 자리
    }
  }

  // ── 궁 둘레 러너: 담장 바깥 보도를 따라 달린다(담을 상자로 보고 바깥쪽으로 가장 가까운 보도 띠를 클래스 맵에서 찾아 잇는다).
  // 차도(횡단보도 포함)는 건너지 않는다 → 보도가 끊기는 곳에서 구간이 나뉘고, 러너는 한 구간을 오간다.
  const RUNB = BIT.PAVE | BIT.DIRT;
  const runChains = [];
  {
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
      const n = Math.max(1, Math.round(RUN_GROUPS * c.L / total));
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
    }
  };
  const ceremony = mkCeremony();
  if (opts.birds) { let n = 0; for (const f of opts.birds.flocks) { if (n >= 5) break; if (mkPigeon(f)) n++; } }
  for (const [c, r0, r1, n] of [[A.gate, 14, 55, 3], [A.geun, 14, 50, 2], [A.gyeong, 18, 60, 2], [A.hyang, 8, 50, 2]]) for (let k = 0; k < n; k++) mkPhoto(c, r0, r1, k === 0);
  for (let k = 0; k < 3; k++) mkPhoto(null, 0, 0, false);
  // 광화문 앞(담 밖) 넷: 밤에도 남아 야경을 찍는다
  // 해치 앞 사진 명소: 석상마다 둘(석상 남쪽 앞)
  for (const h of haechi) for (let k = 0; k < 2; k++) { const sc = mkPhoto([h.x, h.y - 5], 1.5, 7, k === 0, false, true); if (sc) { sc.nightKey = rnd() * 0.4; sc.haechi = true; } }
  for (let k = 0; k < 4; k++) { const sc = mkPhoto([A.gate[0], PALACE[1] - 30], 4, 60, false, false, true); if (sc) sc.nightKey = rnd() * 0.25; }
  // 나란히 걷는 일행은 화면 가로 방향(±20°)으로 늘어선다 → 서로 가리지 않는다
  const sideAng = () => Math.atan2(ex[1], ex[0]) + rr(-0.35, 0.35) + (rnd() < 0.5 ? Math.PI : 0);
  const block = (n) => Array.from({ length: n }, (_, k) => (k === 0 ? [0, 0] : [((k - 1) % 2) * 1.2 - 0.6, -1.2 - Math.floor((k - 1) / 2) * 1.15]));
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
  const wantW = (w) => {
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
  };

  let stepN = 0;
  const sys = {
    haechi, runners, runChains, rpos, runFrac, toPx: (x, y) => { proj.project(x, y, 0, S); return [S[0], S[1]]; },
    time: 0, rainT: 0, actors, guests, scenes, props, fx, floaters, walkers, standing, ov, stats, wpos, toWorld, env: E, ceremony, cast, clsAt, hidden, inPalace, pairCount: pairs.length / 2,
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
    find(kind) { return scenes.filter((s) => s.kind === kind).map((s) => { proj.project(s.actors[0].x, s.actors[0].y, 0, S); return { x: S[0], y: S[1], on: s.on, st: s.st }; }); },
    // 유형별로 지금 보이는 걷는 사람의 위치(지도 px). 캡처용.
    findType(type, zone) { const out = []; walkers.forEach((w, i) => { if (w.type === type && w.vis && (!zone || w.zone === zone)) { wpos(i, sys.time, P3); if (!hidden(P3[0], P3[1])) { proj.project(P3[0], P3[1], 0, S); out.push({ x: S[0], y: S[1], wi: i }); } } }); return out; },
    meets,
    snapshot() {
      return { runners: runners.map((r) => [r.vis ? 1 : 0, r.u, r.lat, r.hold]), time: sys.time, stats: { ...stats }, rs: R1.rs, off: Array.from(ov.off), vis: walkers.map((w) => (w.vis ? 1 : 0)).join(''), actors: actors.map((a) => [a.on ? 1 : 0, a.x, a.y, a.pose, a.bubble]), guests: guests.map((g) => [g.wi, g.x, g.y, g.bubble]), scenes: scenes.map((s) => [s.on ? 1 : 0, s.st]) };
    },
  };
  return sys;
}
