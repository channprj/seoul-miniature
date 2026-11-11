// 고층 지도(여의도)의 밤 창문을 그림의 창틀에 맞춘다: 벽면 나누기 + 면마다 그림의 창 주기 추정.
//   1) buildFaces: 깊이·클래스 맵(1 m 칸)에서 벽 칸(클래스 7, 수직면)을 면으로 묶는다.
//      같은 면 = 이웃 칸의 벽 밑동 깊이(dc)가 이어지고, 가로 기울기(dc 의 x 변화 = 면의 방향)가 같다 → 건물 모서리에서 두 면이 갈린다.
//   2) classifyFaces: z1 바탕 그림으로 면의 종류를 정한다(유리·금빛 유리가 많으면 사무동 커튼월, 흰 벽이 많으면 아파트).
//      면 단위라서 63빌딩 아래쪽의 어두운 금빛(벽돌 건물과 같은 팔레트 색)도 사무동 면으로 남는다.
//   3) createWinEstimator: 타일(z2·z4·z8)이 올라올 때 그 그림 px 를 면마다 두 단면에 모은다.
//        세로 = 벽 위 높이 z(0.125 m 칸)마다 평균 밝기, 가로 = 화면 가로 위치(0.125 m 칸)마다 평균 밝기.
//      단면의 자기상관으로 주기를 찾고, 접기(위상 분산 최소화)로 주기를 다듬은 뒤, 접은 단면에서 창(유리) 구간의 시작 위상과 폭을 잡는다.
//      못 찾으면 그 축은 0(셰이더가 winlights.js 기본값 3.8 m × 1.6 m 를 쓴다).
//   좌표(셰이더 render.js WINGRID 와 같은 식): xf, yf = 연속 지도 px. 벽 위 높이 z = KZ·(dc − 지면 깊이(yf)),
//   dc = 같은 면 네 칸의 쌍선형 보간(faceDc). 세로 칸 = floor((z − φv)/Pv), 가로 칸 = floor((xf·MPP − φh)/Ph).

export const BIN = 0.125;         // 단면 칸(m) = z8 그림 px
export const NB = 16;             // 접은 단면의 위상 칸 수
export const AX = {
  v: { pMin: 1.5, pMax: 6.0, qMin: 0.15 },   // 층(그림의 가로 창틀 주기)
  h: { pMin: 0.9, pMax: 3.5, qMin: 0.3 },    // 칸(세로 창틀 주기, 화면 가로 m). 좁은 면·꺾인 면은 흔들리기 쉬워 품질 문턱을 높인다
};
export const KIND = { none: 0, office: 1, home: 2 };
export const TAB_W = 1024;        // 면 표: 한 줄에 면 1024 개 × 텍셀 2 개

const sm = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

// 커튼월 유리 색(winlights.js winGlassC 와 같은 식)
export function glassC(r, g, b) {
  const l = 0.3 * r + 0.59 * g + 0.11 * b, s = Math.max(r, g, b) - Math.min(r, g, b);
  const gold = g > r * 0.68 && g < r * 0.88 && b < r * 0.62 && s > 0.15 && l > 0.2 && l < 0.85;
  return (b > r * 1.05 && l < 0.85) || gold;
}

