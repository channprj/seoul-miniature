# pipeline3d — 지금 그림을 만든 스크립트

경복궁과 여의도의 지금 그림(3D 장면 → 조건 렌더 → 양식 패스 → 굽기)을 만들 때 실제로 돌린 스크립트의 사본입니다.
절차와 각 단계의 이유는 [docs/PIPELINE.md](../docs/PIPELINE.md)에, 프롬프트 원문은 [docs/PROMPTS.md](../docs/PROMPTS.md)에 있습니다.

**바로 돌아가는 도구가 아닙니다.** 작업하면서 고쳐 쓴 판이라 다음과 같은 한계가 있습니다.

- 지역마다 상수(카메라 판, 랜드마크 이름과 ID, 잠금 문턱값)가 코드 안에 박혀 있습니다.
- 입력 데이터(OSM 원본, 국가유산청 3D, 중간 렌더)는 들어 있지 않습니다. 아래 "입력"을 보고 직접 준비해야 합니다.
- 경복궁 장면은 이전 작업에서 물려받은 중간 자료(건물 풋프린트 표, 평색 알베도 렌더)를 읽습니다. 새 동네에 따라 하려면 OSM 원본에서 바로 시작하는 **여의도 경로를 본으로** 삼는 편이 낫습니다.

내부 경로는 환경 변수와 상대 경로로 바꿔 두었습니다. 코드 주석의 "리드", "워커", "n차"는 작업 기록의 단계 이름입니다.

## 폴더

| 경로 | 단계 | 내용 |
|---|---|---|
| `yeouido/fetch_osm.sh` | 입력 | Overpass 에서 건물·도로·면·점 받기 → `osm/*.json` |
| `yeouido/prep.py` | 장면 자료 | OSM → 지역 좌표(m) 장면 자료 `scene.json`(건물 높이·종류, 도로, 면, 나무, 랜드마크) |
| `yeouido/cam.py` | 카메라 | 판(board) 정의. 판 F = 방위 θ 180°, 고도 35°, 화면 2752×1696 m |
| `yeouido/gen_area.py` | Blender 장면 + 렌더 | `scene.json` → 한 타일의 색·ID·깊이 렌더(`bpy`). 일반 건물·아파트·타워·교량·공원 규칙 |
| `yeouido/lm_build.py` | 랜드마크 | 63빌딩·파크원·IFC·국회의사당 등 전용 모델과 툰 재질. `gen_area.py` 가 실행 중에 읽어 들인다 |
| `yeouido/render_tiles.sh` | 렌더 | 8×8 타일 병렬 렌더(CPU) |
| `yeouido/stitch_halfF.py` | 렌더 | 타일 이어 붙이기 + 점검(빈 타일, 모르는 ID, 이음매 단차) |
| `yeouido/clsdump.py`, `yeouido/make_classes_ydF.py` | 분류 맵 | 지면 분류 래스터 → 0.5 m 분류 맵·랜드마크 맵(프롬프트 조립용) |
| `yeouido/yd_prompt.py`, `yeouido/yd_prompt_halfF.py` | 프롬프트 | 창마다 프롬프트를 조립하는 모듈(여의도 전체 실행에 쓴 판) |
| `yeouido/export_movers.py` | 앱 | 차로·철도·배 경로 |
| `yeouido/build_assets_yd.py` | 굽기 | cache → lock → quant → maps → tiles → mapjson → keys |
| `gyeongbokgung/gen.py` | Blender 장면 + 렌더 | 경복궁 장면(한옥·궁궐·담·나무·국가유산청 모델 배치) |
| `gyeongbokgung/osm_blds.py`, `prep_ground.py` | 입력 | OSM 건물 보충, 지면 그림·지면 분류 |
| `gyeongbokgung/render_all.sh`, `stitch.py`, `make_classes.py` | 렌더 | 8×8 타일 렌더, 이어 붙이기, 0.5 m 분류 맵 |
| `gyeongbokgung/p3d_prompt.py` | 프롬프트 | 경복궁 창별 프롬프트(여의도 모듈도 이 문장을 가져다 쓴다) |
| `gyeongbokgung/build_assets.py` | 굽기 | cache → lock → quant → maps → tiles → keys |
| `gyeongbokgung/make_tiles.py` | 타일 | 256 px 타일 피라미드 + `manifest.json` |
| `common/hd_coord.py` | 양식 패스 | 조정자. 공유 latent 하나를 들고 스텝마다 창 작업을 큐에 넣고, 창별 예측을 겹침 가중 평균한다 |
| `common/hd_worker.py` | 양식 패스 | 워커 드라이버(표준 라이브러리만). 큐에서 작업을 가져와 ComfyUI 에 넘긴다 |
| `common/iso_hd_tasks.py` | 양식 패스 | ComfyUI 사용자 노드. 작업 종류 enc(조건 인코드)·den(한 스텝 예측)·dec(디코드) |
| `common/run_style_pass.sh` | 양식 패스 | 한 장비에서 위 셋을 묶어 돌리는 예 |

