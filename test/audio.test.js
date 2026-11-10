// 배경음 상태 로직 검사 (node --test). 브라우저 API 는 쓰지 않는 부분만.
import test from 'node:test';
import assert from 'node:assert/strict';
import { nightState, targetGains, plan, loopPoints, readPref, VOL, NIGHT_DIP, NIGHT_ON, NIGHT_OFF, FADE, XFADE, PAD, GRID } from '../src/audio.js';

test('밤 판정은 히스테리시스로 경계에서 떨지 않는다', () => {
  assert.equal(nightState(false, 1), false);
  assert.equal(nightState(false, NIGHT_ON - 0.01), true);
  assert.equal(nightState(true, NIGHT_ON + 0.05), true);       // 사이 구간은 이전 상태 유지
  assert.equal(nightState(false, NIGHT_ON + 0.05), false);
  assert.equal(nightState(true, NIGHT_OFF + 0.01), false);
  // 슬라이더를 경계 근처에서 왔다 갔다 해도 전환은 한 번
  let n = false, flips = 0;
  for (const d of [0.5, 0.3, 0.2, 0.3, 0.4, 0.3, 0.2, 0.3, 0.44, 0.26]) { const m = nightState(n, d); if (m !== n) flips++; n = m; }
  assert.equal(flips, 1);
  assert.equal(n, true);
});

test('목표 음량: 꺼짐·낮·밤(밤 곡 유무)', () => {
  assert.deepEqual(targetGains({ on: false, night: true, hasNight: true }), { day: 0, night: 0 });
  assert.deepEqual(targetGains({ on: true, night: false, hasNight: true }), { day: VOL, night: 0 });
  assert.deepEqual(targetGains({ on: true, night: true, hasNight: true }), { day: 0, night: VOL });
  assert.deepEqual(targetGains({ on: true, night: true, hasNight: false }), { day: VOL * NIGHT_DIP, night: 0 });
  assert.deepEqual(targetGains({ on: true, night: false, hasNight: false }), { day: VOL, night: 0 });
});

test('전환 계획: 바뀐 트랙만, 켜고 끌 때 1초·낮밤 3.5초', () => {
  const off = { day: 0, night: 0 }, day = { day: VOL, night: 0 }, nite = { day: 0, night: VOL };
  assert.deepEqual(plan(off, day, true), [{ track: 'day', gain: VOL, sec: FADE }]);
  assert.deepEqual(plan(day, nite, false), [{ track: 'day', gain: 0, sec: XFADE }, { track: 'night', gain: VOL, sec: XFADE }]);
  assert.deepEqual(plan(day, day, false), []);
  assert.deepEqual(plan(nite, off, true).map((s) => s.sec), [FADE]);
});

test('루프 구간: 파일 길이만으로 곡마다 다른 루프 길이를 찾고, 지연·패딩에 흔들리지 않는다', () => {
  const near = (lp, start, end) => { assert.ok(Math.abs(lp.start - start) < 1e-9 && Math.abs(lp.end - end) < 1e-9, JSON.stringify(lp)); };
  for (const L of [60, 67.1, 72, 81.3, 89.9]) {
    const exact = L + 2 * PAD;
    near(loopPoints(exact), PAD, PAD + L);                       // 디코더가 지연·패딩을 지운 경우
    near(loopPoints(exact + 1105 / 48000 + 0.04), PAD, PAD + L); // 안 지운 경우(앞 지연 + 끝 패딩 < GRID)
    near(loopPoints(exact + GRID - 0.002), PAD, PAD + L);
  }
  // 이 구성이 아닌 짧은 파일은 통째로 돈다
  assert.deepEqual(loopPoints(1.5), { start: 0, end: 1.5 });
  assert.deepEqual(loopPoints(NaN).start, 0);
});

test('설정: URL 이 우선, 저장값이 없으면 꺼짐', () => {
  assert.equal(readPref('?bgm=1'), true);
  assert.equal(readPref('?bgm=0'), false);
  assert.equal(readPref(''), false);
});
