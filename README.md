# 경복궁, 살아 있는 미니어처

서울 경복궁 일대(약 1.4 km × 0.85 km)를 실제 지도 배치 그대로 옮긴 픽셀아트 미니어처입니다.
시간·계절·날씨가 바뀌고, 사람과 차와 새가 움직입니다. 확대하면 6.25 cm/px 까지 그림이 세밀해집니다. 개인 비상업 연구 프로젝트입니다.

**보기: https://midagedev.github.io/seoul-miniature/**

![미리보기](og.png)

*A pixel-art miniature of the Gyeongbokgung Palace district in Seoul, laid out from open map data as a 3D scene, restyled window by window with an Apache-2.0 image-edit model, and animated in the browser with WebGL. This repository contains the viewer, the generation pipeline and notes on how to do the same for another place. Documentation is in Korean.*

## 이 저장소에 있는 것

| 경로 | 내용 |
|---|---|
| `index.html`, `style.css`, `src/` | 뷰어. 빌드 없이 그대로 열리는 ES 모듈(WebGL2). GitHub Pages 가 저장소 루트를 그대로 서빙합니다 |
| `assets/` | 뷰어가 쓰는 그림 타일·깊이·분류 맵과 장면 데이터 |
| `test/` | 교통·사람 시뮬레이션, 투영, 타일, 새 로직의 `node --test` 테스트 |
| `pipeline/` | 이전 판 그림을 만든 도구(OSM 받기 → 색 블록 밑그림 → 타일 생성 → 검사 → 병합). 지금 그림을 만든 3D 장면 도구는 이 저장소에 아직 없습니다 |
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

1. **배치는 공개 데이터에서.** OpenStreetMap 의 건물 윤곽·도로·수면·녹지·담과 공공데이터의 건물 높이로 Blender 3D 장면을 만듭니다. 일반 건물은 윤곽과 높이에서 지붕·창·옥탑을 절차적으로 세우고, 경복궁 전각 46건은 국가유산청이 공공누리 제1유형으로 개방한 3D 기록의 형태를 배치했습니다.
2. **고정 카메라로 렌더.** 정사투영 카메라(북서 방향, 35° 내려다봄) 하나로 색, 깊이, 물체 ID 를 렌더합니다. 엄밀한 아이소메트릭은 아니고 회전도 없습니다.
3. **양식만 이미지 모델로.** 색 렌더를 겹치는 창으로 잘라 이미지 편집 모델(Qwen-Image-Edit-2511 + Lightning 8-step LoRA, 둘 다 Apache-2.0)에 넣어 픽셀아트풍으로 다시 그립니다. 배치와 실루엣은 3D 장면이 정하고, 모델은 표면의 그림체를 맡습니다.
4. **되돌리기와 정리.** 모델이 궁궐 마당에 지어낸 것은 렌더 색을 기준으로 찾아 다시 칠합니다. 전체를 128색으로 줄이고 확대 단계별 타일(256 px, 가장 세밀한 단계 6.25 cm/px)로 자릅니다.
5. **깊이·분류 맵.** 같은 3D 장면의 깊이와 ID 렌더에서 가림 판정용 깊이 맵과 픽셀별 종류(도로·잔디·지붕·벽·수목…) 맵을 만듭니다.
6. **브라우저에서 살리기.** WebGL2 뷰어가 깊이 맵으로 차와 사람을 건물 뒤에 가리고, 분류 맵으로 나무 흔들림·물결·창문 불빛·눈비를 셰이더에서 만듭니다. 사람·차·새는 코드로 그립니다.

뷰어 구조는 [docs/APP.md](docs/APP.md)에 있습니다. [docs/PIPELINE.md](docs/PIPELINE.md)와 [docs/LESSONS.md](docs/LESSONS.md)는 이전 판(2D 색 블록 밑그림 방식)의 절차와 시행착오 기록이고, 지금 방식과 다른 점을 문서 머리에 적어 두었습니다.

## 한계

- 그림은 정지 그림 한 벌입니다. 카메라는 돌릴 수 없고, 확대·이동만 됩니다.
- 양식 패스는 창 단위로 돌기 때문에 창 경계에서 그림체가 조금 달라지는 곳이 있습니다. 모델이 지어낸 작은 소품이 남아 있을 수 있습니다.
- 가림 판정은 깊이 맵 한 장으로 합니다. 다리 밑이나 처마 밑처럼 겹친 곳에서는 틀릴 수 있습니다.
- 교통 시뮬레이션은 단순합니다. 신호와 차로는 따르지만 실제 교통량·신호 주기와는 무관합니다.
- 휴대폰에서는 화면 크기와 메모리에 맞춰 낮은 확대 단계의 타일을 씁니다. 기기별 프레임 속도는 측정해 공개한 값이 없습니다.

## 사실성에 대해

건물 배치와 높이는 공개 지도 데이터 기반이지만 측량 수준이 아닙니다. 국가유산청 기록을 쓴 전각 46건 외의 파사드·지붕·창문·수목은 절차적으로 만들거나 AI 가 그린 장식이고, 사람과 차는 연출입니다.
지도로 쓰지 마세요.

## 출처와 라이선스

지도 데이터 © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) (ODbL) · Overture Maps Foundation · 국토교통부 GIS건물통합정보 · 국가유산청 경복궁 3D 기록(공공누리 제1유형) · 그림 Qwen-Image-Edit-2511 + Lightning 8-step LoRA (Apache-2.0).
위 기관·단체가 이 작업을 후원하거나 보증한 것은 아닙니다.

- 전체 출처와 조건: [CREDITS.md](CREDITS.md)
- 코드는 MIT, `assets/` 는 파일별로 다릅니다: [LICENSE](LICENSE)
- 공개 전에 라이선스를 어떻게 점검했는지: [docs/LICENSING.md](docs/LICENSING.md)
