// 화면 갈무리 순수 로직 검사 (node --test). 캔버스·공유는 브라우저 API 라 여기서 부르지 않는다.
import test from 'node:test';
import assert from 'node:assert/strict';
import { stripLayout, isInApp, snapName, wrapParts } from '../src/snap.js';

test('띠 높이: 작은 화면은 22, 큰 화면은 64, 그 사이는 높이의 3.5%', () => {
  // 100*0.035 → 4, 22로 올린다. 글자·여백은 잘린 높이에서 다시 반올림.
  assert.ok(Math.round(100 * 0.035) < 22);
  assert.deepEqual(stripLayout(320, 100), { bandH: 22, font: 11, pad: 9 });
  assert.deepEqual(stripLayout(320, 1), { bandH: 22, font: 11, pad: 9 });
  // 반올림이 이미 22·64 이면 더 밀지 않는다
  assert.equal(Math.round(628 * 0.035), 22);
  assert.equal(stripLayout(320, 628).bandH, 22);
  assert.equal(Math.round(1828 * 0.035), 64);
  assert.equal(stripLayout(320, 1828).bandH, 64);
  // 3000*0.035 → 105, 64로 내린다
  assert.ok(Math.round(3000 * 0.035) > 64);
  assert.deepEqual(stripLayout(320, 3000), { bandH: 64, font: 32, pad: 26 });
  assert.deepEqual(stripLayout(320, 10000), { bandH: 64, font: 32, pad: 26 });
  // 1000*0.035 = 35 그대로. font = round(17.5) = 18, pad = round(14) = 14
  assert.deepEqual(stripLayout(320, 1000), { bandH: 35, font: 18, pad: 14 });
  assert.deepEqual(stripLayout(320, 800), { bandH: 28, font: 14, pad: 11 });
  // 가로는 띠 크기에 안 들어간다
  assert.deepEqual(stripLayout(1, 1000), stripLayout(8000, 1000));
});

test('인앱 브라우저: 목록에 있는 토큰만, 대소문자 무시', () => {
  assert.equal(isInApp('Mozilla/5.0 KAKAOTALK/10.0'), true);
  assert.equal(isInApp('kakaotalk'), true);
  assert.equal(isInApp('Mozilla Instagram 250.0'), true);
  assert.equal(isInApp('Mozilla FBAN/1'), true);
  assert.equal(isInApp('Mozilla FBAV/1'), true);
  assert.equal(isInApp('Line/12.1.0'), true);
  assert.equal(isInApp('NAVER(inapp; search; 190)'), true);
  assert.equal(isInApp('Twitter for iPhone'), true);
  assert.equal(isInApp('DaumApps/1.0'), true);
  assert.equal(isInApp(''), false);
  assert.equal(isInApp('Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'), false);
  assert.equal(isInApp('Mozilla/5.0 (iPhone) Version/17.0 Mobile/15E148 Safari/604.1'), false);
  assert.equal(isInApp('Mozilla Line 12'), false);          // 'Line/' 가 아니면 라인이 아니다
  assert.equal(isInApp('NAVER'), false);                    // '(inapp' 이 없는 네이버
  assert.equal(isInApp('daum'), false);
  assert.equal(isInApp('FB_IAB'), false);                   // FBAN·FBAV 만
  assert.equal(isInApp(), isInApp(navigator.userAgent));    // 기본 인자는 부를 때 navigator 를 본다
});

test('파일 이름: 로컬 시각 YYYYMMDD-HHMMSS', () => {
  assert.equal(snapName(new Date(2026, 0, 2, 3, 4, 5)), 'seoul-miniature-20260102-030405.png');
  assert.equal(snapName(new Date(2026, 11, 31, 23, 59, 59)), 'seoul-miniature-20261231-235959.png');
  assert.match(snapName(new Date()), /^seoul-miniature-\d{8}-\d{6}\.png$/);
});

test('출처 띠 줄바꿈: 조각을 버리지 않고 폭에 맞춰 여러 줄로 나눈다', () => {
  const parts = ['지도 데이터 © OSM', 'Overture', '국토교통부', '국가유산청'];
  const fits = (n) => (t) => t.length <= n;
  assert.deepEqual(wrapParts(parts, fits(100)), [parts.join(' · ')]);
  const two = wrapParts(parts, fits(26));
  assert.ok(two.length >= 2 && two.every((l) => l.length <= 26));
  assert.equal(two.join(' · '), parts.join(' · '));
  assert.deepEqual(wrapParts(parts, fits(3)), parts, '한 조각이 폭보다 길어도 조각은 남는다');
});
