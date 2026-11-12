#!/bin/bash
# 전체 지도 8x8 타일 렌더(CPU). 사용: render_all.sh <출력폴더> [병렬 수=8] ["i j" 목록 파일(없으면 전체)]
cd "$(dirname "$0")"; D=${1:-full2}; N=${2:-8}; mkdir -p $D
export P3D_ROOT=${P3D_ROOT:-work/} P3D_KHS=${P3D_KHS:-work/khs/} PY=${PY:-python3} P3D_W=2752 P3D_H=1696 D
( [ -n "$3" ] && cat "$3" || for j in 0 1 2 3 4 5 6 7; do for i in 0 1 2 3 4 5 6 7; do echo "$i $j"; done; done ) | xargs -P $N -L 1 bash -c '
  i=$0; j=$1; o=$D/t_${i}_${j}
  [ -f ${o}_z.png ] && exit 0
  $PY -u gen.py $((i*2752)) $((j*1696)) $o > ${o}.log 2>&1 || echo "FAIL $o"
'
echo ALLDONE
