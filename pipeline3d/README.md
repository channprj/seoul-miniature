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
| `teheran/fetch_osm.sh`, `teheran/prep_extra.py` | 입력·장면 자료 | 테헤란로: OSM 받기(건물은 여섯 칸으로 나눠서) + Overture 풋프린트, `yeouido/prep.py` 결과에 건물 보충·큰길가 높이·랜드마크 윤곽·지하철 출입구·왕릉·교량 높이를 더한다 |
| `teheran/cam.py`, `teheran/lm_build.py` | 카메라·빌더 | 판 T(θ −24°, 15.625 cm/px). 랜드마크(위워크타워·GT타워·코엑스 등), 기와지붕 전각, 봉분 언덕, 홍살문, 공사 현장(가림벽·굴착·버팀보·골조·타워크레인). `yeouido/gen_area.py` 가 `P3D_AREA` 로 읽는다 |
| `teheran/plaza_samseong.py` | 빌더 | 삼성역 광장: 선큰 마당(밀레니엄 광장), 달걀꼴 조형탑, 판석·화단·채광창·가로등, 호텔 앞 천막, 공사 야적장(벽화 담장·창고·크롤러 크레인·펌프카). `lm_build.py` 가 끝에서 읽는다. 자리는 `prep_extra.py` 가 `scene.json` 의 `samseong` 에 적는다 |
| `teheran/patch.sh`, `teheran/patch_tiles.py` | 부분 굽기 | 한 구역만 고쳤을 때: 그 타일을 고치기 전·후 코드로 각각 렌더해 달라진 화소만 지금 자산에 덧입힌다(팔레트·다른 타일은 그대로) |
| `teheran/render_tiles.sh`, `teheran/build_assets_th.py`, `teheran/run.sh` | 렌더·굽기 | 8×8 타일 렌더, 양식 패스 없이 조건 렌더를 그대로 굽는 굽기(여의도 굽기의 단계 함수를 부른다), 처음부터 끝까지의 순서 |
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
| `common/blend_save.py`, `common/roofgrid.py`, `common/BLEND-README.md` | 장면 저장 | `--save-blend` 가 부른다. 텍스처 넣기·경로 정리·장면 속성, 기와 지붕을 그림 + 지오메트리 노드로 |
| `common/render_window.py` | 장면 저장 | 저장한 .blend 에서 원하는 창(타일)만 렌더 |
| `gyeongbokgung/insert_khs.py` | 장면 저장 | 공개 경복궁 .blend 의 전각 자리에 직접 받은 국가유산청 모델을 끼운다 |
| `common/export_glb.py`, `common/view_glb.py` | 장면 저장 | 저장한 .blend 에서 구역 GLB·여의도 랜드마크별 GLB 를 내고, GLB 를 다시 불러와 한 장 렌더해 확인 |

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
| `P3D_AREA`, `P3D_SCENE` | `yeouido/gen_area.py`, `export_movers.py`, `make_classes_ydF.py` | 다른 지역의 `cam.py`·`lm_build.py` 폴더(기본 `yeouido/`), 장면 자료 경로(기본 `P3D_AREA/scene.json`) |
| `P3D_ORG`, `P3D_LM` | `yeouido/prep.py` | 지역 원점(EPSG:5186 m, JSON 배열), 랜드마크 표(JSON). 기본은 여의도 |
| `P3D_DZS` | `yeouido/gen_area.py` | 깊이 패스 단위(m, 기본 0.05). 화면 세로가 약 2100 m 를 넘는 판은 키운다(테헤란로 0.0625) |
| `YD_PASS`, `YD_BOARD`, `YD_CLS` | `yeouido/stitch_halfF.py`, `make_classes_ydF.py`, `export_movers.py` | 타일 폴더(기본 `halfF`), 판 이름(기본 `F`), 지면 분류 래스터(기본 `clsF/ground_cls`) |
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

## 장면을 .blend 로 저장하기