// proj = geom.js makeProjection, depth·sem = RGBA 바이트(W×H)
export function buildFaces({ proj, depth, sem }) {
  const { W, H } = proj, MPP = proj.m, EYZ = proj.ey[2], VDZ = proj.vd[2], CY = proj.cy, CAMVD = proj.camDotVd;
  const N = W * H;
  const gD = (py) => -((H * 0.5 - py) * MPP + CY) * EYZ / VDZ - CAMVD;   // render.js groundDepth
  const D = new Float64Array(N);
  for (let i = 0; i < N; i++) { const v = depth[i * 4] * 256 + depth[i * 4 + 1]; D[i] = v > 65534.5 ? NaN : proj.D0 + v * proj.dstep; }
  const hOf = (y, d) => VDZ * (d - gD(y + 0.5));
  const per = 2 * MPP / EYZ;
  const dc = new Float32Array(N).fill(NaN);
  const ok = new Uint8Array(N);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = y * W + x;
    if (sem[i * 4] !== 7 || !(D[i] === D[i])) continue;
    const d0 = D[Math.max(0, y - 1) * W + x], d1 = D[Math.min(H - 1, y + 1) * W + x];
    if (!(d0 === d0) || !(d1 === d1)) continue;
    const r = (hOf(Math.max(0, y - 1), d0) - hOf(Math.min(H - 1, y + 1), d1)) / per;
    if (sm(0.45, 0.8, r) * (1 - sm(1.6, 2.4, r)) <= 0.5) continue;   // render.js wallness > 0.5
    ok[i] = 1; dc[i] = D[i] - hOf(y, D[i]) * VDZ;
  }
  // 가로 기울기(면의 방향): 양쪽 이웃이 같은 면 후보면 중앙 차분, 아니면 한쪽
  const sl = new Float32Array(N).fill(NaN);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = y * W + x;
    if (!ok[i]) continue;
    const L = x > 0 && ok[i - 1] && Math.abs(dc[i] - dc[i - 1]) < 3, R = x < W - 1 && ok[i + 1] && Math.abs(dc[i + 1] - dc[i]) < 3;
    sl[i] = L && R ? (dc[i + 1] - dc[i - 1]) / 2 : R ? dc[i + 1] - dc[i] : L ? dc[i] - dc[i - 1] : NaN;
  }
  // 합집합-찾기
  const par = new Int32Array(N).fill(-1);
  const find = (a) => { while (par[a] !== a) { par[a] = par[par[a]]; a = par[a]; } return a; };
  const uni = (a, b) => { a = find(a); b = find(b); if (a !== b) { if (a < b) par[b] = a; else par[a] = b; } };
  for (let i = 0; i < N; i++) if (ok[i]) par[i] = i;
  const sameSl = (a, b) => !(sl[a] === sl[a]) || !(sl[b] === sl[b]) || Math.abs(sl[a] - sl[b]) < 0.3;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = y * W + x;
    if (!ok[i]) continue;
    if (x < W - 1 && ok[i + 1] && Math.abs(dc[i + 1] - dc[i]) < 3 && sameSl(i, i + 1)) uni(i, i + 1);
    if (y < H - 1 && ok[i + W] && Math.abs(dc[i + W] - dc[i]) < 1.5 && sameSl(i, i + W)) uni(i, i + W);
  }
  // 이어진 덩어리를 열(x) 순서로 훑어, 열의 기울기 평균이 구간 첫 열에서 0.15 넘게 벗어나면 새 면으로 끊는다
  //   (IFC 처럼 조금씩 꺾이는 면은 이웃끼리는 기울기가 비슷해 한 덩어리가 된다 → 면마다 화면 가로 창 간격이 다르다)
  const comp = new Int32Array(N).fill(-1);
  let NC = 0;
  const cx0 = [], cx1 = [];
  for (let i = 0; i < N; i++) {
    if (!ok[i]) continue;
    const r = find(i);
    if (comp[r] < 0) { comp[r] = NC++; cx0.push(W); cx1.push(-1); }
    const c = comp[r], x = i % W;
    comp[i] = c;
    if (x < cx0[c]) cx0[c] = x; if (x > cx1[c]) cx1[c] = x;
  }
  const off = new Int32Array(NC + 1);
  for (let c = 0; c < NC; c++) off[c + 1] = off[c] + (cx1[c] - cx0[c] + 1);
  const ssum = new Float64Array(off[NC]), scnt = new Int32Array(off[NC]), npx = new Int32Array(off[NC]);
  for (let i = 0; i < N; i++) {
    if (!ok[i]) continue;
    const c = comp[i], k = off[c] + (i % W) - cx0[c];
    npx[k]++;
    if (sl[i] === sl[i]) { ssum[k] += sl[i]; scnt[k]++; }
  }
  const seg = new Int32Array(off[NC]);
  let NS = 0;
  for (let c = 0; c < NC; c++) {
    let s0 = NaN, prev = false;
    for (let k = off[c]; k < off[c + 1]; k++) {
      if (!npx[k]) { prev = false; continue; }
      const md = scnt[k] ? ssum[k] / scnt[k] : NaN;
      if (!prev) { NS++; s0 = NaN; }
      if (md === md) { if (s0 === s0 && Math.abs(md - s0) > 0.15) { NS++; s0 = md; } else if (!(s0 === s0)) s0 = md; }
      seg[k] = NS; prev = true;
    }
  }
  // 작은 조각(모서리 칸, 낮은 담)은 면으로 치지 않는다 → 0(셰이더는 예전 식)
  const scount = new Int32Array(NS + 1), sface = new Int32Array(NS + 1).fill(-1), sbld = new Int32Array(NS + 1);
  const segAt = (i) => seg[off[comp[i]] + (i % W) - cx0[comp[i]]];
  for (let i = 0; i < N; i++) if (ok[i]) { const g = segAt(i); scount[g]++; sbld[g] = comp[i]; }
  const face = new Uint16Array(N);
  const faces = [null];
  for (let g = 1; g <= NS; g++) {
    if (scount[g] < 40 || faces.length >= 65535) continue;
    sface[g] = faces.length;
    faces.push({ n: 0, x0: W, x1: 0, y0: H, y1: 0, zlo: Infinity, zhi: -Infinity, kind: KIND.none, glass: 0, white: 0, seen: 0, bld: sbld[g] });
  }
  for (let i = 0; i < N; i++) if (ok[i]) { const f = sface[segAt(i)]; if (f > 0) face[i] = f; }
  const G = { W, H, MPP, KZ: VDZ / (1 - VDZ * VDZ), gD, face, dc, faces };
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const f = face[y * W + x];
    if (!f) continue;
    const F = faces[f];
    F.n++; F.x0 = Math.min(F.x0, x); F.x1 = Math.max(F.x1, x + 1); F.y0 = Math.min(F.y0, y); F.y1 = Math.max(F.y1, y + 1);
    for (const yy of [y, y + 1]) { const z = zOf(G, faceDc(G, f, x + 0.5, yy) ?? dc[y * W + x], yy); F.zlo = Math.min(F.zlo, z); F.zhi = Math.max(F.zhi, z); }
  }
  for (let f = 1; f < faces.length; f++) {
    const F = faces[f];
    F.zlo = Math.floor(F.zlo / BIN) * BIN - BIN; F.zhi = Math.ceil(F.zhi / BIN) * BIN + BIN;
  }
  // 낮은 면(난간·담·포디움 테두리, 높이 8 m 미만)은 면으로 치지 않는다 → 0(예전 식: 둘레 다수결)
  const keep = faces.map((F, f) => f === 0 || F.zhi - F.zlo >= 8);
  if (keep.some((k) => !k)) {
    const remap = new Uint16Array(faces.length), kept = [null];
    for (let f = 1; f < faces.length; f++) if (keep[f]) { remap[f] = kept.length; kept.push(faces[f]); }
    for (let i = 0; i < N; i++) if (face[i]) face[i] = remap[face[i]];
    faces.length = 0; faces.push(...kept);
  }
  return G;
}

