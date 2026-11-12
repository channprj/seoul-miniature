# 가져다 쓰기

이 프로젝트의 그림과 장면은 다른 사람이 가져다 새 콘텐츠를 만들라고 열어 둔 것입니다. 영상·글·인쇄물·상품·게임에 써도 되고, 고치거나 다시 배포해도 됩니다. 조건은 **출처 표시** 하나가 기본이고, 지도 데이터를 고쳐서 다시 배포할 때만 같은 조건(ODbL)으로 내야 합니다.

이 문서는 법률 자문이 아닙니다. 한 개인이 각 라이선스 원문을 읽고 정리한 안내입니다.

## 무엇을 어떤 조건으로

| 파일 | 어디 | 라이선스 | 한 줄 요약 |
|---|---|---|---|
| 그림: 배경 그림·타일 | `assets/redraw/bg.png`·`bg_1x.png`·`tiles/`, `assets/yeouido/bg.png`·`bg_1x.png`·`tiles/` | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.ko) | 상업 이용·수정·재배포 가능, 출처 표시 |
| 그림: 미리보기, 이 사이트를 찍은 스크린샷·영상 | `og.png`, 직접 찍은 화면 | CC BY 4.0 | 위와 같음 |
| 보조 그림: 깊이·분류·수관 맵 | `assets/redraw/`·`assets/yeouido/` 의 `depth_rg8.png`·`classes.png`·`crown.png`, `assets/web-poc/occlusion_class8.png`, `pipeline/input/*.png` | CC BY 4.0 | 위와 같음 |
| 장면 데이터 | `assets/web-poc/scene.json(.gz)`, `assets/yeouido/map.json`·`winfaces.json` | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) | 자유 이용, 출처 표시, 고친 데이터를 배포하면 ODbL 로 |
| 3D 장면 | GitHub Releases 의 `.blend`(Blender)와 `.glb`(glTF 2.0) 구역 파일(아래 「받는 곳」) | ODbL 1.0 | 위와 같음 |
| 3D 랜드마크 | GitHub Releases 의 여의도 랜드마크 `.glb`(63빌딩, 파크원, IFC, 국회의사당 등 건물 하나에 파일 하나) | ODbL 1.0 | 위와 같음. 판단 근거는 [LICENSING.md](LICENSING.md) |
| 코드·문서 | `src/`, `test/`, `tools/`, `pipeline/`, `pipeline3d/`, `docs/`, `*.html`, `*.css`, `*.mjs`, `*.md` | MIT | 저작권 표시와 허락 문구를 함께 두면 자유 |
| 배경음 | `assets/audio/*.mp3` | 이번 CC BY 4.0 부여 대상이 아님 | 생성 모델과 조건은 [CREDITS.md](../CREDITS.md) 「배경음 생성 모델」. 이 사이트를 찍은 영상에 함께 담기는 것은 영상과 같은 조건으로 봅니다 |

- 그림은 OpenStreetMap 등에서 만든 3D 장면을 렌더하고 이미지 모델로 양식만 바꾼 것입니다. 그 원천의 출처 표시 조건이 그림에도 따라오므로, 아래 문구처럼 **이 프로젝트와 원천을 함께** 적어 주세요.
- 장면 데이터와 3D 파일(.blend·.glb)은 OSM 의 형상(건물 윤곽·도로·수면)을 그대로 담은 데이터베이스라 ODbL 입니다. 이것으로 렌더한 그림·영상(ODbL 의 "Produced Work")은 출처 표시만 하면 원하는 라이선스로 낼 수 있습니다. 데이터나 장면 자체를 고쳐서 배포하면 그 고친 것도 ODbL 로 내야 합니다.
- 국가유산청 원본 3D 모델은 이 저장소에도 .blend·.glb 에도 없습니다. 쓰려면 직접 받으세요(아래 「주의」).

## 출처 표시 문구(그대로 복사)

### 짧은 판 — 영상 설명란, SNS, 이미지 캡션

경복궁:

```text
그림: 서울 미니어처 by midagedev (CC BY 4.0) https://midagedev.github.io/seoul-miniature/ · 지도 © OpenStreetMap contributors · 국가유산청 경복궁 3D 기록(공공누리 제1유형)
```

