# 뷰어 구조

빌드 단계가 없는 ES 모듈 앱입니다. `index.html` 이 `src/main.js` 를 불러오고, 의존 라이브러리는 없습니다(WebGL2 필요).

## 파일

| 파일 | 하는 일 |
|---|---|
| `src/main.js` | 시작, 시계(시간·계절), UI 연결, 자동 둘러보기, 주소 해시 동기화 |
| `src/assets.js` | 그림·맵·장면 데이터 읽기. 큰 텍스처를 못 쓰는 기기는 절반 해상도 그림으로 |
| `src/geom.js` | 카메라 투영: 월드(m) ↔ 지도 px, 깊이 계산 |
| `src/render.js` | WebGL2 렌더러(아래 "렌더 순서") |
| `src/camera.js` | 이동·확대, 부드러운 이동(`flyTo`) |
| `src/sim/traffic.js` | 차량 시뮬레이션: 차선 그래프, 신호, 교차로 양보, 추종 모델 |
| `src/movers.js` | 사람(걷는 경로, 서 있는 사람)과 스프라이트 배치 |
| `src/vehicles.js` | 차량 스프라이트를 실행 시점에 그림(상자 모형을 같은 카메라로 32방향 래스터화) |
| `src/birds.js` | 비둘기 무리·백로·까치(고정 시드 배치, 다가가면 날아오름) |
| `src/tour.js` | 자동 둘러보기 장면 표 |
| `src/panels.js`, `src/photo-credits.js` | 출처 패널, 검증 도구 패널 |
| `serve.mjs` | 로컬 미리보기 서버(의존성 없음) |
| `tools/shot.mjs`, `tools/capture.mjs` | 헤드리스 크롬으로 스크린샷·영상 캡처(`puppeteer-core`, ffmpeg) |

## 자산

모두 같은 카메라, 같은 캔버스(2752×1696 지도 px, 0.5 m/px)에 맞춰져 있습니다.

| 파일 | 내용 |
|---|---|
| `assets/redraw/bg.png` | 배경 그림 5504×3392(0.25 m/px), 96색 인덱스 PNG |
| `assets/redraw/bg_1x.png` | 절반 해상도 판 |
| `assets/redraw/depth_rg8.png` | 깊이. `depth_m = 2060 + (R·256 + G) × 0.02`, 65535 는 없음 |
| `assets/redraw/classes.png` | 픽셀별 클래스(도로·잔디·물·지붕·벽·나무 등, 번호는 [PIPELINE.md](PIPELINE.md)) |
| `assets/web-poc/occlusion_class8.png` | 가림 판정 검증용 오버레이 |
| `assets/web-poc/scene.json.gz` | 카메라, 차선, 보행 경로, 서 있는 사람, 차종 규격(ODbL) |

## 렌더 순서

합성은 전부 지도 해상도(또는 그 2배)의 오프스크린 버퍼에서 텍셀 단위로 합니다. 화면 해상도에서 합성하면 픽셀아트의 격자와 깊이 비교가 어긋납니다.

1. **바탕**: 배경 그림에 계절 변환(잔디·나무 색, 눈)을 입히고, 나무 흔들림과 물결을 적용합니다. 둘 다 클래스 맵으로 대상을 고르고, 그림 픽셀 단위로만 움직입니다.
2. **그림자와 스프라이트**: 차·사람·새를 그립니다. 스프라이트의 각 픽셀 깊이를 배경 깊이와 비교해, 건물 뒤에 있으면 버립니다. 이것이 "차가 건물 뒤로 지나간다"의 전부입니다.
3. **빛**: 가로등·전조등의 빛 웅덩이를 절반 해상도에 더합니다.
4. **조명 합성**: 낮밤 색, 구름 그림자, 궁궐 야간 조명, 창문 불빛. 창문은 벽 클래스 픽셀 중 푸른 유리색인 곳만, 층·칸 단위 난수로 켭니다.
5. **화면**: 카메라 변환, 확대 시 또렷한 픽셀 유지, 눈·비, 틸트시프트(화면 위아래를 흐리게, 가까이 확대하면 꺼짐).