// 면 f 의 벽 밑동 깊이를 연속 지도 좌표(xf, yf)에서: 같은 면 네 칸의 쌍선형 보간(가중치 +1e-3, render.js 와 같은 식). 네 칸 다 다른 면이면 null
export function faceDc(G, f, xf, yf) {
  const tx = xf - 0.5, ty = yf - 0.5, ix = Math.floor(tx), iy = Math.floor(ty), fx = tx - ix, fy = ty - iy;
  let ws = 0, ds = 0;
  for (let k = 0; k < 4; k++) {
    const cx = ix + (k & 1), cy = iy + (k >> 1);
    if (cx < 0 || cy < 0 || cx >= G.W || cy >= G.H) continue;
    const i = cy * G.W + cx;
    if (G.face[i] !== f) continue;
    const w = ((k & 1) ? fx : 1 - fx) * ((k >> 1) ? fy : 1 - fy) + 1e-3;
    ws += w; ds += w * G.dc[i];
  }
  return ws > 0 ? ds / ws : null;
}
export const zOf = (G, dc, yf) => G.KZ * (dc - G.gD(yf));

// z1 바탕 그림(W×H RGBA)으로 면 종류를 정한다
export function classifyFaces(G, rgba) {
  const { face, faces } = G;
  for (let i = 0; i < face.length; i++) {
    const f = face[i];
    if (!f) continue;
    const r = rgba[i * 4] / 255, g = rgba[i * 4 + 1] / 255, b = rgba[i * 4 + 2] / 255;
    const l = 0.3 * r + 0.59 * g + 0.11 * b, s = Math.max(r, g, b) - Math.min(r, g, b);
    const F = faces[f];
    F.seen++;
    if (glassC(r, g, b)) F.glass++;
    else if (l > 0.55 && s < 0.12) F.white++;
  }
  for (let f = 1; f < faces.length; f++) {
    const F = faces[f];
    if (!F.seen) continue;
    const gf = F.glass / F.seen, wf = F.white / F.seen;
    // 커튼월 = 유리가 많고 흰 벽이 거의 없다(63·파크원·IFC 는 흰 벽 0). 푸른 띠창 아파트는 유리 0.5 여도 흰 벽이 0.2 넘게 섞인다 → 아파트
    F.kind = gf >= 0.4 && wf < 0.12 ? KIND.office : wf >= 0.2 ? KIND.home : KIND.none;
  }
}

