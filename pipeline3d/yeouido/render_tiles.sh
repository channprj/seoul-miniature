#!/bin/bash
# [5차] 판 F(θ=180) 를 12.5 cm/px 로 직접 렌더. 8×8 타일(2752×1696 px = 344×212 m), X0 = i·5504, Y0 = j·3392 (6.25 cm 좌표).
# 이어받기: _z.png 가 있는 타일은 건너뛴다. 사용: bash render_tiles.sh [병렬=14] [스레드=4] ["i j" 목록 파일]   CPU 만, 동시 프로세스 ≤ 16
# SPP 기본 256: 12.5 cm 직접 렌더 64 spp 는 6.25 cm 64 spp 를 2×2 로 줄인 것(px 당 256 표본)보다 거칠다(시험 타일에서 확인).
cd "$(dirname "$0")"; PY=${PY:-python3}; N=${1:-14}; T=${2:-4}; D=${OUTD:-halfF}; mkdir -p $D
[ "$N" -le 16 ] || { echo "병렬 수는 16 이하"; exit 2; }
export N T D SPP GTEX BOARD PY
date +%s > $D/_start
( [ -n "$3" ] && cat "$3" || for j in $(seq 0 7); do for i in $(seq 0 7); do echo "$i $j"; done; done ) | xargs -P $N -L 1 bash -c '
  i=$0; j=$1; o=$D/t_${i}_${j}
  [ -f ${o}_z.png ] && exit 0
  ( /usr/bin/time -f "wall %e s" env P3D_PXR=0.125 P3D_W=2752 P3D_H=1696 P3D_SPP=${SPP:-256} P3D_THREADS=$T ${GTEX:+P3D_GTEX=$GTEX} $PY -u gen_area.py ${BOARD:-F} $((i*5504)) $((j*3392)) $o > ${o}.log 2>&1 ) || { echo "FAIL $o"; rm -f ${o}_z.png; }
'
date +%s > $D/_end; echo ALLDONE
