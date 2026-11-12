#!/bin/bash
# 판 T 를 15.625 cm/px 로 렌더한다. 8×8 타일(2752×1696 px = 430×265 m), X0 = i·5504, Y0 = j·3392 (작업 px).
# 사용(작업 폴더 = scene.json 이 있는 곳): bash render_tiles.sh [출력 폴더=passT] [병렬=3] [스레드=5]   환경: PY(bpy 가 있는 파이썬), SPP(기본 256)
# 이어받기: _z.png 가 있는 타일은 건너뛴다. 장면을 고쳤으면 출력 폴더를 비우고 다시 돌린다.
HERE="$(cd "$(dirname "$0")" && pwd)"; D=${1:-passT}; N=${2:-3}; T=${3:-5}; PY=${PY:-python3}; mkdir -p "$D"
export HERE D T PY SPP P3D_AREA="$HERE" P3D_SCENE="$PWD/scene.json" P3D_PXR=0.15625 P3D_W=2752 P3D_H=1696 P3D_DZS=0.0625
for j in $(seq 0 7); do for i in $(seq 0 7); do echo "$i $j"; done; done | xargs -P "$N" -L 1 bash -c '
  i=$0; j=$1; o=$PWD/$D/t_${i}_${j}
  [ -f ${o}_z.png ] && exit 0
  P3D_SPP=${SPP:-256} P3D_THREADS=$T $PY -u "$HERE/../yeouido/gen_area.py" T $((i*5504)) $((j*3392)) $o > ${o}.log 2>&1 < /dev/null || { echo "FAIL $o"; rm -f ${o}_z.png; }
'
echo ALLDONE