// 단면 하나에서 주기·위상·창 구간. sum·cnt = 칸별 밝기 합·개수, origin = 칸 0 의 시작 좌표(m), dark = 창이 어두운 쪽(아파트)
// → { P, phi, w, q } (P 주기 m, phi 창 구간이 시작하는 위상 m(0 ≤ phi < P), w 창 구간 폭(주기 비율), q 접기 품질) 또는 null
// 신호 둘을 보고 자기상관 봉우리가 더 뚜렷한 쪽을 쓴다:
//   가는 선 = 밝기 − 둘레 ±0.5 m 중앙값(커튼월의 한두 px 창틀 선. 넓은 색 띠·그늘에 묻히지 않는다)
//   넓은 무늬 = 밝기 − 둘레 ±pMax 평균(아파트의 어두운 창 덩어리, 흰 띠창)
export function estimateAxis(sum, cnt, origin, { pMin, pMax, qMin = 0.15 }, dark = false, dbg = null) {
  const n = sum.length;
  const v = new Float64Array(n); let nv = 0;
  for (let i = 0; i < n; i++) { v[i] = cnt[i] > 0 ? sum[i] / cnt[i] : NaN; if (cnt[i] > 0) nv++; }
  if (nv * BIN < pMax * 2.5) return null;   // 주기 2.5 개 이상
  const L0 = Math.max(2, Math.floor(pMin / BIN)), L1 = Math.ceil(pMax / BIN);
  const acf = (a) => {
    const r = new Float64Array(L1 + 2).fill(-1);
    for (let L = L0 - 1; L <= L1 + 1; L++) {
      let sab = 0, saa = 0, sbb = 0, np = 0;
      for (let i = 0; i + L < n; i++) {
        const x = a[i], y = a[i + L];
        if (x === x && y === y) { sab += x * y; saa += x * x; sbb += y * y; np++; }
      }
      r[L] = np >= 1.5 * L && saa > 0 && sbb > 0 ? sab / Math.sqrt(saa * sbb) : -1;
    }
    let best = -1;
    const peaks = [];
    for (let L = L0; L <= L1; L++) if (r[L] > r[L - 1] && r[L] >= r[L + 1]) { peaks.push(L); best = Math.max(best, r[L]); }
    return { r, peaks, best };
  };
  const line = new Float64Array(n).fill(NaN), broad = new Float64Array(n).fill(NaN);
  const k = Math.round(0.5 / BIN), w0 = [];
  for (let i = 0; i < n; i++) {
    if (!(v[i] === v[i])) continue;
    w0.length = 0;
    for (let j = Math.max(0, i - k); j <= Math.min(n - 1, i + k); j++) if (v[j] === v[j]) w0.push(v[j]);
    w0.sort((x, y) => x - y);
    line[i] = v[i] - w0[w0.length >> 1];
  }
  { const hw = Math.ceil(pMax / BIN); let s = 0, c = 0, lo = 0, hi = -1;
    for (let i = 0; i < n; i++) {
      while (hi < Math.min(n - 1, i + hw)) { hi++; if (v[hi] === v[hi]) { s += v[hi]; c++; } }
      while (lo < i - hw) { if (v[lo] === v[lo]) { s -= v[lo]; c--; } lo++; }
      if (v[i] === v[i] && c > 0) broad[i] = v[i] - s / c;
    } }
  // 자기상관은 [1 2 1] 로 살짝 퍼뜨린 신호로 잰다: 그림의 창틀은 정수 px 에 찍혀 주기가 9.5 px 이면 9·10 px 를 번갈아 → 한 px 선끼리는 정수 지연에서 반만 겹친다
  const blur = (a) => { const b = new Float64Array(n).fill(NaN);
    for (let i = 0; i < n; i++) { if (!(a[i] === a[i])) continue; let s = 2 * a[i], c = 2;
      if (i > 0 && a[i - 1] === a[i - 1]) { s += a[i - 1]; c++; } if (i < n - 1 && a[i + 1] === a[i + 1]) { s += a[i + 1]; c++; } b[i] = s / c; }
    return b; };
  let pick = null;
  for (const [name, a] of [['line', line], ['broad', broad]]) {
    let ss = 0, sc = 0;
    for (let i = 0; i < n; i++) if (a[i] === a[i]) { ss += a[i] * a[i]; sc++; }
    if (!sc || Math.sqrt(ss / sc) < 0.006) continue;   // 민무늬
    const c = acf(name === 'line' ? blur(a) : a);
    if (dbg) dbg[name] = { best: c.best, peaks: c.peaks.map((L) => [L, +c.r[L].toFixed(2)]) };
    if (c.best >= 0.2 && (!pick || c.best > pick.best)) pick = { ...c, a, ss, name };
  }
  if (!pick) return null;
  const { r, peaks, best, a, ss } = pick;
  const L = peaks.find((p) => r[p] >= best * 0.8);   // 배수 주기(2P·3P)보다 가장 짧은 강한 봉우리
  const den = r[L - 1] - 2 * r[L] + r[L + 1];
  const P0 = (L + (den < 0 ? 0.5 * (r[L - 1] - r[L + 1]) / den : 0)) * BIN;
  // 접기 품질(칸 사이 분산 / 전체 분산): 주기가 맞을수록 크다 → 거칠게 다듬고 곱게 다듬는다
  const ctr = new Float64Array(n);
  for (let i = 0; i < n; i++) ctr[i] = origin + (i + 0.5) * BIN;
  const fs = new Float64Array(NB), fc = new Float64Array(NB);
  const fold = (P) => {
    fs.fill(0); fc.fill(0);
    for (let i = 0; i < n; i++) {
      if (!(a[i] === a[i])) continue;
      const ph = ctr[i] / P; let kk = Math.floor((ph - Math.floor(ph)) * NB); if (kk >= NB) kk = NB - 1;
      fs[kk] += a[i]; fc[kk]++;
    }
    let q = 0;
    for (let kk = 0; kk < NB; kk++) if (fc[kk]) q += fs[kk] * fs[kk] / fc[kk];
    return q / ss;
  };
  let P = P0, q = fold(P0);
  for (const [span, step] of [[BIN * 1.5, 0.005], [0.006, 0.0005]]) {
    const c = P;
    for (let p = c - span; p <= c + span + 1e-9; p += step) {
      if (p < pMin * 0.9 || p > pMax * 1.1) continue;
      const qq = fold(p);
      if (qq > q) { q = qq; P = p; }
    }
  }
  // 한 주기에 창틀이 둘·셋(굵은 선과 가는 선이 번갈아)이면 창 칸은 그 사이: P/2·P/3 으로 접어도 무늬가 꽤 남으면 그쪽
  // (접은 단면에 같은 쪽 골(가장 깊은 골의 25% 이상)이 1/m 주기 간격으로 m 개 있어야 한다: 한 줄짜리 무늬도 P/2 로 접으면 품질이 반쯤 남으니 품질만으로는 못 가른다)
  fold(P);
  const f0 = Array.from(fs, (v, kk) => (fc[kk] ? v / fc[kk] : 0)), mean0 = f0.reduce((x, y) => x + y, 0) / NB;
  let k0 = 0; for (let kk = 1; kk < NB; kk++) if (Math.abs(f0[kk] - mean0) > Math.abs(f0[k0] - mean0)) k0 = kk;
  const dip = f0[k0] - mean0;
  const hasDips = (m) => { for (let j = 1; j < m; j++) { const c0 = k0 + Math.round(j * NB / m); let b = 0;
    for (let d = -1; d <= 1; d++) { const v = (f0[(c0 + d + NB) % NB] - mean0) / dip; if (v > b) b = v; }
    if (b < 0.25) return false; } return true; };
  for (const m of [3, 2]) {
    const Pm = P / m;
    if (Pm < pMin || !hasDips(m)) continue;
    let bq = fold(Pm), bp = Pm;
    for (let p = Pm - 0.006; p <= Pm + 0.006 + 1e-9; p += 0.0005) { const qq = fold(p); if (qq > bq) { bq = qq; bp = p; } }
    if (bq >= q * 0.7) { P = bp; q = bq; break; }   // 한 줄짜리 무늬도 P/2 로 접으면 품질이 반쯤 남는다 → 0.7
  }
  if (dbg) Object.assign(dbg, { sig: pick.name, P0, P, q });
  if (q < qMin) return null;
  fold(P);
  // 접은 단면: 가운데 값으로 어두운 칸·밝은 칸을 가르고, 창 쪽(아파트 = 어두운 쪽, 커튼월 = 넓은 쪽 = 창틀이 아닌 쪽)의 가장 긴 고리 구간
  const fm = new Float64Array(NB);
  let mn = Infinity, mx = -Infinity;
  for (let kk = 0; kk < NB; kk++) { fm[kk] = fc[kk] ? fs[kk] / fc[kk] : NaN; if (fm[kk] === fm[kk]) { mn = Math.min(mn, fm[kk]); mx = Math.max(mx, fm[kk]); } }
  const mid = (mn + mx) / 2;
  const isDark = (kk) => (fm[kk] === fm[kk] ? fm[kk] < mid : fm[(kk + NB - 1) % NB] < mid);
  let nd = 0; for (let kk = 0; kk < NB; kk++) if (isDark(kk)) nd++;
  const winDark = dark ? true : nd >= NB - nd;
  let bs = -1, bl = 0;
  for (let s0 = 0; s0 < NB; s0++) {
    if (isDark(s0) !== winDark || isDark((s0 + NB - 1) % NB) === winDark) continue;   // 구간의 시작만
    let l = 0; while (l < NB && isDark((s0 + l) % NB) === winDark) l++;
    if (l > bl) { bl = l; bs = s0; }
  }
  if (dbg) Object.assign(dbg, { fm, bs, bl, winDark });
  if (bs < 0) return null;   // 고리 전체가 한쪽(대비 없음)
  const w = bl / NB;
  if (dark ? w < 0.1 || w > 0.75 : w < 0.4 || w > 0.97) return null;
  return { P, phi: (bs / NB) * P, w, q, sig: pick.name };
}

