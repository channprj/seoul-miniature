// JS gunzip(구형 WebKit 대비)이 zlib 과 같은 바이트를 내는지 (node --test)
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import zlib from 'node:zlib';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { gunzip } from '../src/gunzip.js';

const here = path.dirname(fileURLToPath(import.meta.url));

test('scene.json.gz 를 zlib 과 똑같이 푼다', () => {
  const gz = fs.readFileSync(path.resolve(here, '../assets/web-poc/scene.json.gz'));
  const want = zlib.gunzipSync(gz);
  const got = gunzip(new Uint8Array(gz));
  assert.equal(got.length, want.length);
  assert.ok(Buffer.from(got).equals(want));
});

test('저장·고정·동적 블록과 긴 거리 복사를 모두 푼다', () => {
  const rnd = Buffer.alloc(70000); let s = 7;
  for (let i = 0; i < rnd.length; i++) { s = (s * 1103515245 + 12345) & 0x7fffffff; rnd[i] = s >>> 16; }
  const rep = Buffer.from('경복궁 '.repeat(5000));
  for (const [buf, level] of [[rnd, 0], [Buffer.from('abc'), 9], [rep, 9], [Buffer.concat([rep, rnd, rep]), 6], [Buffer.alloc(0), 9]]) {
    const gz = zlib.gzipSync(buf, { level });
    assert.ok(Buffer.from(gunzip(new Uint8Array(gz))).equals(buf), `len ${buf.length} level ${level}`);
  }
  // 고정 허프만 블록 강제
  const fixed = zlib.gzipSync(Buffer.from('hello hello hello'), { strategy: zlib.constants.Z_FIXED });
  assert.equal(Buffer.from(gunzip(new Uint8Array(fixed))).toString(), 'hello hello hello');
});
