// 고층 지도의 밤 창문(src/winlights.js): 시각 곡선, 층마다 다른 켜진 비율, 셰이더 조각이 JS 판과 같은 곡선인지.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { SCHEDULE, ratioAt, floorRatio, WINDOW_GLSL, WINDOW_GRID } from '../src/winlights.js';
import { MAPS } from '../src/maps.js';

const here = path.dirname(fileURLToPath(import.meta.url));

test('켜진 비율 곡선: 사무동은 밤이 깊을수록 꺼지고, 아파트는 저녁에 많다', () => {
  for (const k of ['office', 'home']) for (let h = 0; h < 24; h += 0.25) {
    const r = ratioAt(k, h);
    assert.ok(r >= 0 && r <= 1, `${k} ${h}시 ${r}`);
  }
  // 자정에서 끊기지 않는다
  for (const k of ['office', 'home']) assert.ok(Math.abs(ratioAt(k, 23.999) - ratioAt(k, 0)) < 0.01);
  // 사무동: 퇴근 뒤 줄곧 준다
  const off = [18, 19, 20, 21, 22, 23, 24, 25, 26].map((h) => ratioAt('office', h));
  for (let i = 1; i < off.length; i++) assert.ok(off[i] <= off[i - 1] + 1e-9, `사무동 ${18 + i}시 ${off[i]} > ${off[i - 1]}`);
  assert.ok(ratioAt('office', 2) < ratioAt('office', 19) * 0.25);
  // 아파트: 저녁(20~22시)이 해 질 녘·새벽보다 많고, 그 시간엔 사무동보다 많다
  const eve = Math.max(ratioAt('home', 20), ratioAt('home', 21), ratioAt('home', 22));
  assert.ok(eve > ratioAt('home', 18) && eve > ratioAt('home', 1) * 2, `아파트 저녁 ${eve}`);
  for (const h of [21, 22, 23, 0]) assert.ok(ratioAt('home', h) > ratioAt('office', h), `${h}시 아파트 < 사무동`);
  assert.ok(ratioAt('home', 4) < 0.1 && ratioAt('office', 4) < 0.1);
});

test('층마다 켜진 비율이 다르고, 층들의 평균은 시각 곡선 값', () => {
  for (const base of [0.05, 0.12, 0.3, 0.45, 0.6]) {
    let s = 0, full = 0, dark = 0;
    const N = 4000;
    for (let i = 0; i < N; i++) {
      const f = floorRatio(base, (i + 0.5) / N);
      assert.ok(f >= 0 && f <= 1);
      s += f; if (f > 0.85) full++; if (f < base * 0.2) dark++;
    }
    assert.ok(Math.abs(s / N - base) < 0.02, `base ${base} 평균 ${s / N}`);
    if (base >= 0.3) assert.ok(full / N > 0.08 && dark / N > 0.2, `base ${base}: 다 켜진 층 ${full / N}, 꺼진 층 ${dark / N}`);
  }
});

test('셰이더 조각의 시각 곡선은 JS 판과 같다(같은 점·같은 식)', () => {
  // GLSL 함수 winOffice·winHome 을 JS 로 옮겨 값을 비교한다(mix·clamp·mod 만 쓴다)
  const fn = (name) => {
    const m = WINDOW_GLSL.match(new RegExp(`float ${name}\\(float h\\)\\{([^}]*)\\}`));
    assert.ok(m, `${name} 없음`);
    const body = m[1].replace(/float /g, 'let ');
    // eslint-disable-next-line no-new-func
    return new Function('h', `const mix = (a, b, t) => a + (b - a) * t, clamp = (x, a, b) => Math.min(b, Math.max(a, x)), mod = (x, y) => x - y * Math.floor(x / y);${body}`);
  };
  const go = fn('winOffice'), gh = fn('winHome');
  for (let h = 0; h < 24; h += 0.37) {
    assert.ok(Math.abs(go(h) - ratioAt('office', h)) < 1e-9, `사무동 ${h}`);
    assert.ok(Math.abs(gh(h) - ratioAt('home', h)) < 1e-9, `아파트 ${h}`);
  }
  assert.equal(SCHEDULE.office[0][0], 0); assert.equal(SCHEDULE.office.at(-1)[0], 24);
  // 층고·칸 폭이 조각에 그대로 들어간다
  assert.ok(WINDOW_GLSL.includes(String(WINDOW_GRID.office.floor)) && WINDOW_GLSL.includes(String(WINDOW_GRID.home.floor)));
});

test('창 격자는 여의도에서만, 벽면에만(지붕·헬리패드 제외)', () => {
  assert.equal(MAPS.yeouido.windows, 'grid');
  assert.ok(!MAPS.gyeongbok.windows, '경복궁은 예전 식 그대로');
  const src = fs.readFileSync(path.resolve(here, '../src/render.js'), 'utf8');
  const blk = src.slice(src.indexOf('#ifdef WINGRID\n      //'), src.indexOf('#else', src.indexOf('#ifdef WINGRID\n      //')));
  assert.ok(blk.length > 100, '조명 패스에 창 격자 갈래가 없다');
  assert.match(blk, /if \(wall > 0\.5\)/, '수직면 판정 없이 켠다');
  assert.match(blk, /winCell\(/);
});
