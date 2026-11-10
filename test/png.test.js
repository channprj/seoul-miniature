// png.js: 수치 맵(깊이·클래스)을 브라우저 디코더 없이 푼 값이 PNG 에 적힌 값 그대로인지.
import test from 'node:test';
import assert from 'node:assert/strict';
import zlib from 'node:zlib';
import { decodePng } from '../src/png.js';

const crcT = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
const crc = (b) => { let c = 0xffffffff; for (const v of b) c = crcT[(c ^ v) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
const chunk = (type, data) => { const b = Buffer.alloc(12 + data.length); b.writeUInt32BE(data.length, 0); b.write(type, 4, 'latin1'); data.copy(b, 8); b.writeUInt32BE(crc(b.subarray(4, 8 + data.length)), 8 + data.length); return b; };
const paeth = (a, b, c) => { const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c); return pa <= pb && pa <= pc ? a : pb <= pc ? b : c; };
// 줄마다 필터 0~4 를 돌려 가며 쓴다
function encode(w, h, ch, ctype, px, split = 1) {
  const stride = w * ch, raw = Buffer.alloc((stride + 1) * h);
  for (let y = 0; y < h; y++) {
    const f = y % 5; raw[y * (stride + 1)] = f;
    for (let i = 0; i < stride; i++) {
      const v = px[y * stride + i], a = i >= ch ? px[y * stride + i - ch] : 0, b = y ? px[(y - 1) * stride + i] : 0, c = i >= ch && y ? px[(y - 1) * stride + i - ch] : 0;
      raw[y * (stride + 1) + 1 + i] = (v - [0, a, b, (a + b) >> 1, paeth(a, b, c)][f]) & 255;
    }
  }
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = ctype;
  const z = zlib.deflateSync(raw), parts = [];
  for (let i = 0; i < split; i++) parts.push(chunk('IDAT', z.subarray(Math.floor(z.length * i / split), Math.floor(z.length * (i + 1) / split))));
  return new Uint8Array(Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk('IHDR', ihdr), ...parts, chunk('IEND', Buffer.alloc(0))]));
}
const rnd = (seed) => () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296;

test('회색조 8 비트: 클래스 값이 그대로 나온다(필터 0~4, IDAT 여러 조각)', async () => {
  const w = 37, h = 23, r = rnd(7), px = Uint8Array.from({ length: w * h }, () => Math.floor(r() * 12));
  const m = await decodePng(encode(w, h, 1, 0, px, 3));
  assert.equal(m.width, w); assert.equal(m.height, h);
  for (let i = 0; i < w * h; i++) { assert.equal(m.data[i * 4], px[i]); assert.equal(m.data[i * 4 + 3], 255); }
});

test('RGB 8 비트: 깊이 맵의 두 바이트가 그대로 나온다', async () => {
  const w = 29, h = 31, r = rnd(3), px = Uint8Array.from({ length: w * h * 3 }, () => Math.floor(r() * 256));
  const m = await decodePng(encode(w, h, 3, 2, px));
  for (let i = 0; i < w * h; i++) for (let k = 0; k < 3; k++) assert.equal(m.data[i * 4 + k], px[i * 3 + k]);
});

test('지원하지 않는 형식은 예외(로더가 브라우저 디코더로 넘어간다)', async () => {
  await assert.rejects(decodePng(new Uint8Array(32)));
  const bad = encode(4, 4, 1, 0, new Uint8Array(16)); bad[24] = 16;   // 비트 깊이 16
  await assert.rejects(decodePng(bad));
});
