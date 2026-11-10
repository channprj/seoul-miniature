# 경복궁, 살아 있는 미니어처

서울 경복궁 일대(약 1.4 km × 0.85 km)를 실제 지도 배치 그대로 옮긴 픽셀아트 미니어처입니다.
시간·계절·날씨가 바뀌고, 사람과 차와 새가 움직입니다. 개인 비상업 연구 프로젝트입니다.

**보기: https://midagedev.github.io/seoul-miniature/**

![미리보기](og.png)

*A pixel-art miniature of the Gyeongbokgung Palace district in Seoul, laid out from open map data, painted tile by tile with an Apache-2.0 image-edit model, and animated in the browser. This repository contains the viewer, the generation pipeline and notes on how to do the same for another place. Documentation is in Korean.*

## 이 저장소에 있는 것

| 경로 | 내용 |
|---|---|
| `index.html`, `style.css`, `src/` | 뷰어. 빌드 없이 그대로 열리는 ES 모듈(WebGL2). GitHub Pages 가 저장소 루트를 그대로 서빙합니다 |
| `assets/` | 뷰어가 쓰는 그림·깊이·클래스 맵과 장면 데이터 |
| `test/` | 교통 시뮬레이션·투영·새 로직의 `node --test` 테스트 |
| `pipeline/` | 그림을 만드는 도구: OSM 받기 → 블록 밑그림 → 타일 생성 → 검사 → 병합 → 랜드마크 합성 → 픽셀 격자 정리 |
| `pipeline/input/` | 밑그림을 만들 때 쓴 카메라 정의와 렌더 깊이 |
| `docs/` | 만드는 방법, 뷰어 구조, 라이선스 점검 방법, 시행착오 기록 |
| `CREDITS.md`, `LICENSE` | 출처와 라이선스 |

## 바로 실행

```bash
git clone https://github.com/midagedev/seoul-miniature && cd seoul-miniature
node serve.mjs 5173        # http://127.0.0.1:5173/  (의존성 없음)
npm install && npm test    # 테스트를 돌릴 때만
```

주소 옵션: `?res=1` 절반 해상도 그림 · `?cars=150` 차량 수 · `?tilt=0` 미니어처 흐림 끄기 · `?tour` 자동 둘러보기 · `?clean` UI 숨김 ·
`#x,y,높이` 특정 위치로 바로 열기(화면 아래 「링크 복사」가 만들어 줍니다).

## 어떻게 만들었나 (요약)

1. **배치는 공개 데이터에서.** OpenStreetMap 의 건물 윤곽·도로·수면·녹지와 공공데이터의 건물 높이로 3D 장면을 만들고, 고정된 정사투영 카메라(북서 방향, 35° 내려다봄, 0.5 m/px)로 깊이를 렌더합니다.
2. **블록 밑그림.** 깊이와 OSM 을 합쳐 "도로는 회색, 잔디는 연두, 한옥 지붕은 남색…" 식의 의미색 블록 그림과 픽셀별 클래스 맵을 만듭니다(`pipeline/make_guide.py`).
3. **타일 단위로 다시 그리기.** 밑그림을 4배로 키운 겹치는 타일을 이미지 편집 모델(Qwen-Image-Edit-2511 + Lightning 8-step LoRA, 둘 다 Apache-2.0)에 넣어 픽셀아트로 다시 그립니다. 타일마다 클래스 비율을 보고 프롬프트를 조립합니다.
4. **자동 검사와 재시도.** 도로가 물색으로 칠해졌는지, 잔디가 모래색이 됐는지 같은 색 규칙으로 실패 타일을 골라 다시 돌립니다.
5. **랜드마크는 사진을 보여 주고 따로.** 광화문·경회루 같은 건물은 재사용이 허용된 사진을 두 번째 입력으로 주고 다시 그려, 그 건물 자리만 합성합니다.
6. **진짜 픽셀 격자로.** 96색 팔레트로 줄이고 2×2 칸마다 최빈색으로 채워 0.25 m 격자의 픽셀아트로 정리합니다.
7. **브라우저에서 살리기.** 같은 카메라의 깊이 맵으로 차와 사람이 건물 뒤로 가려지게 하고, 클래스 맵으로 나무 흔들림·물결·창문 불빛·눈비를 셰이더에서 만듭니다.

자세한 절차는 [docs/PIPELINE.md](docs/PIPELINE.md), 뷰어 구조는 [docs/APP.md](docs/APP.md), 안 됐던 것들은 [docs/LESSONS.md](docs/LESSONS.md)에 있습니다.
다른 동네로 같은 작업을 하려면 [docs/PIPELINE.md 의 "다른 지역에 적용하기"](docs/PIPELINE.md#다른-지역에-적용하기)부터 보세요.

## 사실성에 대해

건물 배치와 높이는 공개 지도 데이터 기반이지만 측량 수준이 아닙니다. 파사드·지붕·창문·수목은 AI 가 그린 장식이고, 사람과 차는 연출입니다.
지도로 쓰지 마세요.

## 출처와 라이선스

지도 데이터 © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) (ODbL) · Overture Maps Foundation · 국토교통부 GIS건물통합정보 · 국가유산청 3D 기록(공공누리 제1유형) · 그림 Qwen-Image-Edit-2511.
위 기관·단체가 이 작업을 후원하거나 보증한 것은 아닙니다.

- 전체 출처와 조건: [CREDITS.md](CREDITS.md)
- 코드는 MIT, `assets/` 는 파일별로 다릅니다: [LICENSE](LICENSE)
- 공개 전에 라이선스를 어떻게 점검했는지: [docs/LICENSING.md](docs/LICENSING.md)
