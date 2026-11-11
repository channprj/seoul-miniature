// 흐르는 구름 그림자(src/clouds.js): 세기와 이동. 셰이더는 같은 상수·같은 식으로 만들어진다(CLOUD_GLSL).
import test from 'node:test';
import assert from 'node:assert/strict';
import { WIND, CLOUD, CLOUD_GLSL, cloudAmount, cloudLean, cloudDrift, cloudCover } from '../src/clouds.js';

test('구름 그림자 세기: 밤 0, 해 질 녘 옅게, 비·눈·끔', () => {
  assert.equal(cloudAmount({ day: 0 }), 0);                       // 밤
  assert.equal(cloudAmount({ day: 0.2 }), 0);                     // 어스름
  assert.equal(cloudAmount({ day: 1 }), 1);                       // 한낮 맑음
  const dusk = cloudAmount({ day: 0.5 });
  assert.ok(dusk > 0.05 && dusk < 0.45, `해 질 녘 ${dusk}`);
  assert.ok(cloudAmount({ day: 1, rain: 1 }) <= 0.2);             // 비
  assert.ok(cloudAmount({ day: 1, winter: 1 }) < 0.5);            // 눈
  assert.equal(cloudAmount({ day: 1, on: false }), 0);            // 설정 끔
  assert.equal(cloudAmount({ day: 0, rain: 1, winter: 1 }), 0);
});

test('구름 그림자는 시간에 따라 바람 방향으로 흐르고, 같은 시각이면 같은 값', () => {
  const pts = []; for (let i = 0; i < 400; i++) pts.push([(i % 20) * 137 - 1300, Math.floor(i / 20) * 113 - 1100]);
  const at = (t, dx = 0, dy = 0) => pts.map(([x, y]) => cloudCover(x + dx, y + dy, t));
  const a = at(100), b = at(100);
  assert.deepEqual(a, b);                                          // 결정적
  assert.ok(a.every((v) => v >= 0 && v <= 1));
  const cov = a.filter((v) => v > 0.5).length / a.length;
  assert.ok(cov > 0.1 && cov < 0.6, `그림자 비율 ${cov}`);         // 지도 전체가 덮이거나 텅 비지 않는다
  // 60초 뒤: 제자리 값은 달라지고, 바람 따라 옮긴 자리의 값은 거의 같다(둘째 옥타브가 조금 더 빨리 흘러 모양이 천천히 변한다)
  const dt = 60, [dx, dy] = cloudDrift(dt);
  assert.ok(Math.abs(Math.hypot(dx, dy) - CLOUD.speed * dt) < 0.05);
  assert.ok(dx > 0 && dy < 0);                                     // 북서 → 남동
  assert.equal(Math.hypot(...cloudDrift(0)), 0);
  const still = at(100 + dt), moved = at(100 + dt, dx, dy);
  const mad = (u, v) => u.reduce((s, x, i) => s + Math.abs(x - v[i]), 0) / u.length;
  assert.ok(mad(a, still) > 0.08, `제자리 변화 ${mad(a, still)}`);
  assert.ok(mad(a, moved) < mad(a, still) * 0.5, `따라간 변화 ${mad(a, moved)} / 제자리 ${mad(a, still)}`);
  // 한 프레임(1/30초) 사이 변화는 아주 작다(깜빡이지 않는다)
  assert.ok(Math.max(...at(100 + 1 / 30).map((v, i) => Math.abs(v - a[i]))) < 0.02);
});

test('구름 그림자 높이 어긋남과 셰이더 상수', () => {
  assert.deepEqual(cloudLean([0, 0, 1]), [0, 0]);                  // 해가 머리 위: 어긋남 없음
  const l = cloudLean([0.6, 0, 0.8]); assert.ok(Math.abs(l[0] - 0.75) < 1e-9 && l[1] === 0);
  const low = cloudLean([0.7, -0.7, 0.1]); assert.ok(Math.abs(Math.hypot(...low) - CLOUD.maxLean) < 1e-9);   // 낮은 해: 한도
  assert.ok(Math.abs(Math.hypot(...WIND.dir) - 1) < 1e-3);
  for (const k of ['uCloud', 'uCloudLean', 'uTime', 'vnoise']) assert.ok(CLOUD_GLSL.includes(k));
  assert.ok(!/texture\(|sampler/.test(CLOUD_GLSL));                // 텍스처 없이 절차 잡음만
});
