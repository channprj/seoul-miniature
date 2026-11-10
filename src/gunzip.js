// 최소 gunzip(RFC 1952 + RFC 1951 inflate). DecompressionStream 이 없는 구형 WebKit(iOS 16.3 이하) 대비.
// 장면 데이터(수백 KB) 한 번 푸는 용도라 속도보다 짧고 의존성 없는 쪽을 택했다. 구조는 zlib 의 puff.c 를 따른다.
const LBASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258];
const LEXT = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0];
const DBASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577];
const DEXT = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13];
const ORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15];

// 정규 허프만 표: 길이별 개수 + 길이순 기호
function table(lengths, n) {
  const counts = new Uint16Array(16), offs = new Uint16Array(16), syms = new Uint16Array(n);
  for (let i = 0; i < n; i++) counts[lengths[i]]++;
  counts[0] = 0;
  for (let i = 1; i < 16; i++) offs[i] = offs[i - 1] + counts[i - 1];
  for (let i = 0; i < n; i++) if (lengths[i]) syms[offs[lengths[i]]++] = i;
  return { counts, syms };
}

export function inflateRaw(src, sizeHint = src.length * 4) {
  let out = new Uint8Array(Math.max(1024, sizeHint)), op = 0;
  let pos = 0, bb = 0, bc = 0;
  const need = (n) => { if (op + n > out.length) { const o = new Uint8Array(Math.max(out.length * 2, op + n)); o.set(out); out = o; } };
  const bits = (n) => {
    while (bc < n) { if (pos >= src.length) throw new Error('inflate: 입력이 모자람'); bb |= src[pos++] << bc; bc += 8; }
    const v = bb & ((1 << n) - 1); bb >>>= n; bc -= n; return v;
  };
  const decode = (t) => {
    let code = 0, first = 0, index = 0;
    for (let len = 1; len < 16; len++) {
      code |= bits(1);
      const count = t.counts[len];
      if (code - first < count) return t.syms[index + code - first];
      index += count; first += count; first <<= 1; code <<= 1;
    }
    throw new Error('inflate: 잘못된 허프만 부호');
  };
  const codes = (lt, dt) => {
    for (;;) {
      let s = decode(lt);
      if (s < 256) { need(1); out[op++] = s; continue; }
      if (s === 256) return;
      s -= 257;
      const len = LBASE[s] + bits(LEXT[s]);
      const ds = decode(dt);
      const dist = DBASE[ds] + bits(DEXT[ds]);
      if (dist > op) throw new Error('inflate: 거리가 출력보다 김');
      need(len);
      for (let i = 0; i < len; i++, op++) out[op] = out[op - dist];   // 겹치는 복사는 바이트 단위여야 한다
    }
  };
  let fixed = null;
  for (let last = 0; !last;) {
    last = bits(1);
    const type = bits(2);
    if (type === 0) {
      bb = 0; bc = 0;                                  // 바이트 경계로 맞춘다
      const len = src[pos] | (src[pos + 1] << 8);
      pos += 4;
      need(len); out.set(src.subarray(pos, pos + len), op); op += len; pos += len;
    } else if (type === 1) {
      if (!fixed) {
        const l = new Uint8Array(288);
        l.fill(8, 0, 144); l.fill(9, 144, 256); l.fill(7, 256, 280); l.fill(8, 280, 288);
        fixed = [table(l, 288), table(new Uint8Array(30).fill(5), 30)];
      }
      codes(fixed[0], fixed[1]);
    } else if (type === 2) {
      const hlit = bits(5) + 257, hdist = bits(5) + 1, hclen = bits(4) + 4;
      const cl = new Uint8Array(19);
      for (let i = 0; i < hclen; i++) cl[ORDER[i]] = bits(3);
      const ct = table(cl, 19);
      const L = new Uint8Array(hlit + hdist);
      for (let i = 0; i < hlit + hdist;) {
        const s = decode(ct);
        if (s < 16) { L[i++] = s; continue; }
        let rep, v = 0;
        if (s === 16) { if (!i) throw new Error('inflate: 반복할 길이 없음'); v = L[i - 1]; rep = 3 + bits(2); }
        else if (s === 17) rep = 3 + bits(3);
        else rep = 11 + bits(7);
        while (rep--) L[i++] = v;
      }
      codes(table(L.subarray(0, hlit), hlit), table(L.subarray(hlit), hdist));
    } else throw new Error('inflate: 잘못된 블록 형식');
  }
  return out.subarray(0, op);
}

export function gunzip(u8) {
  if (u8[0] !== 0x1f || u8[1] !== 0x8b || u8[2] !== 8) throw new Error('gzip 형식이 아님');
  const flg = u8[3];
  let p = 10;
  if (flg & 4) p += 2 + (u8[p] | (u8[p + 1] << 8));   // FEXTRA
  if (flg & 8) while (u8[p++]);                         // FNAME
  if (flg & 16) while (u8[p++]);                        // FCOMMENT
  if (flg & 2) p += 2;                                  // FHCRC
  const n = u8.length;
  const isize = (u8[n - 4] | (u8[n - 3] << 8) | (u8[n - 2] << 16) | (u8[n - 1] << 24)) >>> 0;
  return inflateRaw(u8.subarray(p, n - 8), isize);
}