두 생성기 모두 `--save-blend <경로.blend>` 를 주면 렌더 직전 장면(카메라·해·재질·텍스처 포함)을 저장하고, `--no-render` 를 더하면 렌더 없이 끝냅니다. 창 크기(`P3D_W`·`P3D_H`)를 타일보다 크게 주면 그 창 전체가 한 장면이 됩니다. 공개 릴리스의 .blend 는 지도마다 2 × 2 구역(구역 하나 = 8 × 8 타일 중 4 × 4)으로 이렇게 만들었습니다.

```bash
# 여의도 구역 (qi, qj) ∈ {0,1}²
cd yeouido && P3D_PXR=0.125 P3D_W=11008 P3D_H=6784 P3D_SPP=256 \
  python gen_area.py F $((qi*22016)) $((qj*13568)) out/y --save-blend yeouido_q${qi}${qj}.blend --no-render
# 경복궁 구역(국가유산청 모델 없이, 전각 자리 표시)
cd gyeongbokgung && P3D_GROUND=v2 P3D_KHS_SLOTS=work/placements.json P3D_KHS_GEO=work/khs/scene_geometry.json P3D_W=11008 P3D_H=6784 \
  python gen.py $((qi*11008)) $((qj*6784)) out/g --save-blend gyeongbokgung_q${qi}${qj}.blend --no-render
# 저장한 파일에서 타일 (i, j) 하나 렌더(두 지도 모두 타일 2752×1696 px)
python common/render_window.py gyeongbokgung_q01.blend $((3*2752)) $((4*1696)) 2752 1696 t_3_4.png
```

- 이미지(입면 텍스처, 지면 그림)는 모두 파일 안에 넣고 경로 칸은 `//textures/…` 로 둡니다. 압축 저장(zstd)입니다.
- Blender 는 경로 칸을 짧은 값으로 바꿔도 칸 뒤쪽에 옛 값을 남긴 채 저장하고, 렌더로 저장한 PNG 에는 .blend 경로가 메타데이터로 들어갑니다. 그래서 `blend_save.py` 는 그림을 넣은 바이트로 새로 만들어 바꿔 끼우고(PNG 글 청크 제거), 저장 뒤 압축을 풀어 NUL 바로 뒤의 절대 경로 조각과 `P3D_SCRUB`(쉼표 목록) 낱말이 든 문자열을 0 으로 지웁니다(`zstandard` 모듈이 있을 때). 확인은 `zstd -dc x.blend | strings | grep -iE "$HOME|/tmp/|<내 장비 이름>"`.
- 경복궁의 기와 지붕(높이장, 5–8 cm 격자)은 메시로 두면 구역 하나가 수 GB 라서, 지붕마다 16비트 높이 PNG + RGBA 색 PNG 와 노드 그룹 `P3D_RoofGrid` 로 둡니다. 열 때 같은 격자·같은 면을 다시 만듭니다(높이 양자화 오차는 지붕 높이 범위의 1/131070). 경복궁 구역 파일에서 타일 하나를 렌더하면 최대 메모리가 약 14 GB 입니다(8 스레드, 검증용 ID 패스까지 하면 36–60 GB). 노드 그룹 안의 정수 노드 `Step`(기본 1)을 2–4 로 올리거나 `render_window.py --roof-step N` 을 주면 격자를 건너뛰어 줄어듭니다(2 에서 약 7 GB).
- `P3D_KHS_SLOTS` 는 전각 배치 파일(모델 이름, 회전·이동, 평면 윤곽)입니다. 이 파일은 저장소에 없지만, 같은 값(모델 이름·`theta`·`tx`·`ty`·`tz`)이 릴리스 .blend 의 자리 표시 오브젝트 속성에 들어 있습니다. 주지 않으면 자리 표시 없이 대체 모형만 섭니다. 국가유산청 모델을 불러오지 않고, 그 모델이 있었으면 빠졌을 오브젝트(평면에 50% 넘게 덮인 건물·담, 지붕 속 나무, 광화문 OSM 모형)를 컬렉션 `KHS_STANDIN/<자리>` 로 모으고, 자리 표시 빈 오브젝트를 `KHS_SLOTS` 에 둡니다.

