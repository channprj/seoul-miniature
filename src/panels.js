// 출처·권리 패널과 검증 도구 패널의 본문. 출처는 레포 루트 CREDITS-AND-USAGE.txt 를 따른다.
import { PHOTO_CREDITS } from './photo-credits.js';

const esc = (t) => String(t).replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));

export function aboutHtml() {
  return `
<h2>출처와 라이선스</h2>
<p>서울 경복궁 일대를 실제 지도 배치 그대로 픽셀아트 미니어처로 옮긴 개인 연구 프로젝트입니다. 비상업 목적입니다. 아래 기관·단체가 이 작업을 후원하거나 보증한 것은 아닙니다.</p>
<p><a class="gh" href="https://github.com/midagedev/seoul-miniature" target="_blank" rel="noopener"><svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>소스 코드와 만든 과정 — github.com/midagedev/seoul-miniature</a></p>
<h3>지도·건물 데이터</h3>
<ul>
  <li>© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a> — 지도 데이터는 Open Database License(ODbL)로 제공됩니다. 도로·수면·녹지·건물 윤곽·궁궐 경계에 썼습니다.</li>
  <li><a href="https://overturemaps.org" target="_blank" rel="noopener">Overture Maps Foundation, overturemaps.org</a> — 건물 테마(ODbL). 그 안에 포함된 East Asian Buildings(Qian Shi 외, 2023, <a href="https://doi.org/10.5281/zenodo.8174931" target="_blank" rel="noopener">doi:10.5281/zenodo.8174931</a>)는 CC BY 4.0 입니다.</li>
  <li>본 저작물은 '국토교통부'에서 작성하여 공공누리 제1유형으로 개방한 'GIS건물통합정보'를 이용하였으며, 해당 저작물은 '공공데이터포털, <a href="https://www.data.go.kr/data/15083092/fileData.do" target="_blank" rel="noopener">data.go.kr/data/15083092</a>'에서 무료로 다운받으실 수 있습니다. (건물 높이·층수에 사용)</li>
  <li>본 저작물은 '국가유산청'에서 '2023년' 작성하여 공공누리 제1유형으로 개방한 '사적 경복궁 광화문 월대 일원' 3D 기록을 이용하였으며, 해당 저작물은 '국가유산청 디지털 서비스, <a href="https://digital.khs.go.kr/record/recordDetail3D.do?ichDataUid=13928228084136100041&bizId=BIZ202300030001" target="_blank" rel="noopener">digital.khs.go.kr</a>'에서 무료로 다운받으실 수 있습니다. (광화문 일대 형태에 사용, 원본 모델은 포함하지 않음)</li>
  <li>본 저작물은 '국가유산청'에서 작성하여 공공누리 제1유형으로 개방한 '경복궁 3D 기록'(전각 46건)을 이용하였으며, 해당 저작물은 '국가유산청 디지털 서비스, <a href="https://digital.khs.go.kr" target="_blank" rel="noopener">digital.khs.go.kr</a>'에서 무료로 다운받으실 수 있습니다. (경회루(섬 포함), 수정전, 강녕전 일원(함원전·흠경각), 건춘문, 영추문, 신무문, 광화문 일원(동·서 수문장청, 용성문, 협생문, 초관처소, 군사방), 흥례문 일원(흥례문, 유화문, 기별청, 행각), 동궁(계조당·비현각·자선당·통장청), 건청궁(곤녕합·장안당·초양문·복수당·행각), 태원전 일원(태원전, 건숙문, 경안문, 숙문당, 복도, 동측·북측 세답방), 함화당·집경당, 흥복전, 자경전 일원(자경전, 청연루, 협경당, 복안당, 행각), 소주방(내소주방·외소주방·복회당·제수합)의 형태에 사용. 원본 모델은 이 페이지에 들어 있지 않습니다.)</li>
</ul>
<p style="opacity:.8">위 데이터로 3D 장면을 만들고, 그 장면의 렌더(색·깊이)를 그림의 뼈대로 썼습니다. 데이터를 고쳐 재배포하지는 않습니다.</p>
<h3>그림</h3>
<ul>
  <li>AI 일러스트: Qwen-Image-Edit-2511 과 Lightning 8-step LoRA(모델 카드 기준 Apache-2.0)를 제작자 장비에서 실행했습니다. 3D 장면의 렌더를 겹치는 창 단위로 양식만 바꿔 다시 그린 뒤 128색으로 정리했습니다.</li>
  <li>사람·차·불빛·날씨·계절은 코드로 그립니다. 게임 에셋은 쓰지 않았습니다.</li>
  <li>주요 건물은 생김새를 맞추려고 아래 사진을 AI 에 참조로 보여 주고 다시 그렸습니다. 사진 자체는 이 페이지에 들어 있지 않습니다.</li>
</ul>
<h3>소리</h3>
<ul>
  <li>배경음: <a href="https://huggingface.co/ACE-Step/Ace-Step1.5" target="_blank" rel="noopener">ACE-Step 1.5</a>(turbo + 5Hz LM 1.7B, 모델 카드·저장소 기준 MIT)로 제작자 장비에서 글 프롬프트만으로 만들었습니다. 샘플·녹음·기존 곡은 쓰지 않았고, 보컬은 없습니다. 루프·음량만 다듬었습니다.</li>
</ul>
<h3>참조 사진 (위키미디어 공용)</h3>
<ul class="small">
${PHOTO_CREDITS.map((c) => `  <li>${esc(c.name)} — <a href="${esc(c.page)}" target="_blank" rel="noopener">${esc(c.title)}</a>, ${esc(c.artist)}, ${esc(c.license)}</li>`).join('\n')}
</ul>
<h3>사실성</h3>
<ul>
  <li>배치(도로, 건물 윤곽·높이, 궁궐 경계)는 공개 지도 데이터 기반이지만 측량 수준은 아닙니다.</li>
  <li>건물 종류(빌라·한옥·타워 등)는 지도 태그·높이·면적으로 나눴고, 북촌·서촌의 한옥 일부는 추정입니다.</li>
  <li>파사드, 지붕, 창문, 수목은 AI 가 그린 장식입니다. 창문 불빛, 계절, 눈·비는 화면 연출입니다.</li>
  <li>사람과 차는 연출용이며 실제 교통이 아닙니다.</li>
</ul>`;
}

export function verifyHtml(state) {
  return `
<h2>검증 도구</h2>
<p>가림(건물 뒤로 지나가는 차·사람)은 휴리스틱 보정 깊이에 의존합니다. 통계가 아니라 눈으로 확인하세요.</p>
<div class="row">
  <button data-a="cls" aria-pressed="${state.debug}">가림 판정 클래스 오버레이</button>
  <button data-a="bus">버스 가림 사례로 이동</button>
</div>
<p style="opacity:.75">오버레이 색: 빨강 확실한 가림체 · 초록 확실한 지면 · 주황 대역→가림체 · 청록 대역→지면 · 자홍 모호(렌더 깊이 유지)</p>
<h3>성능</h3>
<div class="row">
  <button data-a="hud" aria-pressed="${state.hud}">프레임타임 HUD</button>
  <button data-a="bench">벤치마크 실행(자동 투어, 약 52초)</button>
</div>
<p style="opacity:.75">벤치마크는 이 기기에서 잰 값만 보여 줍니다. 결과 JSON 에 기기·브라우저·GPU 가 함께 기록됩니다.</p>
<h3>단축키</h3>
<p>H 화면 UI 숨김 · Space 시간 흐름 · Esc 닫기</p>`;
}
