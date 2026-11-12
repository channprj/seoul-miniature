#!/usr/bin/env python3
"""작업 큐 워커 드라이버(표준 라이브러리만). 같은 장비의 ComfyUI 에 붙어, 공유 폴더의 todo/ 에서 작업을 가져와 처리시킨다.

  python3 hd_worker.py <run_dir> <worker_name> <comfy_port>

가져오기 = todo/<작업> 을 claimed/<worker>/ 로 rename(원자적). 처리 중에는 그 파일의 mtime 을 갱신한다(살아 있다는 표시).
죽으면 조정자가 오래된 claimed 파일을 todo 로 되돌린다. SIGTERM·SIGINT 나 <run_dir>/stop_<worker>·stop_all 파일이 생기면 하던 묶음만 끝내고 나간다.
"""
import json, os, signal, sys, time, urllib.request, urllib.error

RUN, NAME, PORT = sys.argv[1], sys.argv[2], sys.argv[3]
B = int(os.environ.get('HD_BATCH', '4'))
U = f'http://127.0.0.1:{PORT}'
todo, mine, logf = f'{RUN}/todo', f'{RUN}/claimed/{NAME}', f'{RUN}/log/{NAME}.jsonl'
os.makedirs(mine, exist_ok=True); os.makedirs(f'{RUN}/log', exist_ok=True)
stop = {'v': False}
signal.signal(signal.SIGTERM, lambda *a: stop.update(v=True)); signal.signal(signal.SIGINT, lambda *a: stop.update(v=True))

def graph(paths):
    return {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_edit_2511_fp8mixed.safetensors", "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "lora": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["unet", 0], "lora_name": "Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors", "strength_model": 1.0}},
        "ms": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["lora", 0], "shift": 3.1}},
        "cn": {"class_type": "CFGNorm", "inputs": {"model": ["ms", 0], "strength": 1.0}},
        "t": {"class_type": "IsoHDTasks", "inputs": {"model": ["cn", 0], "clip": ["clip", 0], "vae": ["vae", 0], "tasks": json.dumps(paths)}},
    }

def give_back():
    for n in os.listdir(mine):
        try: os.rename(f'{mine}/{n}', f'{todo}/{n}')
        except OSError: pass

def log(**k):
    with open(logf, 'a') as f: f.write(json.dumps(dict(k, t=time.time(), worker=NAME)) + '\n')

give_back()          # 지난 실행이 남긴 것
errs = 0
while not stop['v'] and not os.path.exists(f'{RUN}/stop_{NAME}') and not os.path.exists(f'{RUN}/stop_all'):
    try: names = sorted(n for n in os.listdir(todo) if n.endswith('.json'))
    except FileNotFoundError: names = []
    got, kind = [], None
    for n in names:
        if kind and n[:3] != kind: continue
        try: os.rename(f'{todo}/{n}', f'{mine}/{n}'); os.utime(f'{mine}/{n}')
        except OSError: continue
        got.append(n); kind = n[:3]
        if len(got) >= B: break
    if not got:
        time.sleep(1); continue
    t0 = time.time()
    try:
        req = urllib.request.Request(U + '/prompt', json.dumps({"prompt": graph([f'{mine}/{n}' for n in got]), "client_id": NAME}).encode(), {"Content-Type": "application/json"})
        pid = json.load(urllib.request.urlopen(req, timeout=30))['prompt_id']
        last = time.time()
        while True:
            h = json.load(urllib.request.urlopen(f'{U}/history/{pid}', timeout=30))
            if pid in h:
                st = h[pid].get('status', {})
                if st.get('status_str') == 'error': raise RuntimeError(json.dumps(st)[:1500])
                break
            if time.time() - last > 10:
                for n in got:
                    try: os.utime(f'{mine}/{n}')
                    except OSError: pass
                last = time.time()
            time.sleep(0.3)
        for n in got:
            try: os.remove(f'{mine}/{n}')
            except OSError: pass
        log(ok=True, kind=kind, n=len(got), secs=round(time.time() - t0, 2)); errs = 0
    except Exception as e:      # noqa: BLE001
        give_back(); errs += 1
        log(ok=False, kind=kind, n=len(got), err=str(e)[:1500])
        if errs >= 5: break
        time.sleep(5)
give_back()
log(ok=True, kind='exit', n=0, secs=0)
