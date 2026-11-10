#!/usr/bin/env bash
# 생성 장비에서 재작업용 ComfyUI 컨테이너를 띄우거나 내린다. 기존 작업을 방해하지 않도록 GPU·컨테이너·포트가 비어 있을 때만 뜬다.
#   gen_server.sh up | down | status
set -euo pipefail
BASE="${GEN_REMOTE_DIR:-/srv/gen/redraw}"
NAME=redraw-comfy
case "${1:-status}" in
  up)
    if docker ps --format '{{.Names}}' | grep -qx "$NAME"; then echo "already up"; exit 0; fi
    test -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)" || { echo 'GPU busy'; exit 20; }
    test -z "$(docker ps -q)" || { echo 'other containers running'; docker ps --format '{{.Names}}'; exit 21; }
    if curl -sf --max-time 2 http://127.0.0.1:8188/queue >/dev/null; then echo '8188 occupied'; exit 22; fi
    docker rm -f "$NAME" >/dev/null 2>&1 || true
    cat > "$BASE/model-paths.yaml" <<'YAML'
iso_seoul_redraw:
  base_path: /srv/gen/models/apache-qwen-edit/
  diffusion_models: diffusion_models
  text_encoders: text_encoders
  vae: vae
  loras: loras
iso_seoul_nodes:
  base_path: /srv/gen/redraw/
  custom_nodes: custom_nodes
YAML
    docker run -d --name "$NAME" --oom-score-adj 1000 --memory 96g --gpus all --ipc host --network host \
      -v /srv/gen:/srv/gen -w /srv/gen/comfy/ComfyUI comfyui:local \
      bash -c "python -u main.py --listen 127.0.0.1 --port 8188 --extra-model-paths-config $BASE/model-paths.yaml --input-directory $BASE/in --output-directory $BASE/out --reserve-vram 16 >> $BASE/logs/server.log 2>&1"
    for i in $(seq 1 90); do curl -sf --max-time 2 http://127.0.0.1:8188/queue >/dev/null && { echo up; exit 0; }; sleep 2; done
    echo 'server did not come up'; tail -20 "$BASE/logs/server.log"; exit 1 ;;
  down) docker stop "$NAME" >/dev/null 2>&1 || true; docker rm "$NAME" >/dev/null 2>&1 || true; echo down ;;
  status) docker ps --format '{{.Names}} {{.Status}}'; free -g | sed -n 2p ;;
esac
