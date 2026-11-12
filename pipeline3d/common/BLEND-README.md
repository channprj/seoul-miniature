서울 미니어처 — Blender 장면 (seoul-miniature)
================================================

이 파일은 공개판 그림의 "조건 렌더"(양식 패스에 넣기 전 3D 렌더)를 만든 장면의 한 구역입니다.
파일을 열고 바로 렌더(F12, Cycles)하면 이 구역 전체가 공개판 조건 렌더와 같은 크기·해상도로 나옵니다.
타일 하나만 보려면 저장소의 pipeline3d/common/render_window.py 를 쓰세요.

- 만든 도구: Blender Python 모듈 bpy 5.0 (장면 속성 p3d_blender 에 정확한 판).
- 카메라: 정사투영. 경복궁 6.25 cm/px, 여의도 12.5 cm/px. 장면 속성 p3d_window_* 가 지도 전체에서 이 구역의 자리입니다.
- 해: SUN 하나 + 흰 하늘빛 0.7. 재질은 평색·직접 그린 입면 텍스처·툰 재질이고, 텍스처는 모두 파일 안에 들어 있습니다(pack).
- 오브젝트의 pass_index = 건물 ID. 장면 속성 p3d_meta 가 ID → 종류(hanok, tower, palace, landmark:63 …) 표입니다.

경복궁 파일만: 국가유산청 3D 모델은 들어 있지 않습니다.
- 컬렉션 KHS_SLOTS 의 빈 오브젝트 하나 = 전각 하나의 자리. 속성 khs_model(국가유산청 자료 이름), theta·tx·ty·tz(모델을 놓는 변환).
- 컬렉션 KHS_STANDIN/<자리> = 그 자리에 대신 세운 OSM 윤곽 + 규칙 지붕 모형(오브젝트 속성 khs_slot).
- 국가유산청 디지털 서비스(digital.khs.go.kr)에서 직접 받은 모델로 바꾸려면 pipeline3d/gyeongbokgung/insert_khs.py.
- 기와 지붕은 그림 두 장(높이·색) + 지오메트리 노드 그룹 P3D_RoofGrid 로 들어 있고 열 때 메시를 다시 만듭니다.
  원래 격자(5–8 cm)로 만들면 메모리가 많이 듭니다(구역 파일에서 타일 하나 렌더에 최대 약 14 GB). 모자라면 노드 그룹
  P3D_RoofGrid 안의 정수 노드 Step 을 2–4 로 올리세요(격자를 그만큼 건너뜀, 1 = 원래 격자. render_window.py --roof-step N 과 같음).

라이선스: 이 장면 데이터는 OpenStreetMap 에서 왔으므로 ODbL 1.0 입니다.
  © OpenStreetMap contributors (https://www.openstreetmap.org/copyright)
  건물 높이 등 다른 원천과 출처 표시 문구는 저장소의 CREDITS.md 와 docs/REUSE.md 를 보세요.
  실제 지도가 아닙니다(건물 높이·형태·재질 상당 부분이 추정·규칙 생성).

Seoul Miniature — Blender scene. Open and render (F12) to reproduce this section of the published
condition render. Scene data (c) OpenStreetMap contributors, ODbL 1.0. The Gyeongbokgung files contain
no Korea Heritage Service models; KHS_SLOTS marks where they go (see insert_khs.py).
