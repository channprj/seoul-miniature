// 최소 PNG 디코더(8 비트, 비인터레이스: 회색·RGB·팔레트·RGBA) → RGBA 바이트.
// 깊이·클래스 맵은 "그림"이 아니라 수치다. 브라우저 디코더에 맡기면 WebKit(iOS 사파리)이 회색조 PNG 에 감마·색공간 변환을 걸어
// 클래스 값(0~11)이 다른 수로 바뀐다(createImageBitmap 의 colorSpaceConversion: 'none' 도 막지 못한다). 그러면 지붕·수목 칸이
// 궁궐 벽·건물 벽으로 읽혀 밤에 조명·창문 불빛이 0.5 m 칸 단위 점무늬로 켜진다. 그래서 바이트를 직접 푼다.
import { inflateRaw } from './gunzip.js';

const u32 = (b, o) => ((b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]) >>> 0;

async function inflateZlib(z, size) {
  if (typeof DecompressionStream === 'function') {
    try {
      const ds = new Blob([z]).stream().pipeThrough(new DecompressionStream('deflate'));
      return new Uint8Array(await new Response(ds).arrayBuffer());
    } catch { /* 아래 JS inflate */ }
  }
  return inflateRaw(z.subarray(2, z.length - 4), size);   // zlib 머리 2 바이트·꼬리 adler32 4 바이트를 뗀다
}

// → { width, height, data: Uint8ClampedArray(RGBA) }. 지원하지 않는 형식이면 예외.
export async function decodePng(u8) {
  if (u32(u8, 0) !== 0x89504e47 || u32(u8, 4) !== 0x0d0a1a0a) throw new Error('png: 서명이 아님');
  let w = 0, h = 0, depth = 0, ctype = 0, lace = 0, pal = null, trns = null;
  const idat = [];
  for (let o = 8; o + 8 <= u8.length;) {
    const len = u32(u8, o), type = String.fromCharCode(u8[o + 4], u8[o + 5], u8[o + 6], u8[o + 7]), d = o + 8;
    if (type === 'IHDR') { w = u32(u8, d); h = u32(u8, d + 4); depth = u8[d + 8]; ctype = u8[d + 9]; lace = u8[d + 12]; }
    else if (type === 'PLTE') pal = u8.subarray(d, d + len);
    else if (type === 'tRNS') trns = u8.subarray(d, d + len);
    else if (type === 'IDAT') idat.push(u8.subarray(d, d + len));
    else if (type === 'IEND') break;
    o = d + len + 4;
  }
  const ch = { 0: 1, 2: 3, 3: 1, 6: 4 }[ctype];
  if (!w || !h || depth !== 8 || !ch || lace || (ctype === 3 && !pal)) throw new Error(`png: 지원하지 않는 형식(depth ${depth}, type ${ctype}, interlace ${lace})`);
  let z = idat[0];
  if (idat.length > 1) { z = new Uint8Array(idat.reduce((n, p) => n + p.length, 0)); let p = 0; for (const c of idat) { z.set(c, p); p += c.length; } }
  const stride = w * ch, raw = await inflateZlib(z, (stride + 1) * h);
  if (raw.length < (stride + 1) * h) throw new Error('png: 데이터가 모자람');
  // 필터 풀기(제자리)
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)], r = y * (stride + 1) + 1, up = r - stride - 1;
    if (f === 1) { for (let i = ch; i < stride; i++) raw[r + i] += raw[r + i - ch]; }
    else if (f === 2) { if (y) for (let i = 0; i < stride; i++) raw[r + i] += raw[up + i]; }
    else if (f === 3) { for (let i = 0; i < stride; i++) raw[r + i] += ((i >= ch ? raw[r + i - ch] : 0) + (y ? raw[up + i] : 0)) >> 1; }
    else if (f === 4) {
      for (let i = 0; i < stride; i++) {
        const a = i >= ch ? raw[r + i - ch] : 0, b = y ? raw[up + i] : 0, c = i >= ch && y ? raw[up + i - ch] : 0;
        const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
        raw[r + i] += pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
      }
    } else if (f !== 0) throw new Error('png: 알 수 없는 필터 ' + f);
  }
  const data = new Uint8ClampedArray(w * h * 4);
  for (let y = 0, o = 0; y < h; y++) {
    let r = y * (stride + 1) + 1;
    for (let x = 0; x < w; x++, o += 4, r += ch) {
      if (ctype === 0) { data[o] = data[o + 1] = data[o + 2] = raw[r]; data[o + 3] = 255; }
      else if (ctype === 2) { data[o] = raw[r]; data[o + 1] = raw[r + 1]; data[o + 2] = raw[r + 2]; data[o + 3] = 255; }
      else if (ctype === 6) { data[o] = raw[r]; data[o + 1] = raw[r + 1]; data[o + 2] = raw[r + 2]; data[o + 3] = raw[r + 3]; }
      else { const i = raw[r]; data[o] = pal[i * 3]; data[o + 1] = pal[i * 3 + 1]; data[o + 2] = pal[i * 3 + 2]; data[o + 3] = trns && i < trns.length ? trns[i] : 255; }
    }
  }
  return { width: w, height: h, data };
}
