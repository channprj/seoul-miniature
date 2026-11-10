// 원본 해상도 배경 타일 캐시(휴대폰 경로). 절반 해상도 그림(bg_1x)만 올려 둔 기기가 확대했을 때
// 보이는 칸의 0.25 m/px 타일(redraw/tiles/z2_x_y.png, 256 그림 px)만 받아 고정 크기 아틀라스에 올린다.
//   아틀라스 8×8 칸(2048², RGBA8) + 칸 색인(타일 격자 크기, RGBA8: r,g = 칸 위치, b = 있음).
//   셰이더는 색인에 없으면 bg_1x 를 읽는다 → 받는 동안 빈칸·깜빡임 없이 절반 해상도로 보였다가 또렷해진다.
//   교체는 LRU. 이번 프레임에 보이는 타일은 내보내지 않는다.
import { optionalImage } from './assets.js';

export const TILE = 256;
const SX = 8, SY = 8, SLOTS = SX * SY;
const MAX_FETCH = 4, MAX_UPLOAD = 3, RETRY_MS = 3000;

export function createBgTiles(gl, W, H, load = (tx, ty) => optionalImage(`redraw/tiles/z2_${tx}_${ty}.png`)) {
  const GW = Math.ceil(W * 2 / TILE), GH = Math.ceil(H * 2 / TILE);
  const mk = (w, h) => {
    const t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texStorage2D(gl.TEXTURE_2D, 1, gl.RGBA8, w, h);
    for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.NEAREST], [gl.TEXTURE_MAG_FILTER, gl.NEAREST], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
    return t;
  };
  const atlas = mk(SX * TILE, SY * TILE), index = mk(GW, GH);
  const idx = new Uint8Array(GW * GH * 4);
  let idxDirty = true;
  const tiles = new Map();          // key → { st: 'load'|'ready'|'up'|'miss'|'err', slot, used, bmp, at }
  const owner = new Int32Array(SLOTS).fill(-1), slotUsed = new Float64Array(SLOTS);
  let inFlight = 0, misses = 0, ups = 0, disabled = false, frame = 0;

  const fetchTile = (key) => {
    const tx = key % GW, ty = (key / GW) | 0;
    const e = { st: 'load', slot: -1, used: frame, bmp: null, at: 0 };   // used = 마지막으로 범위 안에 있던 프레임
    tiles.set(key, e); inFlight++;
    load(tx, ty).then((bmp) => {
      if (!bmp) { e.st = 'miss'; if (++misses >= 3 && ups === 0) disabled = true; return; }   // 타일이 배포되지 않은 판(오프라인 HTML 등)
      e.bmp = bmp; e.st = 'ready';
    }, () => { e.st = 'err'; e.at = performance.now(); }).finally(() => { inFlight--; });
  };
  const upload = (key, e) => {
    // 빈 칸, 없으면 이번 프레임에 안 쓰인 가장 오래된 칸
    let s = -1, best = Infinity;
    for (let i = 0; i < SLOTS; i++) {
      if (owner[i] < 0) { s = i; break; }
      const o = tiles.get(owner[i]);
      if (o && o.used < frame && slotUsed[i] < best) { best = slotUsed[i]; s = i; }
    }
    if (s < 0) return false;
    if (owner[s] >= 0) { tiles.delete(owner[s]); idx.fill(0, owner[s] * 4, owner[s] * 4 + 4); }
    const sx = s % SX, sy = (s / SX) | 0;
    gl.bindTexture(gl.TEXTURE_2D, atlas);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, sx * TILE, sy * TILE, gl.RGBA, gl.UNSIGNED_BYTE, e.bmp);
    e.bmp.close?.(); e.bmp = null; e.st = 'up'; e.slot = s; ups++;
    owner[s] = key; slotUsed[s] = frame;
    idx.set([sx, sy, 255, 255], key * 4); idxDirty = true;
    return true;
  };

  return {
    atlas, index,
    get active() { return !disabled; },
    // 이번 프레임에 쓸 그림 px 범위 [bx0, bx1) × [by0, by1). 보이는 타일 먼저(가운데부터), 칸이 남으면 한 칸 둘레를 미리 받는다.
    // 범위(둘레 포함) 안의 타일은 이번 프레임에 '쓰임' → 내보내지 않는다. 범위는 칸 수(64)를 넘지 않게 둘레를 뺀다.
    update(bx0, by0, bx1, by1) {
      frame++;
      if (disabled) return;
      const tx0 = Math.max(0, Math.floor(bx0 / TILE)), ty0 = Math.max(0, Math.floor(by0 / TILE));
      const tx1 = Math.min(GW - 1, Math.floor((bx1 - 1) / TILE)), ty1 = Math.min(GH - 1, Math.floor((by1 - 1) / TILE));
      const cx = (tx0 + tx1) / 2, cy = (ty0 + ty1) / 2;
      let rx0 = Math.max(0, tx0 - 1), ry0 = Math.max(0, ty0 - 1), rx1 = Math.min(GW - 1, tx1 + 1), ry1 = Math.min(GH - 1, ty1 + 1);
      if ((rx1 - rx0 + 1) * (ry1 - ry0 + 1) > SLOTS) { rx0 = tx0; ry0 = ty0; rx1 = tx1; ry1 = ty1; }
      const want = [];
      for (let ty = ry0; ty <= ry1; ty++) {
        for (let tx = rx0; tx <= rx1; tx++) {
          const vis = tx >= tx0 && tx <= tx1 && ty >= ty0 && ty <= ty1;
          const key = ty * GW + tx, e = tiles.get(key);
          if (e) { e.used = frame; if (e.slot >= 0) slotUsed[e.slot] = frame; }
          if (!e || e.st === 'ready' || (e.st === 'err' && performance.now() - e.at > RETRY_MS)) want.push([(vis ? 0 : 100) + Math.hypot(tx - cx, ty - cy), key]);
        }
      }
      want.sort((a, b) => a[0] - b[0]);
      let n = 0;
      for (const [, key] of want) {
        const e = tiles.get(key);
        if (e && e.st === 'ready') { if (n < MAX_UPLOAD && upload(key, e)) n++; }
        else if (inFlight < MAX_FETCH) fetchTile(key);
      }
      // 받았지만 범위를 벗어난 지 오래된 타일(빠르게 지나간 곳)은 버린다
      if (frame % 60 === 0) for (const [k, e] of tiles) if (e.st === 'ready' && e.used < frame - 120) { e.bmp.close?.(); tiles.delete(k); }
      if (idxDirty) {
        gl.bindTexture(gl.TEXTURE_2D, index);
        gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
        gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, GW, GH, gl.RGBA, gl.UNSIGNED_BYTE, idx);
        idxDirty = false;
      }
    },
    stats() { let up = 0, ready = 0; for (const e of tiles.values()) { if (e.st === 'up') up++; else if (e.st === 'ready') ready++; } return { uploaded: up, ready, inFlight, disabled }; },
    // 추정 GPU 메모리(바이트): 아틀라스 + 색인
    bytes: SX * TILE * SY * TILE * 4 + GW * GH * 4,
  };
}
