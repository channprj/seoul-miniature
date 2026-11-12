// 지도별 설정을 한 곳에 모은다. 주소의 ?map=<id> 로 고르고(없으면 경복궁), 화면의 전환 버튼은 그 주소로 다시 연다.
// 여기 없는 값(카메라, 깊이 디코드 상수, 경로)은 장면 데이터에서 온다:
//   경복궁 = assets/web-poc/scene.json(.gz), 여의도 = assets/yeouido/map.json → mapscene.js 가 같은 모양으로 바꾼다.
// 좌표는 모두 그 지도의 지도 px(2752×1696 캔버스). 경복궁 1 px = 0.5 m, 여의도 1 px = 1 m.
import { PLACES as GB_PLACES, SHOTS as GB_SHOTS } from './tour.js';

export const MAPS = {
  gyeongbok: {
    id: 'gyeongbok', label: '경복궁',
    dir: 'redraw',                               // 그림·깊이·클래스·타일 폴더(assets/ 아래)
    scene: 'web-poc/scene.json',                 // 장면 데이터(.gz 도 찾는다)
    cls: 'web-poc/occlusion_class8.png',         // 가림 판정 클래스(검증 오버레이)
    docTitle: '서울 미니어처 — 경복궁', h1: '경복궁, 살아 있는 미니어처',
    canvasLabel: '경복궁과 주변 서울 도심의 픽셀아트 미니어처',
    places: GB_PLACES, shots: GB_SHOTS,
    palace: [-258.6, 12.2, 297.3, 878.1],        // 궁궐 로컬 경계(m): 궁 조명·골목등 제외에 쓴다
    uplights: [[850, 1225, 70], [1215, 985, 80], [1275, 800, 70]],   // 광화문·근정전·경회루: 벽 밑동 업라이트
    firstView: { wide: [0.47, 0.52, 0.86], box: [715, 720, 1370, 1290] },   // 넓은 화면(가로·세로 비율, 세로 시야 비율) / 세로 화면에 담을 상자
    busDemo: [1042, 201, 150],                   // 검증 도구의 버스 가림 사례
    people: true, birds: true, finds: true, traffic: 'live', cars: 190,
  },
  yeouido: {
    id: 'yeouido', label: '여의도',
    dir: 'yeouido',
    map: 'map.json',                             // 지도 고유 값(dir 아래)
    devDir: '_yd_interim',                       // 개발용: 정식 세트(dir)가 아직 없으면 이 임시 세트를 쓴다(공개 배포본에는 없다)
    cls: null,
    docTitle: '서울 미니어처 — 여의도', h1: '여의도, 살아 있는 미니어처',
    canvasLabel: '여의도와 한강의 픽셀아트 미니어처',
    // 여의도 좌표는 여기 적지 않는다: 그림을 다시 구우면(방위가 바뀌면) 지도 px 가 전부 달라진다.
    // 자리는 map.json 의 랜드마크 이름(landmarks.<key>.px)으로 가리키고 resolveView 가 실행 때 지도 px 로 바꾼다. vh = 세로 시야(지도 px, 1 px = 1 m).
    places: [
      { name: '전체', at: 'center', vh: 1500, note: '여의도와 한강' },
      { name: '국회의사당', key: 'assembly', vh: 300, note: '국회의사당 — 섬 서쪽 끝' },
      { name: '여의도공원', key: 'park', vh: 420, note: '여의도공원 — 섬 한가운데를 가로지르는 숲' },
      { name: '파크원·IFC', key: 'parc1', vh: 420, note: '파크원과 IFC — 고층 업무지구' },
      { name: '63빌딩', key: '63', vh: 380, note: '63빌딩 — 섬 동쪽 끝의 금빛 타워' },
      { name: '한강공원', key: 'mulbit', vh: 380, note: '여의도한강공원 — 강변 잔디밭과 물빛광장' },
      { name: '마포대교', key: 'mapo', vh: 520, note: '마포대교 — 여의도와 마포를 잇는 다리' },
      { name: '밤섬', key: 'bamseom', vh: 420, note: '밤섬 — 사람이 살지 않는 한강의 섬' },
    ],
    shots: [
      { d: 7, a: { at: 'mapo', vh: 760 }, b: { at: 'mulbit', vh: 620 }, tod: [6.4, 8.2], season: 1, caption: '한강에서 본 아침의 여의도' },
      { d: 7, a: { at: '63', vh: 620 }, b: { at: '63', vh: 360 }, tod: [8.4, 10.4], season: 1, caption: '63빌딩' },
      { d: 7, a: { at: 'hyundai', vh: 520 }, b: { at: 'parc1', vh: 400 }, tod: [11, 13.5], season: 0, caption: '봄 — 파크원과 IFC' },
      { d: 7, a: { at: 'park_plaza', vh: 420 }, b: { at: 'park', vh: 340 }, tod: [14, 16.2], season: 2, caption: '가을 — 여의도공원' },
      { d: 7, a: { at: 'assembly_library', vh: 520 }, b: { at: 'assembly', vh: 340 }, tod: [16.6, 18.8], season: 2, caption: '해 질 녘의 국회의사당' },
      { d: 8, a: { at: 'parc1', vh: 620 }, b: { at: 'center', vh: 1500 }, tod: [19.4, 22.6], season: 3, caption: '겨울밤, 불이 켜진 여의도' },
    ],
    noticeMore: '',                              // 하단 표기의 추가 기관 문구(경복궁 전용 자료)를 뺀다
    palace: null, uplights: [],
    firstView: { wide: [0.5, 0.5, 0.9], box: { at: ['parc1', 'park'], w: 850, h: 680 } },   // 세로 화면: 파크원과 여의도공원 사이를 가운데로
    busDemo: null,
    windows: 'grid',                             // 밤 창문을 층 × 칸으로(winlights.js). 없으면 경복궁 식(그림의 창 픽셀, 2 m 칸)
    // 사람: profile 'city' = 경복궁 전용 장면(수문장·관람 시간·한복 비율) 대신 공원·강변·업무지구 장면(sim/people.js). 찾아보기는 아직 경복궁만.
    people: true, profile: 'city', birds: false, finds: false, traffic: 'simple', cars: 2500,   // cars = 출퇴근 때 대수(낮 약 1900, 밤 약 900: simple-traffic demandAt)
    parking: 900,                                 // 세워 둔 차 최대 대수(sim/parking.js, ?parked=0 이면 없음)
  },
};
export const DEFAULT_MAP = 'gyeongbok';