## 준비물

- Python 3.11, `bpy` 5.0.1(PyPI 휠, 별도 Blender 앱 없이), `numpy`, `pillow`, `shapely`, `scipy`. 렌더는 CPU(Cycles)로 했습니다.
- ComfyUI 와 모델 4개(파일 이름은 `common/run_style_pass.sh` 머리말). 모두 Apache-2.0 입니다.
- 공간: 22016×13568 PNG 여러 장과 굽기 캐시(npy)로 지역 하나에 수십 GB.

## 환경 변수

| 변수 | 쓰는 곳 | 뜻 |
|---|---|---|
| `P3D_ROOT` | `gyeongbokgung/*` | 입력 폴더(기본 `work/`). 그 아래 `redraw/` 에 카메라 json·OSM·풋프린트 표를 둔다 |
| `P3D_OLD_CLASSES` | `gyeongbokgung/prep_ground.py` | 이전 판 앱 클래스 맵(0.5 m). 렌더에 녹지가 없던 곳을 잔디로 보충하는 데만 쓴다 |
| `P3D_KHS` | `gyeongbokgung/gen.py` | 국가유산청 광화문 3D 기록을 풀어 둔 폴더(아래). 없으면 광화문을 OSM 윤곽 모형으로 세운다 |
| `P3D_KHSP` | `gyeongbokgung/gen.py` | 전각 배치 파일(json). 없으면 전각을 OSM 윤곽 + 규칙 지붕으로 세운다 |
| `P3D_W`, `P3D_H` | 두 생성기 | 렌더 창 크기(px). 타일 렌더는 2752×1696 |
| `P3D_PXR` | `yeouido/gen_area.py` | 렌더 해상도(m/px). 여의도는 0.125 |
| `P3D_SPP`, `P3D_THREADS` | `yeouido/gen_area.py` | Cycles 표본 수(여의도 256), 프로세스당 스레드 |
| `P3D_FULL`, `YD_FULL` | 프롬프트 모듈 | 분류 맵 폴더(경복궁 `full5`, 여의도 `halfF`) |
| `PY` | 셸 스크립트 | 쓸 파이썬(기본 `python3`) |
| `COMFY_PORTS`, `HD_BATCH` | `common/run_style_pass.sh` | ComfyUI 포트 목록, 워커가 한 번에 가져갈 작업 수 |

## 입력

이 저장소에는 입력 데이터가 없습니다. 각자 받아 두세요.

| 입력 | 받는 곳 | 조건 |
|---|---|---|
| OSM 건물·도로·수면·녹지·담·나무 | Overpass API(`yeouido/fetch_osm.sh` 의 질의) | ODbL 1.0, "© OpenStreetMap contributors" |
| 건물 높이(경복궁 일대) | 국토교통부 GIS건물통합정보(data.go.kr/data/15083092), Overture Maps 건물 테마 | 공공누리 제1유형 / ODbL·CC BY 4.0 |
| 궁궐 전각 3D | 국가유산청 디지털 서비스(digital.khs.go.kr)의 「경복궁 3D 기록」. 로그인과 이용 신청서가 필요하고, 일부 대용량 파일은 따로 「대용량파일 제공신청」을 합니다 | 공공누리 제1유형, 출처 "국가유산청" |

