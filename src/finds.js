// 찾아보기: 가까이서 들여다보다 마주친 장면을 조용히 적어 두는 목록. 점수·보상·알림은 없다.
// 무엇이 「보였는지」는 people.spot(view) 가 정한다(sim/people.js). 여기는 목록·저장·패널 글만.
export const FINDS = [
  ['ceremony', '수문장 교대', '광화문 안마당 · 오전 10시(시간을 멈춰 두면 오후 2시에도)'],
  ['hanbok', '한복 나들이', '궁 안 · 낮'],
  ['askphoto', '사진 좀 찍어 주세요', '궁 안팎 · 한복 입은 사람이 지나가는 사람에게'],
  ['classphoto', '단체 사진', '근정전 앞 · 낮'],
  ['pigeon', '비둘기와 아이', '마당과 광장 · 낮'],
  ['busk', '거리 연주', '궁 밖 보행로 · 오후에서 저녁'],
  ['bench', '벤치 담소', '낮 · 맑은 날'],
  ['picnic', '소풍', '궁 밖 잔디밭 · 봄과 가을, 맑은 날'],
  ['snow', '눈사람', '겨울'],
  ['share', '우산 같이 쓰기', '비 오는 날'],
  ['nightphoto', '야경 사진', '광화문 앞 · 밤'],
  ['guide', '깃발 든 안내', '궁 안 · 낮 · 깃발을 따라 모인 사람들'],
  ['cat', '고양이', '돌담 근처 어딘가'],
  ['kite', '연', '바람 좋은 낮'],
  ['soap', '비눗방울', '낮 · 맑은 날'],
  ['proposal', '해 질 녘의 고백', '향원정 근처 · 오후 5시쯤 · 드물다'],
];
const KEY = 'seoul-miniature-finds-v1';
const esc = (s) => s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

// store: getItem/setItem 을 가진 것(localStorage). 없거나 던지면 이번 방문 동안만 기억한다.
export function createFinds(store) {
  const known = new Set(FINDS.map((f) => f[0]));
  const seen = new Set();
  try { for (const k of JSON.parse(store.getItem(KEY) || '[]')) if (known.has(k)) seen.add(k); } catch { /* 저장소를 못 쓴다(사파리 비공개 창·인앱) */ }
  const save = () => { try { store.setItem(KEY, JSON.stringify([...seen])); } catch { /* 위와 같음 */ } };
  return {
    seen, total: FINDS.length,
    // keys 가운데 처음 본 것의 [열쇠, 이름] 목록을 돌려준다
    mark(keys) {
      const fresh = [];
      for (const k of keys) if (known.has(k) && !seen.has(k)) { seen.add(k); fresh.push(FINDS.find((f) => f[0] === k)); }
      if (fresh.length) save();
      return fresh;
    },
    reset() { seen.clear(); save(); },
    // 좁은 화면에서는 가운데 두 글자를 숨겨 「찾기 n/16」 이 된다(style.css)
    label() { return `찾<span class="w">아보</span>기 ${seen.size}/${FINDS.length}`; },
    html() {
      const li = FINDS.map(([k, name, hint]) => `<li class="${seen.has(k) ? 'got' : ''}"><b>${seen.has(k) ? esc(name) : '· · ·'}</b><span>${esc(hint)}</span></li>`).join('');
      return `<h2>찾아보기</h2><p>가까이 당겨서 들여다보면 가끔 이런 장면을 만납니다. 본 것은 이 기기에만 적어 둡니다.</p><ul class="finds">${li}</ul><div class="row"><button data-a="finds-reset">처음부터 다시</button></div>`;
    },
  };
}