// 공개 여부: public: false 인 지도는 공개 사이트에 자산이 없다 → 전환 버튼에 안 나오고, 빌드(build-site.mjs·tools/publish.py)가 싣지 않는다.
export const isPublic = (id) => MAPS[id].public !== false;
export const publicMaps = () => Object.values(MAPS).filter((m) => isPublic(m.id));
const isLocal = () => typeof location !== 'undefined' && /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname);

// 주소에서 지도 고르기: ?map=<id>. 모르는 값은 기본 지도. 비공개 지도는 로컬 개발 서버에서 dev=1 을 붙였을 때만(그 밖에는 기본 지도).
export function mapIdFrom(search, local = isLocal()) {
  let id = null, dev = false;
  try { const q = new URLSearchParams(search || ''); id = q.get('map'); dev = q.has('dev'); } catch { /* 잘못된 주소 */ }
  if (!id || !Object.prototype.hasOwnProperty.call(MAPS, id)) return DEFAULT_MAP;
  return isPublic(id) || (local && dev) ? id : DEFAULT_MAP;
}
export const currentMap = () => MAPS[mapIdFrom(typeof location === 'undefined' ? '' : location.search)];

// 다른 지도로 가는 주소: map 만 바꾸고(기본 지도면 뺀다) 위치 해시는 버린다(지도마다 좌표가 다르다). res·look 같은 옵션은 남긴다.
export function mapUrl(id, href) {
  const u = new URL(href);
  if (id === DEFAULT_MAP) u.searchParams.delete('map'); else u.searchParams.set('map', id);
  if (isPublic(id)) u.searchParams.delete('dev'); else u.searchParams.set('dev', '1');
  for (const k of ['tod', 'season', 'tour']) u.searchParams.delete(k);
  u.hash = '';
  return u.toString();
}

// 자리 적는 법 → 지도 px [x, y, vh]. 배열이면 그대로(경복궁). 객체면 { at, off, vh }:
//   at = 랜드마크 이름 | 이름 둘의 배열(가운데 점) | 'center'(지도 한가운데), off = [dx, dy] 지도 px 만큼 옮김(없으면 0).
// 이름이 장면 데이터에 없으면 지도 한가운데로 간다(그리고 한 번 경고).
const warned = new Set();
export function resolveView(v, anchors = {}, size = [2752, 1696]) {
  if (!v || Array.isArray(v)) return v;
  const mid = [size[0] / 2, size[1] / 2];
  const one = (k) => {
    if (k === 'center') return mid;
    const a = anchors && anchors[k];
    if (!a && !warned.has(k)) { warned.add(k); console.warn(`랜드마크 '${k}' 가 장면 데이터에 없다 → 지도 한가운데`); }
    return a || mid;
  };
  const ks = Array.isArray(v.at) ? v.at : [v.at ?? 'center'];
  let x = 0, y = 0;
  for (const k of ks) { const p = one(k); x += p[0] / ks.length; y += p[1] / ks.length; }
  const off = v.off || [0, 0];
  return [x + off[0], y + off[1], v.vh ?? size[1] * 0.9];
}
// 첫 화면에 담을 상자: 배열 [x0, y0, x1, y1] 이면 그대로, { at, w, h } 면 그 자리를 가운데로 한 상자
export function resolveBox(b, anchors, size) {
  if (Array.isArray(b)) return b;
  const [x, y] = resolveView({ at: b.at, off: b.off }, anchors, size);
  return [x - b.w / 2, y - b.h / 2, x + b.w / 2, y + b.h / 2];
}
// 둘러보기 대본의 a·b 를 지도 px 로
export const resolveShots = (shots, anchors, size) => shots.map((s) => ({ ...s, a: resolveView(s.a, anchors, size), b: resolveView(s.b, anchors, size) }));
