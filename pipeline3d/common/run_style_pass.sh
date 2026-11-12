#!/bin/bash
# 양식 패스 한 번을 한 장비에서 돌리는 예. 실제 작업에서는 GPU 3장이 같은 공유 폴더(run_dir)를 보며 돌았다.
#   run_style_pass.sh <run_dir> <cond.png> <prompt_module.py> [seed=213]
# 준비:
#   - ComfyUI 가 COMFY_PORTS(공백으로 나눈 포트 목록, 기본 8188)에 떠 있고, iso_hd_tasks.py 가 그 ComfyUI 의 custom_nodes/ 에 있다.
#   - ComfyUI models/ 에 qwen_image_edit_2511_fp8mixed.safetensors(diffusion_models), qwen_2.5_vl_7b_fp8_scaled.safetensors(text_encoders),
#     qwen_image_vae.safetensors(vae), Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors(loras).
#   - PY 는 numpy·pillow 가 있는 파이썬(조정자용). 워커 드라이버는 표준 라이브러리만 쓴다.
# 결과: <run_dir>/raw.png. 중간에 끊겨도 같은 명령으로 다시 부르면 이어서 한다(run_dir/state/).
set -euo pipefail
RUN=$1; COND=$2; PM=$3; SEED=${4:-213}; PY=${PY:-python3}
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$RUN/log"; rm -f "$RUN/stop_all"
"$PY" -u "$HERE/hd_coord.py" "$RUN" --cond "$COND" --origin 0,0 --prompt-module "$PM" --seed "$SEED" >> "$RUN/log/coord.out" 2>&1 &
COORD=$!
i=0
for p in ${COMFY_PORTS:-8188}; do
  HD_BATCH=${HD_BATCH:-2} python3 "$HERE/hd_worker.py" "$RUN" "gpu$i" "$p" >> "$RUN/log/gpu$i.out" 2>&1 &
  i=$((i + 1))
done
wait "$COORD"
touch "$RUN/stop_all"     # 워커는 하던 묶음만 끝내고 나간다
wait
ls -la "$RUN/raw.png"