여의도:

```text
그림: 서울 미니어처 by midagedev (CC BY 4.0) https://midagedev.github.io/seoul-miniature/?map=yeouido · 지도 © OpenStreetMap contributors
```

영어:

```text
Image: Seoul Miniature by midagedev (CC BY 4.0) https://midagedev.github.io/seoul-miniature/ · Map data © OpenStreetMap contributors
```

경복궁 그림이면 영어 판 끝에 `· Korea Heritage Service, Gyeongbokgung 3D records (KOGL Type 1)` 를 붙이세요.

### 긴 판 — 블로그·기사·책·앱의 크레디트 화면

경복궁:

```text
「서울 미니어처: 경복궁」 midagedev, https://midagedev.github.io/seoul-miniature/
라이선스 CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)
지도 데이터 © OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)
건물 데이터: Overture Maps Foundation (overturemaps.org); East Asian Buildings, Shi et al. 2023 (CC BY 4.0, doi:10.5281/zenodo.8174931)
건물 높이: 국토교통부 GIS건물통합정보(data.go.kr/data/15083092), 공공누리 제1유형
궁궐 전각 형태: 국가유산청 「경복궁 3D 기록」·「사적 경복궁 광화문, 광화문 월대 일원 3D 기록」, 공공누리 제1유형, 국가유산청 디지털 서비스(digital.khs.go.kr)
그림 양식 변환: Qwen-Image-Edit-2511 + Lightning 8-step LoRA (Apache-2.0)
위 기관·단체가 이 작업을 후원하거나 보증한 것은 아닙니다. 실제 지도가 아닙니다.
```

여의도:

```text
「서울 미니어처: 여의도」 midagedev, https://midagedev.github.io/seoul-miniature/?map=yeouido
라이선스 CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)
지도 데이터 © OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)
그림 양식 변환: Qwen-Image-Edit-2511 + Lightning 8-step LoRA (Apache-2.0)
위 단체가 이 작업을 후원하거나 보증한 것은 아닙니다. 실제 지도가 아닙니다.
```

두 지도를 함께 쓰면 경복궁 판을 쓰고 첫 줄에 여의도 주소를 더하면 됩니다.

### 3D 파일(.blend·.glb)을 쓰거나 다시 배포할 때

여의도(구역 파일, 랜드마크 GLB):

```text
3D 장면: 서울 미니어처 by midagedev, https://github.com/midagedev/seoul-miniature · © OpenStreetMap contributors, ODbL 1.0
```

경복궁:

```text
3D 장면: 서울 미니어처 by midagedev, https://github.com/midagedev/seoul-miniature · © OpenStreetMap contributors, ODbL 1.0 · Overture Maps Foundation · East Asian Buildings (Shi et al. 2023, CC BY 4.0) · 건물 높이 국토교통부 GIS건물통합정보(공공누리 제1유형)
```

3D 파일로 렌더한 그림이나 영상만 낼 때도 이 한 줄이면 됩니다. 파일을 고쳐 다시 배포하면 고친 파일도 ODbL 1.0 으로 내고, 고쳤다고 적어 주세요.

- **고쳤으면 고쳤다고** 적어 주세요(CC BY 4.0 의 조건). 예: `원본을 잘라 색을 바꿈`.
- 여의도의 63빌딩·파크원·국회의사당 같은 랜드마크는 사진을 사람이 눈으로 보고 3D 로 만든 것이라 사진 저작자 표시는 필요 없습니다. 사진은 모델에 넣지 않았습니다.
- 이미지 모델 표시는 라이선스 조건이 아니지만, AI 로 만든 그림임을 밝히는 뜻으로 넣었습니다. 빼도 라이선스 위반은 아닙니다.

## 용도별 안내