### GLB 로 내보내기

```bash
python common/export_glb.py quad gyeongbokgung_q01.blend gyeongbokgung_q01.glb [--roof-step 0.2] [--max-tex 8192]
python common/export_glb.py landmarks landmarks/ yeouido_q00.blend yeouido_q01.blend yeouido_q10.blend yeouido_q11.blend
python common/view_glb.py landmarks/yeouido_63_building.glb 63.png front      # 다시 불러와 한 장 렌더
```

- 재질은 Principled BSDF 의 기본색(평색 또는 창 격자·입면 텍스처)만 남기고 툰 혼합 셰이더를 건너뜁니다. 텍스처 보간 Closest → glTF NEAREST. 툰 명암(3단·테두리)은 glTF 로 옮겨지지 않습니다.
- 경복궁 기와 지붕은 높이장 그림에서 약 `--roof-step` m 격자 메시(꼭짓점 색 `COLOR_0`, 부드러운 음영)로 다시 만듭니다. 0.2 m 에서 구역 하나 89–133 MB.
- 카메라·해는 빼고, 오브젝트·장면 사용자 속성은 `extras` 로 들어갑니다. +Y 위, 단위 m, Draco·meshopt 압축 없음.
- `landmarks` 는 장면 속성 `p3d_meta` 의 `landmark:*` 종류와 KBS 신관·별관을 건물(단지) 단위로 묶어, 원점을 바닥 중심으로 옮겨 하나씩 냅니다. 묶음 표는 스크립트의 `GROUP`, 결과 목록은 `landmarks.json`.

### 국가유산청 모델 끼우기

```bash
python gyeongbokgung/insert_khs.py gyeongbokgung_q01.blend ~/khs-downloads/ gyeongbokgung_q01_khs.blend --list   # 자리와 찾은 원본 보기
python gyeongbokgung/insert_khs.py gyeongbokgung_q01.blend ~/khs-downloads/ gyeongbokgung_q01_khs.blend
```

- `~/khs-downloads/` 에 digital.khs.go.kr 에서 받은 zip 을 받은 이름 그대로 두세요(예: `국보_경복궁_경회루.zip`). 광화문은 `SM_GwanghwamunComplex.fbx` 가 든 폴더를 두면 됩니다.
- 자리마다 FBX 를 불러와 변환을 굽고, 떠돌이 객체를 빼고, 400 m 를 넘으면 cm 단위로 보고 0.01 배 하고, 지면 재질 면을 지면 ID 로 나눈 뒤 자리 표시의 `theta`·`tx`·`ty`·`tz` 로 놓습니다. 그 자리의 대체 모형은 지웁니다. 못 찾은 자리는 대체 모형을 그대로 둡니다.
- Blender 가 못 읽는 ASCII FBX(영추문)는 FBX2glTF 등으로 `<이름>_conv.glb` 를 만들어 같은 폴더에 두면 그것을 읽습니다.
- 텍스처는 렌더 캐시와 같게 정리합니다: FBX 안 경로 대신 이름으로 찾고, 전각 zip 밖의 공용 텍스처(예: `T_KoreanTile_BC`)는 같은 폴더의 다른 zip 에서 빌리며, B 채널이 비어 검게 나오는 2채널 노멀맵은 Z 를 복원한 사본을 씁니다. 끝내 없는 그림은 노드 연결을 끊습니다.
- 시험: zip 129개로 `gyeongbokgung_q01.blend` 의 17자리에 모두 끼워(약 4.5분, 최대 18 GB) 타일 t_3_4 를 렌더하니 국가유산청 모델로 렌더한 공개판 조건 렌더와 전각 자리 안 MAE 1.21 / 255, 타일 전체 0.196 이었습니다.
- 출력 파일에는 국가유산청 자료가 들어갑니다. 다시 올리지 말고, 각자 받게 하세요.

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

