#!/bin/bash
# 테헤란로 한 구역만 고쳐 굽기. 작업 폴더(osm/ 이 있는 곳, 예: work/teheran)에서 실행한다. 전체를 다시 굽는 순서는 run.sh.
#   PY=/path/to/python-with-bpy bash /path/to/pipeline3d/teheran/patch.sh "6_1[,i_j …]" [기준 커밋=HEAD] [patch_tiles.py 에 넘길 인자 …]
# 기준 커밋의 코드로 「고치기 전」 타일을, 지금 작업 트리의 코드로 「고친 뒤」 타일을 렌더해 달라진 자리만 assets/teheran/ 에 덧입힌다(patch_tiles.py).
# 자산은 기준 커밋의 것이어야 한다(다시 돌릴 때는 먼저 git checkout -- assets assets.manifest.json). 타일 가장자리에 닿는다는 경고가 나오면 이웃 타일을 더해 다시 돌린다.
set -e
T="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$T/../.." && pwd)"; PY=${PY:-python3}; TILES=$1; REV=${2:-HEAD}; shift; [ $# -gt 0 ] && shift; SPP=${SPP:-48}
export P3D_DZS=0.0625 YD_BOARD=T YD_CLS=clsT/ground_cls
scene() { # 코드 폴더, 장면 폴더: prep.py → prep_extra.py
  mkdir -p "$2"; [ -e "$2/osm" ] || ln -s "$PWD/osm" "$2/osm"
  (cd "$2" && P3D_AREA="$1/teheran" P3D_SCENE="$PWD/scene.json" P3D_ORG='[204300.0, 545000.0]' P3D_LM='{}' $PY "$1/yeouido/prep.py" > prep.log && P3D_AREA="$1/teheran" $PY "$1/teheran/prep_extra.py" >> prep.log)
}
render() { # 코드 폴더, 장면 파일, 출력 폴더
  mkdir -p "$3"
  for t in ${TILES//,/ }; do i=${t%_*}; j=${t#*_}
    P3D_AREA="$1/teheran" P3D_SCENE="$2" P3D_PXR=0.15625 P3D_W=2752 P3D_H=1696 P3D_SPP=$SPP $PY -u "$1/yeouido/gen_area.py" T $((i*5504)) $((j*3392)) "$PWD/$3/t_${i}_${j}" > "$3/t_${i}_${j}.log" 2>&1 < /dev/null || { echo "FAIL $3/t_$t"; exit 1; }
  done
}
rm -rf base_src && mkdir base_src && git -C "$REPO" archive "$REV" pipeline3d | tar -x -C base_src      # 고치기 전 코드
scene "$PWD/base_src/pipeline3d" base_scene; render "$PWD/base_src/pipeline3d" "$PWD/base_scene/scene.json" base
scene "$T/.." new_scene; cp new_scene/scene.json scene.json; render "$T/.." "$PWD/scene.json" new
export P3D_AREA="$T" P3D_SCENE="$PWD/scene.json"
mkdir -p clsT && P3D_PXR=0.625 P3D_W=5504 P3D_H=3392 P3D_GTEX=0.25 $PY "$T/../yeouido/clsdump.py" T 0 0 "$PWD/clsT/ground_cls"
YD_TILES=$TILES YD_PASS=new P3D_PXR=0.15625 $PY "$T/../yeouido/make_classes_ydF.py"                           # new/classes_05m.png (그 타일만)
$PY "$T/patch_tiles.py" --base base --new new --tiles "$TILES" --assets "$REPO/assets/teheran" --manifest "$REPO/assets.manifest.json" "$@"