| 용도 | 할 일 |
|---|---|
| SNS·유튜브 영상 | 짧은 판을 설명란에. 화면 안에 넣을 때는 끝부분 2–3초면 충분합니다. 이 사이트를 그대로 찍을 때는 `?clean` 주소로 UI 를 숨길 수 있지만, 그러면 화면의 출처 표시도 사라지므로 설명란에 꼭 적으세요 |
| 블로그·기사 이미지 | 이미지 바로 아래 캡션에 짧은 판, 글 끝에 긴 판. 원본 링크를 걸어 주세요 |
| 인쇄물·포스터 | 앞면 가장자리에 짧은 판 한 줄. 지면이 좁으면 QR 로 긴 판을 담은 페이지를 가리켜도 됩니다. z8 타일을 이어 붙이면 경복궁은 22016 × 13568 px 라 A1 이상도 됩니다(아래 「받는 곳」) |
| 굿즈 같은 상업 상품 | 그림의 라이선스는 상업 이용을 허용합니다. 다만 그림 속 **실제 건물의 생김새**는 별개의 권리일 수 있습니다(아래 「주의」). 특정 건물을 크게 담은 상품은 따로 확인하세요 |
| 게임·앱에 넣기 | 그림은 크레디트 화면에 긴 판. 장면 데이터(`map.json`, `scene.json`)를 넣거나 고쳐 쓰면 그 데이터는 ODbL — 고친 데이터를 앱과 함께 배포하면 ODbL 로 공개해야 합니다(앱 코드 전체가 ODbL 이 되는 것은 아님). 뷰어 코드는 MIT |
| 다른 동네로 확장 | [pipeline3d/README.md](../pipeline3d/README.md)의 여의도 경로가 본입니다. 스크립트는 MIT, OSM 은 직접 받으면 됩니다. 이 저장소의 .blend 를 고쳐 다시 배포하면 ODbL 입니다 |
| 3D 모델로 쓰기(게임 엔진·웹·3D 도구) | 랜드마크 `.glb` 나 구역 `.glb` 를 받아 그대로 불러오면 됩니다. 크레디트에 긴 판. 모델을 고쳐서 배포하면 그 모델도 ODbL 로 공개해야 합니다. 모델을 넣은 게임 화면·영상은 Produced Work 라 출처 표시만 하면 됩니다. 실제 건물을 본뜬 모델을 **3D 프린트 상품**으로 팔려면 아래 「주의」의 건물 생김새 항목을 보세요 |
| AI 학습·생성 입력 | CC BY 4.0 은 학습·생성 입력도 막지 않습니다. 데이터셋 설명(카드)에 긴 판을 적어 주세요. 이 그림 자체가 이미지 모델 출력이라 실제 사진처럼 쓰면 안 됩니다 |

## 주의

