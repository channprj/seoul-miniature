// 배경 타일 피라미드 캐시. 바탕(z1, 0.5 m)은 통짜 텍스처로 늘 올라가 있고, 확대하면 보이는 칸의
// z2(0.25 m)·z4(0.125 m)·z8(0.0625 m) 타일(redraw/tiles/z{z}_{x}_{y}.png, 256 그림 px)만 받아 고정 크기 아틀라스에 올린다.
//   아틀라스: 256 px 칸 SX×SY(휴대폰 8×12 = 2048×3072, 데스크톱 16×16 = 4096²), RGBA8
//   단계마다 칸 색인 텍스처(그 단계 타일 격자 크기, RGBA8: r,g = 칸 위치, b = 있음)
//   단색 타일(manifest.solid, 지도 밖 등)은 파일이 없다 → 그 색으로 채운 예약 칸을 가리킨다.
// 단계 고르기(plan): 목표 단계의 보이는 타일이 전부 올라왔을 때만 그 단계로 그린다. 아니면 다 올라온 더 거친 단계(없으면 z1).
//   한 프레임 안에서 단계를 섞지 않는다. 목표와 거친 두 단계(z8 이면 z4·z2)를 같이 받아 두어 빠르게 끌 때 z1 까지 떨어지지 않게 한다.
//   끄는 방향으로 앞쪽(속도 × LOOKAHEAD 프레임)을 미리 받는다.
//   내려가는 것은 즉시, 올라가는 것은 그 단계가 UP_FRAMES 프레임 연속 다 있을 때만(빠르게 끌 때 1→4→1 깜빡임 방지).
// 교체는 LRU. 이번 프레임에 쓰는 범위(보이는 칸 + 둘레 한 칸)는 내보내지 않는다.
import { optionalImage } from './assets.js';

export const TILE = 256;
const MAX_FETCH = 6, MAX_UPLOAD = 4, RETRY_MS = 3000, UP_FRAMES = 6, LOOKAHEAD = 12;