// 타일이 올라올 때마다 그림 px 를 면 단면에 모으고, 바뀐 면만 다시 추정한다.
export function createWinEstimator(G, { levels = [2, 4, 8] } = {}) {
  const { W, H, face, faces, MPP } = G;
  const NF = faces.length;
  const acc = new Array(NF).fill(null);
  const mk = (f) => {
    const F = faces[f];
    const nz = Math.max(1, Math.round((F.zhi - F.zlo) / BIN)), nx = Math.max(1, Math.ceil((F.x1 - F.x0) * MPP / BIN) + 2);
    return (acc[f] = { zs: new Float32Array(nz), zc: new Uint32Array(nz), xs: new Float32Array(nx), xc: new Uint32Array(nx), xlo: F.x0 * MPP - BIN, n: 0, est: 0 });
  };
  const seenTiles = new Set();
  const dirty = new Set();
  const tab = new Float32Array(TAB_W * 2 * Math.ceil(NF / TAB_W) * 4);
  for (let f = 1; f < NF; f++) { tab[f * 8 + 3] = faces[f].kind; tab[f * 8 + 7] = (faces[f].bld % 8191) + 1; }   // 종류, 건물 번호(켜짐 난수 씨앗: 한 건물의 면들이 같은 층 비율을 쓴다)
  // 그림 조각 하나(z = 지도 칸당 그림 px, 그림 px 좌표 X0·Y0 부터 w×h, RGBA 바이트)
  function add(z, X0, Y0, w, h, rgba, key) {
    if (!levels.includes(z)) return 0;
    if (key !== undefined) { if (seenTiles.has(key)) return 0; seenTiles.add(key); }
    let used = 0;
    for (let y = 0; y < h; y++) {
      const yf = (Y0 + y + 0.5) / z, py = Math.floor(yf);
      if (py < 0 || py >= H) continue;
      for (let x = 0; x < w; x++) {
        const xf = (X0 + x + 0.5) / z, px = Math.floor(xf);
        if (px < 0 || px >= W) continue;
        const f = face[py * W + px];
        if (!f) continue;
        const o = (y * w + x) * 4, l = (0.3 * rgba[o] + 0.59 * rgba[o + 1] + 0.11 * rgba[o + 2]) / 255;
        const A = acc[f] || mk(f), F = faces[f];
        const dc = faceDc(G, f, xf, yf);
        if (dc === null) continue;
        const zi = Math.floor((zOf(G, dc, yf) - F.zlo) / BIN), xi = Math.floor((xf * MPP - A.xlo) / BIN);
        if (zi >= 0 && zi < A.zs.length) { A.zs[zi] += l; A.zc[zi]++; }
        if (xi >= 0 && xi < A.xs.length) { A.xs[xi] += l; A.xc[xi]++; }
        A.n++; used++;
        dirty.add(f);
      }
    }
    return used;
  }
  // 바뀐 면을 다시 추정(시간 예산 ms). 표가 바뀌었으면 true
  function work(budgetMs = 4) {
    const t0 = (typeof performance !== 'undefined' ? performance : Date).now();
    let changed = false;
    for (const f of dirty) {
      dirty.delete(f);
      const A = acc[f], F = faces[f];
      if (!A || A.n < 1.3 * A.est) continue;   // 새 px 가 30% 넘게 늘었을 때만 다시(조금씩 들어오는 타일마다 깜빡이지 않게)
      A.est = A.n;
      const home = F.kind === KIND.home;
      const ev = estimateAxis(A.zs, A.zc, F.zlo, AX.v, home), eh = estimateAxis(A.xs, A.xc, A.xlo, AX.h, home);
      const o = f * 8;
      tab[o] = ev ? ev.P : 0; tab[o + 1] = ev ? ev.phi : 0; tab[o + 2] = ev ? ev.w : 0; tab[o + 3] = F.kind;
      tab[o + 4] = eh ? eh.P : 0; tab[o + 5] = eh ? eh.phi : 0; tab[o + 6] = eh ? eh.w : 0;
      F.ev = ev; F.eh = eh;
      changed = true;
      if ((typeof performance !== 'undefined' ? performance : Date).now() - t0 > budgetMs) break;
    }
    return changed;
  }
  // 면 번호 텍스처(RG8: 번호 = r·256 + g)
  function faceBytes() {
    const b = new Uint8Array(W * H * 2);
    for (let i = 0; i < face.length; i++) { b[i * 2] = face[i] >> 8; b[i * 2 + 1] = face[i] & 255; }
    return b;
  }
  // 타일(256 그림 px) 하나가 면을 덮는지(안 덮으면 그림을 읽지 않는다)
  function covers(z, tx, ty, T = 256) {
    if (!levels.includes(z)) return false;
    const s = T / z, x0 = Math.floor(tx * s), y0 = Math.floor(ty * s), x1 = Math.min(W, Math.ceil((tx + 1) * s)), y1 = Math.min(H, Math.ceil((ty + 1) * s));
    for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) if (face[y * W + x]) return true;
    return false;
  }
  return { G, add, work, covers, tab, tabSize: [TAB_W * 2, tab.length / (TAB_W * 2 * 4)], faceBytes, pending: () => dirty.size, acc };
}