- **국가유산청 원본 모델은 없습니다.** 경복궁 .blend 의 전각 46건과 광화문 자리에는 OSM 윤곽과 높이로 만든 대체 모형이 들어 있습니다. 원래 모델을 쓰려면 [국가유산청 디지털 서비스](https://digital.khs.go.kr)에서 「경복궁 3D 기록」을 직접 받고(로그인과 이용 신청서가 필요합니다) `pipeline3d/gyeongbokgung/insert_khs.py` 로 끼우세요. 그렇게 만든 파일에는 국가유산청 자료가 들어가므로 다시 올리지 말고, 각자 받게 하세요. 공공누리 제1유형 자체는 상업 이용과 변경을 허용하지만, 이 프로젝트는 원본 재배포를 하지 않는 쪽을 택했습니다.
- **실제 건물의 생김새는 별개입니다.** 그림 속 건물은 실제 건물을 본뜬 것이고, 건축물의 생김새는 건축저작물·입체상표·디자인으로 따로 보호될 수 있습니다. 한국 저작권법 제35조 제2항은 공중에게 개방된 장소에 항시 전시된 건축저작물 등을 어떤 방법으로든 복제해 이용할 수 있게 하되, 건축물을 건축물로 복제하는 경우와 **판매 목적으로 복제하는 경우** 등은 예외로 둡니다. 그래서 그림을 영상·글·전시에 쓰는 것은 대개 문제가 적지만, 특정 건물(63빌딩, 파크원, 국회의사당 등)을 전면에 내세운 **굿즈·상품**은 그 건물의 권리자 확인이 필요할 수 있습니다. 랜드마크 3D 모델을 축소 모형(3D 프린트 등)으로 만들어 파는 것도 같은 판매 목적 복제에 해당할 수 있습니다. 나라마다 규칙이 다르니 판매할 곳의 법을 보세요.
- **후원·보증처럼 보이지 않게.** OpenStreetMap, 국가유산청, 국토교통부, Overture Maps, 모델 개발사는 이 작업을 후원하거나 보증하지 않았습니다. 기관 로고를 붙이거나 「○○ 제공」처럼 쓰지 마세요. 공공누리 자료는 이 점이 이용 조건에 들어 있습니다.
- **실제 지도가 아닙니다.** 배치는 공개 지도 데이터를 따랐지만 높이·지붕·창·나무 상당 부분은 추정하거나 그려 넣은 것이고, 사람과 차는 연출입니다. 길 찾기·측량·부동산 설명에 쓰지 마세요.
- 이 프로젝트 이름이나 저자 이름으로 내가 만든 것처럼 오해되게 쓰지 마세요(CC BY 4.0 도 원저작자의 보증을 암시하는 것을 금합니다).

## 받는 곳

### 사이트의 파일

GitHub Pages 가 저장소 루트를 그대로 서빙하므로, 저장소의 경로가 곧 주소입니다.

| 무엇 | 경로 | 크기 |
|---|---|---|
| 경복궁 한 장(낮, 0.25 m/px) | `https://midagedev.github.io/seoul-miniature/assets/redraw/bg.png` | 5504 × 3392 |
| 경복궁 작은 판 | `assets/redraw/bg_1x.png` | 2752 × 1696 |
| 경복궁 타일 | `assets/redraw/tiles/z{단계}_{x}_{y}.png`, 목록 `tiles/manifest.json` | 256 × 256 |
| 여의도 | `assets/yeouido/bg.png`, `bg_1x.png`, `tiles/…` | 같은 꼴 |
| 미리보기 | `og.png` | |

- 확대 단계: `z1.png`(2752 × 1696 한 장), `z2`(5504 × 3392, 22 × 14 타일), `z4`(11008 × 6784, 43 × 27), `z8`(22016 × 13568, 86 × 53). z8 이 가장 세밀한 원본이고 경복궁 6.25 cm/px, 여의도 12.5 cm/px 입니다. `x`, `y` 는 0 부터 시작하는 타일 번호입니다.
- 한 색으로만 찬 타일은 파일이 없고 `manifest.json` 의 `levels.<단계>.solid` 에 `[x, y, 색 번호]`(색은 `colors`)로 적혀 있습니다.
- 그림은 낮 한 벌입니다. 밤·계절·눈비는 뷰어가 실시간으로 입히는 것이라 파일로는 없습니다. 그런 장면이 필요하면 화면을 찍어 쓰세요(`?clean`, `#x,y,높이&t=시각` 주소 옵션은 [APP.md](APP.md)).

### 고해상도 한 장이 필요할 때

z8 타일을 이어 붙이면 공개판 원본 해상도 그대로입니다(경복궁 약 3억 화소). 저장소를 내려받은 뒤:

```bash
python3 - <<'EOF'
import json
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
d = 'assets/redraw/tiles/'                       # 여의도는 assets/yeouido/tiles/
m = json.load(open(d + 'manifest.json')); L = m['levels']['8']; t = m['tile']
out = Image.new('RGB', tuple(L['size']))
for x, y, c in L.get('solid', []): out.paste(tuple(m['colors'][c]), (x * t, y * t, (x + 1) * t, (y + 1) * t))
for y in range(L['grid'][1]):
    for x in range(L['grid'][0]):
        try: out.paste(Image.open(f'{d}z8_{x}_{y}.png').convert('RGB'), (x * t, y * t))
        except FileNotFoundError: pass
out.save('full_z8.png')
EOF
```

양식 패스 전의 3D 렌더(조건 렌더)는 공개하지 않았습니다. 필요하면 아래 .blend 로 직접 렌더할 수 있습니다.

### 3D 파일: 어느 형식을 받을까

| 형식 | 이럴 때 | 다른 점 |
|---|---|---|
| `.blend` | Blender 5.0 이상에서 공개판과 같은 조건 렌더를 다시 만들 때, 장면을 고쳐 다시 렌더할 때 | 카메라·해·툰 재질(3단 명암·테두리)·지붕 노드까지 그대로. 열고 F12 면 공개판과 같은 그림 |
| `.glb` | 게임 엔진(Unity, Unreal, Godot), 웹(three.js, Babylon.js), 다른 3D 도구 | 재질은 **근사**입니다. glTF 표준 재질(기본색 + 창 격자·입면 텍스처, 픽셀 결 유지를 위한 NEAREST 샘플러)만 들어가고, 노드로 만든 툰 명암과 테두리는 옮겨지지 않습니다. 카메라·해도 없습니다. Draco·meshopt 압축은 쓰지 않았습니다(어디서나 열리게) |

둘 다 단위는 m 입니다. `.glb` 는 glTF 규약대로 +Y 가 위입니다. 라이선스는 둘 다 ODbL 1.0 입니다.

### Blender 장면(.blend)

저장소가 아니라 [GitHub Releases](https://github.com/midagedev/seoul-miniature/releases)에 올려 둡니다(파일이 커서 저장소와 사이트에 넣지 않았습니다). 두 지도를 각각 2 × 2 구역으로 나눈 8개 파일이고, 파일 하나가 공개판 그림의 4분의 1(8 × 8 렌더 타일 중 4 × 4)을 맡습니다.

- 열고 바로 렌더(F12)하면 그 구역의 조건 렌더가 공개판과 같은 크기·해상도로 나옵니다. 카메라(정사투영)·해·툰 재질·텍스처가 모두 파일 안에 있습니다.
- 타일 하나만 렌더: `python pipeline3d/common/render_window.py <파일.blend> <x0> <y0> 2752 1696 out.png`.
- 기와 지붕은 메시가 아니라 그림 두 장 + 지오메트리 노드(`P3D_RoofGrid`)로 들어 있고, 열 때 Blender 가 메시를 다시 만듭니다. 그래서 파일은 작지만 렌더할 때 메모리가 많이 듭니다. 경복궁 파일에서 타일 하나를 렌더하면 최대 약 14 GB(여의도는 약 3 GB)이고, 노드 그룹 안의 정수 노드 `Step` 을 2 로 올리면 약 7 GB 로 줄어듭니다(지붕 격자를 건너뛰어 그림이 조금 달라집니다).
- 오브젝트의 `pass_index` 가 건물 ID 이고, 장면 속성 `p3d_meta` 가 ID → 종류 표입니다.
- 경복궁 파일의 `KHS_SLOTS` 컬렉션이 전각 자리 표시, `KHS_STANDIN` 이 대체 모형입니다.
- 라이선스 ODbL 1.0. 이것으로 렌더한 그림을 공개하면 OSM 출처 표시만 하면 됩니다.

### 3D 모델(.glb)

같은 [Releases](https://github.com/midagedev/seoul-miniature/releases)에 있습니다.

- **구역 GLB**: `.blend` 와 같은 2 × 2 구역 8개 파일. 좌표는 장면 좌표 그대로라 여러 개를 불러오면 서로 맞물립니다. 경복궁의 기와 지붕은 `.blend` 의 5–8 cm 높이장 대신 약 20 cm 격자 메시로 줄여 넣었고(기와 골은 꼭짓점 색으로만), 국가유산청 전각 자리에는 `.blend` 와 같은 대체 모형이 들어 있습니다.
- **랜드마크 GLB**(여의도): 63빌딩, 파크원, IFC 서울, 콘래드 서울, 더현대 서울, LG트윈타워, FKI타워, 앵커원, 여의도우체국, 한국거래소, KBS 신관·별관, 국회의사당과 국회 부속 건물 5동, 여의도순복음교회. 건물 하나(여러 동이면 한 단지)에 파일 하나이고, 원점은 건물 바닥 중심입니다. 오브젝트의 사용자 속성(glTF `extras`)에 이름·라이선스·장면 안 원래 위치(`scene_offset_m`)가 들어 있습니다.
- 모양은 OSM 윤곽과 높이에 사진을 눈으로 보고 맞춘 것이라 실제 건물의 정밀 모델이 아닙니다.

## 더 보기

- 출처 전체와 원천별 조건: [CREDITS.md](../CREDITS.md)
- 왜 이렇게 정했는지: [LICENSING.md](LICENSING.md) 「가져다 쓰기 결정」
- 어떻게 만들었는지: [PIPELINE.md](PIPELINE.md), [pipeline3d/README.md](../pipeline3d/README.md)