export function createBgTiles(gl, W, H, man, { phone = false, load } = {}) {
  const maxTex = gl.getParameter(gl.MAX_TEXTURE_SIZE);
  const SX = phone || maxTex < 4096 ? 8 : 16, SY = phone || maxTex < 4096 ? 12 : 16, SLOTS = SX * SY;
  load ||= (z, tx, ty) => optionalImage(`redraw/tiles/z${z}_${tx}_${ty}.${man.levels[z].format || 'png'}`);
  const mk = (w, h) => {
    const t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texStorage2D(gl.TEXTURE_2D, 1, gl.RGBA8, w, h);
    for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.NEAREST], [gl.TEXTURE_MAG_FILTER, gl.NEAREST], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
    return t;
  };
  const atlas = mk(SX * TILE, SY * TILE);
  const owner = new Int32Array(SLOTS).fill(-1), slotUsed = new Float64Array(SLOTS);
  // 단색 예약 칸
  const colors = man.colors || [];
  const reserved = Math.min(colors.length, 8);
  gl.bindTexture(gl.TEXTURE_2D, atlas);
  gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
  for (let i = 0; i < reserved; i++) {
    const px = new Uint8Array(TILE * TILE * 4);
    for (let k = 0; k < px.length; k += 4) { px[k] = colors[i][0]; px[k + 1] = colors[i][1]; px[k + 2] = colors[i][2]; px[k + 3] = 255; }
    gl.texSubImage2D(gl.TEXTURE_2D, 0, (i % SX) * TILE, ((i / SX) | 0) * TILE, TILE, TILE, gl.RGBA, gl.UNSIGNED_BYTE, px);
    owner[i] = -2;
  }
  // 단계별 상태
  const L = {};
  for (const z of man.zs || []) {
    if (z < 2) continue;
    const lv = man.levels[z], [GW, GH] = lv.grid;
    const idx = new Uint8Array(GW * GH * 4), solid = new Uint8Array(GW * GH);
    for (const [tx, ty, ci] of lv.solid || []) {
      if (ci >= reserved) continue;   // 예약 칸이 모자라면 파일처럼 받는다(404 → 바탕 단계에 머문다)
      solid[ty * GW + tx] = 1;
      idx.set([ci % SX, (ci / SX) | 0, 255, 255], (ty * GW + tx) * 4);
    }
    L[z] = { z, GW, GH, idx, solid, tex: mk(GW, GH), dirty: true, tiles: new Map(), misses: 0, ups: 0, dead: false };
  }
  const zs = Object.keys(L).map(Number).sort((a, b) => a - b);
  let inFlight = 0, frame = 0, drawn = 1, vx = 0, vy = 0, last = null;
  const streak = {};

  const fetchTile = (lv, key) => {
    const tx = key % lv.GW, ty = (key / lv.GW) | 0;
    const e = { st: 'load', slot: -1, used: frame, bmp: null, at: 0 };
    lv.tiles.set(key, e); inFlight++;
    load(lv.z, tx, ty).then((bmp) => {
      if (!bmp) { e.st = 'miss'; if (++lv.misses >= 3 && lv.ups === 0) lv.dead = true; return; }   // 그 단계가 배포되지 않음
      e.bmp = bmp; e.st = 'ready';
    }, () => { e.st = 'err'; e.at = performance.now(); }).finally(() => { inFlight--; });
  };
  const upload = (lv, key, e) => {
    let s = -1, best = Infinity;
    for (let i = reserved; i < SLOTS; i++) {
      if (owner[i] < 0) { s = i; break; }
      if (slotUsed[i] < frame && slotUsed[i] < best) { best = slotUsed[i]; s = i; }
    }
    if (s < 0) return false;
    if (owner[s] >= 0) {
      // owner = z * 1e6 + key
      const oz = Math.floor(owner[s] / 1e6), ok = owner[s] % 1e6, ol = L[oz];
      ol.tiles.delete(ok); ol.idx.fill(0, ok * 4, ok * 4 + 4); ol.dirty = true;
    }
    const sx = s % SX, sy = (s / SX) | 0;
    gl.bindTexture(gl.TEXTURE_2D, atlas);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, sx * TILE, sy * TILE, gl.RGBA, gl.UNSIGNED_BYTE, e.bmp);
    e.bmp.close?.(); e.bmp = null; e.st = 'up'; e.slot = s; lv.ups++;
    owner[s] = lv.z * 1e6 + key; slotUsed[s] = frame;
    lv.idx.set([sx, sy, 255, 255], key * 4); lv.dirty = true;
    return true;
  };
  // 지도 px 범위 → 그 단계의 타일 범위(가장자리 포함)
  const rectOf = (lv, x0, y0, x1, y1, ring = 0) => [
    Math.max(0, Math.floor(x0 * lv.z / TILE) - ring), Math.max(0, Math.floor(y0 * lv.z / TILE) - ring),
    Math.min(lv.GW - 1, Math.floor((x1 * lv.z - 1) / TILE) + ring), Math.min(lv.GH - 1, Math.floor((y1 * lv.z - 1) / TILE) + ring)];
  const count = (r) => (r[2] - r[0] + 1) * (r[3] - r[1] + 1);
  const resident = (lv, r) => {
    for (let ty = r[1]; ty <= r[3]; ty++) for (let tx = r[0]; tx <= r[2]; tx++) {
      const k = ty * lv.GW + tx;
      if (!lv.solid[k] && lv.tiles.get(k)?.st !== 'up') return false;
    }
    return true;
  };

  return {
    atlas, zs, slots: SLOTS,
    get active() { return zs.some((z) => !L[z].dead); },
    has: (z) => !!L[z] && !L[z].dead,
    index: (z) => L[z].tex,
    // 목표 단계 target 과 지도 px 범위(합성 범위). 받을 것을 요청·업로드하고, 이번 프레임에 그릴 단계를 돌려준다.
    plan(target, x0, y0, x1, y1) {
      frame++;
      // 화면 이동 속도(지도 px/프레임, 부드럽게). 크기가 바뀌면(확대·축소) 0
      const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, sz = x1 - x0;
      if (last && Math.abs(last[2] - sz) < 1) { vx = vx * 0.6 + (cx - last[0]) * 0.4; vy = vy * 0.6 + (cy - last[1]) * 0.4; } else vx = vy = 0;
      last = [cx, cy, sz];
      const ax = Math.max(-sz, Math.min(sz, vx * LOOKAHEAD)), ay = Math.max(-(y1 - y0), Math.min(y1 - y0, vy * LOOKAHEAD));
      // 받을 범위: 보이는 범위 + 앞쪽(속도 방향) + 둘레 한 칸
      const ahead = (lv) => rectOf(lv, x0 + Math.min(0, ax), y0 + Math.min(0, ay), x1 + Math.max(0, ax), y1 + Math.max(0, ay), 1);
      const want = [];   // [우선순위, lv, key]
      // 거친 것부터: [목표/4, 목표/2, 목표] 중 살아 있는 것
      const lvls = zs.filter((z) => z <= target && !L[z].dead).slice(-3).map((z) => L[z]);
      // 칸 수 예산: 쓰는 범위가 아틀라스를 넘지 않게 앞쪽·둘레 → 거친 단계 순으로 뺀다
      let rs = lvls.map((lv) => [lv, ahead(lv), rectOf(lv, x0, y0, x1, y1)]);
      const free = SLOTS - reserved;
      if (rs.reduce((n, r) => n + count(r[1]), 0) > free) rs = rs.map(([lv, r, v]) => [lv, v, v]);
      while (rs.reduce((n, r) => n + count(r[1]), 0) > free && rs.length > 1) rs = rs.slice(1);
      rs.forEach(([lv, r, v], li) => {
        const vc = [(v[0] + v[2]) / 2, (v[1] + v[3]) / 2];
        for (let ty = r[1]; ty <= r[3]; ty++) for (let tx = r[0]; tx <= r[2]; tx++) {
          const key = ty * lv.GW + tx;
          if (lv.solid[key]) continue;
          const vis = tx >= v[0] && tx <= v[2] && ty >= v[1] && ty <= v[3];
          const e = lv.tiles.get(key);
          if (e) { e.used = frame; if (e.slot >= 0) slotUsed[e.slot] = frame; }
          if (!e || e.st === 'ready' || (e.st === 'err' && performance.now() - e.at > RETRY_MS)) {
            // 순서: 보이는 칸(거친 단계부터: 적고 빨리 온다) → 앞쪽·둘레(거친 단계부터)
            want.push([(vis ? 0 : 1000) + li * 100 + Math.hypot(tx - vc[0], ty - vc[1]), lv, key]);
          }
        }
      });
      want.sort((a, b) => a[0] - b[0]);
      let n = 0;
      for (const [, lv, key] of want) {
        const e = lv.tiles.get(key);
        if (e && e.st === 'ready') { if (n < MAX_UPLOAD && upload(lv, key, e)) n++; }
        else if (inFlight < MAX_FETCH && (!e || e.st === 'err')) fetchTile(lv, key);
      }
      // 오래 안 쓴 받은 타일(빠르게 지나간 곳)은 버린다
      if (frame % 60 === 0) for (const z of zs) for (const [k, e] of L[z].tiles) if (e.st === 'ready' && e.used < frame - 120) { e.bmp.close?.(); L[z].tiles.delete(k); }
      for (const z of zs) {
        const lv = L[z];
        if (!lv.dirty) continue;
        gl.bindTexture(gl.TEXTURE_2D, lv.tex);
        gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
        gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, lv.GW, lv.GH, gl.RGBA, gl.UNSIGNED_BYTE, lv.idx);
        lv.dirty = false;
      }
      // 그릴 단계: 목표부터 거친 쪽으로, 보이는 칸이 전부 있는 첫 단계. 지금 그리는 단계보다 높으면 UP_FRAMES 연속일 때만
      for (const z of zs) streak[z] = z <= target && !L[z].dead && resident(L[z], rectOf(L[z], x0, y0, x1, y1)) ? (streak[z] || 0) + 1 : 0;
      let pick = 1;
      for (let i = zs.length - 1; i >= 0; i--) {
        const z = zs[i];
        if (streak[z] > 0 && (z <= drawn || streak[z] >= UP_FRAMES)) { pick = z; break; }
      }
      return (drawn = pick);
    },
    stats() {
      const o = { inFlight };
      for (const z of zs) {
        let up = 0, ready = 0;
        for (const e of L[z].tiles.values()) { if (e.st === 'up') up++; else if (e.st === 'ready') ready++; }
        o['z' + z] = { up, ready, dead: L[z].dead };
      }
      return o;
    },
    // 추정 GPU 메모리(바이트): 아틀라스 + 색인
    bytes: SX * TILE * SY * TILE * 4 + zs.reduce((n, z) => n + L[z].GW * L[z].GH * 4, 0),
  };
}
