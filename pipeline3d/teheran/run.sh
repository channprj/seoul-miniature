#!/bin/bash
# 테헤란로 지도를 처음부터 굽는 순서. 작업 폴더(입력·중간 자료를 둘 곳, 예: work/teheran)에서 실행한다.
#   PY=/path/to/python-with-bpy bash /path/to/pipeline3d/teheran/run.sh [SPP=64]
# 양식 패스(이미지 모델)는 돌리지 않는다: 조건 렌더를 그대로 그림으로 굽는다. 양식 결과가 있으면 build_assets_th.py --raw 로 넣는다.
set -e
T="$(cd "$(dirname "$0")" && pwd)"; Y="$T/../yeouido"; PY=${PY:-python3}; export PY SPP=${SPP:-64}
export P3D_AREA="$T" P3D_SCENE="$PWD/scene.json" P3D_DZS=0.0625 YD_PASS=passT YD_BOARD=T YD_CLS=clsT/ground_cls
bash "$T/fetch_osm.sh"                                                    # osm/*.json
P3D_ORG='[204300.0, 545000.0]' P3D_LM='{}' $PY "$Y/prep.py"               # scene.json (원점 = 선릉역 근처, EPSG:5186 m)
$PY "$T/prep_extra.py"                                                    # 건물 보충·랜드마크·출입구·왕릉·공사 터
bash "$T/render_tiles.sh" passT 3 5                                       # passT/t_i_j*.png (8×8 타일)
$PY "$Y/stitch_halfF.py"                                                  # passT/cond.png, cond_id.png, cond_z.png, meta.json
mkdir -p clsT && P3D_PXR=0.625 P3D_W=5504 P3D_H=3392 P3D_GTEX=0.25 $PY "$Y/clsdump.py" T 0 0 "$PWD/clsT/ground_cls"
P3D_PXR=0.15625 $PY "$Y/make_classes_ydF.py"                              # passT/classes_05m.png
$PY "$Y/export_movers.py"                                                 # movers/T_movers.json (차로)
$PY "$T/build_assets_th.py" --pass passT --work bake --install "$T/../../assets/teheran"
