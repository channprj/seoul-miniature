// 장소 바로가기와 자동 투어. 좌표는 지도 px(2752×1696 캔버스), vh 는 화면 세로에 담기는 지도 px 수.
// 설명 문구는 널리 알려진 일반 사실만 쓴다. 그림 속 세부(파사드, 지붕, 나무)는 AI 가 그린 장식이다.
export const PLACES = [
  { name: '전체', x: 1300, y: 880, vh: 1500, note: '경복궁과 주변 도심 · 약 1.4 km × 0.85 km' },
  { name: '광화문', x: 850, y: 1225, vh: 300, note: '광화문 — 경복궁의 남쪽 정문' },
  { name: '근정전', x: 1215, y: 985, vh: 300, note: '근정전 — 경복궁의 정전' },
  { name: '경회루', x: 1275, y: 800, vh: 300, note: '경회루 — 연못 위의 누각' },
  { name: '향원정', x: 1830, y: 650, vh: 300, note: '향원정 — 북쪽 연못의 정자' },
  { name: '서촌', x: 640, y: 520, vh: 380, note: '서촌 — 궁 서쪽의 오래된 동네' },
  { name: '세종대로', x: 330, y: 1230, vh: 420, note: '세종대로 사거리 방향의 업무지구' },
  { name: '북촌', x: 2250, y: 980, vh: 400, note: '북촌 방향 — 궁 동쪽의 주거지' },
];

// 각 샷: 시작/끝 카메라, 시각(tod), 계절(0 봄 1 여름 2 가을 3 겨울), 길이(초)
// rain = 그 샷 동안 비, cue = 샷이 시작될 때 일으킬 사람 장면([종류, 몇 번째] → people.force). 사람 장면 좌표는 sim/people.js 시드 5 기준.
const SHOTS = [
  { d: 6, a: [1300, 900, 1650], b: [1260, 920, 1150], tod: [6.6, 8.4], season: 1, caption: '서울의 아침, 경복궁' },
  { d: 6, a: [760, 1290, 330], b: [930, 1180, 250], tod: [8.5, 10.3], season: 1, caption: '광화문 앞, 출근길' },   // 10시를 지나며 교대 행렬이 나오기 시작한다
  { d: 8, a: [870, 1205, 170], b: [840, 1190, 100], tod: [10.3, 11.2], season: 1, caption: '오전 10시, 수문장 교대' },
  { d: 6, a: [1160, 1005, 150], b: [1258, 1018, 105], tod: [11.3, 11.9], season: 0, cue: ['classphoto', 0], caption: '봄 — 근정전 앞, 한복 나들이와 단체 사진' },
  { d: 6, a: [1150, 1020, 360], b: [1300, 840, 300], tod: [12, 13.2], season: 0, caption: '봄 — 근정전에서 경회루로' },
  { d: 6, a: [1700, 720, 420], b: [1860, 640, 280], tod: [14, 15.3], season: 2, caption: '가을 — 향원정' },
  { d: 6, a: [930, 1200, 200], b: [885, 1168, 125], tod: [15.5, 16.3], season: 2, rain: true, caption: '가을비 — 우산 속 궁궐' },
  { d: 6, a: [560, 600, 520], b: [700, 470, 360], tod: [16.6, 18.2], season: 2, caption: '해 질 녘의 서촌' },
  { d: 7, a: [420, 1260, 520], b: [820, 1220, 330], tod: [18.6, 20.5], season: 3, caption: '겨울 저녁, 불이 켜지는 도심' },
  { d: 8, a: [1240, 930, 520], b: [1300, 880, 1500], tod: [21, 23.2], season: 3, caption: '눈 내리는 밤의 경복궁' },
];
let acc = 0;
for (const s of SHOTS) { s.t0 = acc; acc += s.d; }
export const TOUR = { shots: SHOTS, total: acc };

const ease = (u) => u * u * (3 - 2 * u);
export function sampleTour(t) {
  if (t >= TOUR.total) return null;
  const s = SHOTS.find((q) => t < q.t0 + q.d);
  const u = ease((t - s.t0) / s.d);
  const L = (i) => s.a[i] + (s.b[i] - s.a[i]) * u;
  // 줌은 로그 공간에서 보간해야 속도가 일정하게 느껴진다
  const vh = Math.exp(Math.log(s.a[2]) + (Math.log(s.b[2]) - Math.log(s.a[2])) * u);
  return { x: L(0), y: L(1), vh, tod: s.tod[0] + (s.tod[1] - s.tod[0]) * ((t - s.t0) / s.d), season: s.season, caption: s.caption, rain: !!s.rain, cue: s.cue || null, shot: SHOTS.indexOf(s) };
}