## 테헤란로 순서

여의도 스크립트를 환경 변수로 지역만 바꿔 다시 쓰고, 지역 고유의 것만 `teheran/` 에 둡니다. 양식 패스는 돌리지 않았습니다(GPU 가 없는 장비에서 만들었습니다). 순서 전체가 `teheran/run.sh` 에 있습니다.

```bash
mkdir -p work/teheran && cd work/teheran
PY=/path/to/python-with-bpy bash ../../pipeline3d/teheran/run.sh      # OSM 받기 → scene.json → 렌더 → 분류 맵 → 굽기 → assets/teheran/
```

Apple M5 Pro(15코어)에서 64타일 렌더(48 spp, 2프로세스 × 7스레드)가 약 30분, 굽기가 몇 분 걸렸습니다. 장면을 고친 뒤에는 `passT/` 의 해당 타일 파일을 지우고 `render_tiles.sh` 를 다시 돌리면 그 타일만 렌더합니다.

### 한 구역만 고치기(부분 굽기)

전체 굽기는 64타일 조건 렌더가 모두 있어야 하고, 팔레트를 새로 뽑으므로 타일 6천 장이 다 바뀝니다. 한 구역의 장면만 고쳤다면(예: 삼성역 광장) 그 타일만 다시 렌더해 덧입힙니다.

```bash
cd work/teheran                                                       # osm/ 이 있는 작업 폴더. assets/teheran 은 기준 커밋 그대로여야 한다
PY=/path/to/python-with-bpy bash ../../pipeline3d/teheran/patch.sh 6_1 HEAD --landmark 'millennium|코엑스 밀레니엄 광장|place|1189.5,519.5,0'
```

- `patch.sh` 는 기준 커밋(`HEAD`)의 코드로 「고치기 전」 타일을, 작업 트리의 코드로 「고친 뒤」 타일을 렌더합니다. 두 렌더가 같은 OSM 자료·같은 표본 수라서, ID·깊이가 다르거나 색이 뭉쳐서 다른 화소가 곧 고친 자리입니다(새 물체의 그림자 포함). OSM 을 새로 받으면 가로수 몇 그루가 공개판과 달라질 수 있는데, 그런 차이는 두 렌더에 똑같이 들어 있어 덧입히는 범위에 들지 않습니다.
- `patch_tiles.py` 는 그 화소만 지금 팔레트(128색)로 양자화해 z8 타일에 넣고, z4·z2·z1·`bg.png`·`bg_1x.png` 는 그 화소가 든 칸만 다시 줄입니다. 깊이·분류·수관 맵은 전체 굽기의 `step_maps` 를 그 타일만 채운 캐시로 돌려 달라진 칸만 옮깁니다. `--landmark` 로 `map.json` 에 자리 이름을 더하고, `--manifest` 로 `assets.manifest.json` 의 sha256 을 고칩니다.
- 새 색은 팔레트에 있는 색 가까이로 고르세요(분홍·주황처럼 팔레트에 없는 색은 가장 가까운 벽돌색·노랑으로 바뀝니다). 달라진 화소가 타일 가장자리에 닿으면 경고가 나오니 이웃 타일을 더해 다시 돌립니다.
- 지면 ID(1)로 세운 낮은 면은 굽기에서 높이 −1.55 m 아래가 물로 분류됩니다(선큰 마당 바닥을 −1.4 m 에 둔 까닭). 물가처럼 도려낸 구덩이의 비탈을 빼려면 빌더가 전역 `NOSKIRT`(다각형)를 둡니다.
- 삼성역 광장 한 타일(48 spp)은 Apple M6(12코어)에서 렌더 한 번에 약 50초, 덧입히기에 15초쯤 걸렸고, 바뀐 파일은 타일 21장과 맵·목록 일곱 장입니다.

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