국가유산청 파일은 받은 그대로 다른 곳에 올리지 마세요(원본 재배포는 하지 않았습니다). 이 저장소는 그 모델을 장면에 배치해 렌더한 결과를 다시 그린 2D 그림만 담고 있습니다.

`P3D_KHS` 폴더에 `gen.py` 가 기대하는 것: `SM_GwanghwamunComplex.fbx`(광화문·월대 일원 FBX), `tex1024/`(텍스처를 1024 px 로 줄인 것), `scene_geometry.json`(`khs.tx_local`, `khs.ty_local` — FBX 에 좌표계가 없어서 OSM 윤곽에 맞춘 이동값). 전각 배치 파일(`P3D_KHSP`)은 모델마다 `blend`(FBX 를 변환·축척 정리해 둔 캐시), `pass_index`, `zmax`, 평면 윤곽을 담습니다. FBX 를 변환·정합하는 도구는 싣지 않았습니다(전각 46채를 OSM 윤곽에 하나씩 맞춘 수작업이 섞여 있습니다).

## 여의도 순서(본)

```bash
cd pipeline3d/yeouido
mkdir -p osm && ./fetch_osm.sh                       # osm/*.json
python prep.py                                       # scene.json
PY=/path/to/python-with-bpy bash render_tiles.sh 14 4    # halfF/t_i_j*.png  (CPU, 8×8 타일)
python stitch_halfF.py                               # halfF/cond.png, cond_id.png, cond_z.png, meta.json
P3D_PXR=0.5 P3D_W=5504 P3D_H=3392 P3D_GTEX=0.25 python clsdump.py F 0 0 clsF/ground_cls
python make_classes_ydF.py                           # halfF/classes_05m.png, landmarks_05m.png
YD_FULL=halfF python yd_prompt_halfF.py              # 창별 선택 문장 표(확인용)
YD_FULL=$PWD/halfF bash ../common/run_style_pass.sh runs/r1 halfF/cond.png $PWD/yd_prompt_halfF.py 213
YD_BOARD=F python export_movers.py                   # movers/F_movers.json(차로·철도·배). island.json = 섬 윤곽 다각형(장면 좌표)이 필요
python build_assets_yd.py all --raw runs/r1/raw.png --pass halfF --work bake_r1 --jobs 16
```

`render_tiles.sh` 는 `gen_area.py` 를 타일마다 따로 띄웁니다(동시 프로세스 16 이하로 막아 두었습니다). 여의도 64타일은 16병렬 × 4스레드로 22–24분 걸렸습니다.

그다음 뷰어 쪽: 굽기 결과(`bake_r1/` 의 tiles, bg.png, bg_1x.png, depth_rg8.png, classes.png, crown.png, map.json)를 `assets/<지도>/` 에 둡니다. 밤 창문 격자 파일 `winfaces.json` 을 미리 계산하는 도구는 공개 저장소에 아직 없습니다. 파일이 없으면 앱이 첫 확대 때 타일에서 계산합니다.

## 경복궁 순서

여의도와 같은 꼴이지만 입력이 다릅니다.

```bash
cd pipeline3d/gyeongbokgung
python prep_ground.py                                # ground_clean.png, ground_class.png
PY=/path/to/python-with-bpy P3D_KHS=/path/to/khs/gwanghwamun/ bash render_all.sh full 8
python stitch.py && python make_classes.py           # full/cond*.png, meta.json, classes_05m.png
P3D_FULL=full bash ../common/run_style_pass.sh runs/r1 full/cond.png $PWD/p3d_prompt.py 213
python build_assets.py all --raw runs/r1/raw.png --pass full --work bake_r1 --jobs 16
```

`gen.py` 와 `prep_ground.py` 가 읽는 `redraw/hires/`(카메라 json, 건물 풋프린트 표 `city_buildings.json`, 평색 알베도 렌더)와 `redraw/keep/guide6/guide_kinds.png`(이전 판의 건물 유형 맵)는 이전 작업에서 만든 중간 자료라 이 저장소에 없습니다. 같은 형식의 자료를 새로 만드는 대신 여의도 경로(`prep.py` → `scene.json`)를 쓰세요.