// ── 미리 계산한 면(winfaces.json, tools/build-winfaces.mjs 가 자산 설치 때 만든다)
// 앱은 이 파일이 있으면 면 나누기·주기 추정을 하지 않고 읽기만 한다(없거나 지도와 안 맞으면 위의 실행 중 계산).
//   faceMap = 지도 칸(가로줄 순서) 면 번호의 길이 부호화(가변 길이 정수 [길이, 번호] 쌍) → deflate-raw → base64
//   faces[i] = 면 i+1 의 [층 주기, 층 위상, 층 창 폭, 종류, 칸 주기, 칸 위상, 칸 창 폭, 건물 번호] (주기 0 = 못 잼)
export const WINFACES_SCHEMA = 'winfaces-1';
const putV = (out, v) => { while (v >= 128) { out.push((v & 127) | 128); v = Math.floor(v / 128); } out.push(v); };
export function rleFaceMap(face) {
  const out = [];
  for (let i = 0; i < face.length;) { const v = face[i]; let j = i + 1; while (j < face.length && face[j] === v) j++; putV(out, j - i); putV(out, v); i = j; }
  return Uint8Array.from(out);
}
export function unrleFaceMap(u8, N) {
  const face = new Uint16Array(N);
  let i = 0, p = 0;
  const getV = () => { let v = 0, m = 1, b; do { b = u8[p++]; v += (b & 127) * m; m *= 128; } while (b & 128); return v; };
  while (p < u8.length && i < N) { const n = getV(), v = getV(); if (v) face.fill(v, i, Math.min(N, i + n)); i += n; }
  if (i !== N) throw new Error(`winfaces: 면 번호 칸 수 ${i} ≠ ${N}`);
  return face;
}
const r4 = (v) => Math.round(v * 1e4) / 1e4;
// 추정기(createWinEstimator) → JSON 객체(faceMap 은 deflate 를 맡긴다: deflateRaw(Uint8Array) → Uint8Array)
export function packWinFaces(E, { deflateRaw, toB64, meta = {} }) {
  const { G, tab } = E, NF = G.faces.length;
  const faces = [];
  for (let f = 1; f < NF; f++) { const o = f * 8; faces.push([r4(tab[o]), r4(tab[o + 1]), r4(tab[o + 2]), tab[o + 3], r4(tab[o + 4]), r4(tab[o + 5]), r4(tab[o + 6]), tab[o + 7]]); }
  return { schema: WINFACES_SCHEMA, ...meta, size: [G.W, G.H], faces, faceMap: toB64(deflateRaw(rleFaceMap(G.face))) };
}
// JSON → { face: Uint16Array, faceBytes(RG8), tab, tabSize } 또는 이유 문자열(안 맞으면 쓰지 않는다)
//   sem = 클래스 맵 RGBA 바이트: 면 칸이 벽(7)이 아닌 비율이 0.5% 를 넘으면 다른 굽기의 파일로 보고 버린다
export function unpackWinFaces(J, { W, H, sem, inflateRaw, fromB64 }) {
  if (!J || J.schema !== WINFACES_SCHEMA) return '형식이 다름';
  if (!J.size || J.size[0] !== W || J.size[1] !== H) return `크기 ${J.size} ≠ ${W}×${H}`;
  const NF = J.faces.length + 1;
  if (NF >= 65535) return '면이 너무 많음';
  const face = unrleFaceMap(inflateRaw(fromB64(J.faceMap), W * H / 4), W * H);
  let n = 0, bad = 0;
  for (let i = 0; i < face.length; i++) if (face[i]) { n++; if (face[i] >= NF) return '면 번호가 표 밖'; if (sem && sem[i * 4] !== 7) bad++; }
  if (sem && bad > n * 0.005) return `면 칸 ${bad}/${n} 이 벽이 아님(다른 굽기의 파일)`;
  const tab = new Float32Array(TAB_W * 2 * Math.ceil(NF / TAB_W) * 4);
  J.faces.forEach((r, k) => tab.set(r, (k + 1) * 8));
  const faceBytes = new Uint8Array(W * H * 2);
  for (let i = 0; i < face.length; i++) { faceBytes[i * 2] = face[i] >> 8; faceBytes[i * 2 + 1] = face[i] & 255; }
  return { face, faceBytes, tab, tabSize: [TAB_W * 2, tab.length / (TAB_W * 2 * 4)], nf: NF - 1 };
}