깊이는 근사값입니다. 가림이 어색한 곳은 「검증 도구」의 오버레이로 볼 수 있습니다.

## 장면 데이터 형식

`scene.json.gz` 의 주요 키. 좌표는 로컬 미터(x, y, z).

```jsonc
{
  "camera": { "res": [2752, 1696], "m_per_px_screen": 0.5, "cx": …, "cy": …, "cam_location": […],
              "view_dir": […], "screen_x_axis": […], "screen_y_axis": […] },
  "lanes":   [{ "id": "E000", "name": "자하문로", "highway": "primary", "oneway": false,
                "lanes_dir": 2, "length": 938.47, "spawn": false, "exit": true, "stopline": false,
                "pts": [[x, y, z], …] }],
  "walkers": [{ "id": "W0000", "speed_mps": 1.26, "length_m": 20.1, "pts": [[x, y, z], [x, y, z]] }],
  "walker_palette": [["#shirt", "#pants", "#hair"], …], "walker_pal_idx": [222, …],
  "standing": [{ "x": …, "y": …, "z": 0, "facing": 0, "pal": 6 }],
  "vehicle_specs": { "sedan": [길이, 폭, 높이], "bus": […], … },
  "vehicle_atlas": { "headings": 32, "frames": [{ "kind": "bus", "color": "#2f6fd0" }, …] }
}
```

차선은 OSM 도로 중심선을 방향별 차선으로 나눈 것이고, 교차로 연결·신호·양보 구역은 `traffic.js` 가 시작할 때 차선 형상에서 계산합니다.

## 주소 옵션

| 옵션 | 뜻 |
|---|---|
| `#x,y,vh` | 지도 px 중심과 보이는 높이로 바로 이동. `&t=시각`, `&s=계절(0~3)` 을 붙일 수 있음 |
| `?res=1` | 절반 해상도 그림 |
| `?cars=N` | 차량 수 |
| `?tod=시각`, `?season=0~3` | 시작 시각(시간 흐름 정지), 계절 |
| `?tilt=0` | 틸트시프트 끄기 |
| `?tour` | 자동 둘러보기로 시작 |
| `?clean` | UI 숨김(녹화용) |
| `?seed=N`, `?birdseed=N` | 교통·새 배치 난수 |

## 테스트와 캡처

```bash
npm test                                   # 투영, 교통 불변식(겹침 없음, 정체 해소 등), 새 로직
node tools/shot.mjs out.png "clean" "window.__iso.cam.set(800,1200,260),1" 1440 900 3
node tools/capture.mjs tour.mp4            # 둘러보기를 프레임 단위로 결정론적 녹화
```

`window.__iso` 에 캡처·테스트용 손잡이가 있습니다: `manual(true)` 뒤 `step(dt)` 로 한 프레임씩 진행, `cam.set(x, y, vh)`, `state`(시각·계절), `traffic`, `birds`.

테스트가 보지 못하는 것: 셰이더 출력. 화면에 사람·차·새가 실제로 그려지는지는 스크린샷으로 확인해야 합니다.

## 휴대폰과 인앱 브라우저

트위터 같은 앱 안의 브라우저(iOS WKWebView, Android WebView)에서 열리는 것을 기준으로 맞췄습니다.

- 휴대폰에서는 절반 해상도 그림을 씁니다. 큰 그림과 2배 버퍼는 메모리를 많이 써서 앱 안 브라우저가 탭을 죽일 수 있습니다. `?res=2` 로 강제할 수 있습니다.
- 장면 데이터는 비압축 `scene.json` 을 먼저 읽습니다. `DecompressionStream` 이 없는 구형 브라우저에서도 열리게 하기 위해서입니다.
- 화면 높이는 `100dvh` 와 safe-area 여백을 씁니다. 앱 안 브라우저는 위아래에 자체 바가 있어 `100vh` 가 맞지 않습니다.
- 캔버스는 `touch-action: none` 이라 당겨서 새로고침이나 페이지 확대가 지도 조작을 가로채지 않습니다.
- 소리는 기본 꺼짐이고, 버튼을 누른 뒤에만 재생됩니다.
- WebGL2 를 쓸 수 없으면 정지 그림과 안내 문구를 보여 줍니다.
