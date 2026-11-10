#!/usr/bin/env python3
"""밑그림의 한 영역(또는 전체)을 이음매 없이 다시 그린다: 공유 latent + 창별 예측 가중 평균(comfy_nodes/iso_md.py).

  python3 pipeline/seamless.py <guide_dir> <work_dir> <tag> [--rect x,y,w,h] [--scale 4] [--ov 128]
        [--grids 01010100] [--ramp 16] [--pow 1] [--seed 11] [--single] [--tiled]

--rect 는 밑그림 px(0.5 m/px) 단위. 생략하면 전체. --grids 는 스텝별 격자(0 = 기본, 1 = 반 칸 민 격자).
--single 은 창 하나짜리(기존 타일 방식과 같은 결과가 나오는지 확인용). 결과: <work_dir>/<tag>.png
"""
import argparse, json, math, os, subprocess, sys, time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from prompts import prompt_for  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
HOST = os.environ.get('GEN_SSH_HOST', 'genbox')
REMOTE = os.environ.get('GEN_REMOTE_DIR', '/srv/gen/redraw')
ap = argparse.ArgumentParser()
ap.add_argument('guide'); ap.add_argument('work'); ap.add_argument('tag')
ap.add_argument('--rect', default=''); ap.add_argument('--scale', type=int, default=4); ap.add_argument('--ov', type=int, default=128)
ap.add_argument('--tw', type=int, default=1408); ap.add_argument('--th', type=int, default=1024)
ap.add_argument('--grids', default='01010100'); ap.add_argument('--ramp', type=int, default=16); ap.add_argument('--pow', type=float, default=1.0)
ap.add_argument('--seed', type=int, default=11); ap.add_argument('--single', action='store_true'); ap.add_argument('--tiled', action='store_true')
ap.add_argument('--dump', action='store_true'); ap.add_argument('--dry', action='store_true')
a = ap.parse_args()
guide, work, S = Path(a.guide), Path(a.work), a.scale
work.mkdir(parents=True, exist_ok=True)
col = Image.open(guide / 'guide_color.png').convert('RGB')
cls = np.array(Image.open(guide / 'guide_classes.png'))
kinds = np.array(Image.open(guide / 'guide_kinds.png')) if (guide / 'guide_kinds.png').exists() else None
gx, gy, gw, gh = [int(v) for v in a.rect.split(',')] if a.rect else (0, 0, col.width, col.height)
col = col.crop((gx, gy, gx + gw, gy + gh)); cls = cls[gy:gy + gh, gx:gx + gw]
if kinds is not None: kinds = kinds[gy:gy + gh, gx:gx + gw]
W, H = gw * S, gh * S
assert W % 16 == 0 and H % 16 == 0, 'canvas must be a multiple of 16 px'
canvas = col.resize((W, H), Image.NEAREST)

def grid(total, size, ov):
    if total <= size: return [0]
    n = math.ceil((total - ov) / (size - ov)); step = (total - size) / (n - 1)
    return [int(round(i * step / 16)) * 16 for i in range(n)]

def shifted(base, total, size):
    if len(base) == 1: return [0]
    mids = [int(round((p + q) / 2 / 16)) * 16 for p, q in zip(base, base[1:])]
    return sorted(set([0] + mids + [total - size]))

xs0, ys0 = grid(W, a.tw, a.ov), grid(H, a.th, a.ov)
sets = {0: (xs0, ys0)}
if '1' in a.grids and not a.single: sets[1] = (shifted(xs0, W, a.tw), shifted(ys0, H, a.th))
wins = []
for g, (xs, ys) in sets.items():
    for y in ys:
        for x in xs:
            c = cls[y // S:(y + a.th) // S, x // S:(x + a.tw) // S]
            k = None if kinds is None else kinds[y // S:(y + a.th) // S, x // S:(x + a.tw) // S]
            skip = bool((c != 0).mean() <= 0.02)
            wins.append({'x': x, 'y': y, 'grid': g, 'skip': skip, 'prompt': '' if skip else prompt_for(c, k)})
grids = [int(ch) if int(ch) in sets else 0 for ch in a.grids]
spec = {'win': [a.tw, a.th], 'windows': wins, 'step_grids': grids, 'ramp': a.ramp, 'pow': a.pow}
if a.dump: spec['dump'] = f'{REMOTE}/out/{a.tag}'
n_calls = sum(sum(1 for w in wins if w['grid'] == g and not w['skip']) for g in grids)
print(f'canvas {W}x{H}, grids {[(len(v[0]), len(v[1])) for v in sets.values()]}, {len(wins)} windows ({sum(w["skip"] for w in wins)} empty), {n_calls} model calls')
json.dump({'rect': [gx, gy, gw, gh], 'scale': S, **spec}, open(work / f'{a.tag}_spec.json', 'w'))
if a.dry: raise SystemExit
canvas.save(work / f'{a.tag}_canvas.png')

def sh(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0: raise SystemExit(f"failed: {' '.join(cmd)[:300]}\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    return r.stdout

G = {
    "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_edit_2511_fp8mixed.safetensors", "weight_dtype": "default"}},
    "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors", "type": "qwen_image", "device": "default"}},
    "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
    "img": {"class_type": "LoadImage", "inputs": {"image": f'{a.tag}_canvas.png'}},
    "lora": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["unet", 0], "lora_name": "Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors", "strength_model": 1.0}},
    "ms": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["lora", 0], "shift": 3.1}},
    "cn": {"class_type": "CFGNorm", "inputs": {"model": ["ms", 0], "strength": 1.0}},
    "md": {"class_type": "IsoSeamlessSample", "inputs": {"model": ["cn", 0], "clip": ["clip", 0], "vae": ["vae", 0], "image": ["img", 0], "spec": json.dumps(spec),
                                                         "seed": a.seed, "steps": len(a.grids), "sampler_name": "euler", "scheduler": "simple"}},
    "dec": ({"class_type": "VAEDecodeTiled", "inputs": {"samples": ["md", 0], "vae": ["vae", 0], "tile_size": 1024, "overlap": 128, "temporal_size": 64, "temporal_overlap": 8}} if a.tiled
            else {"class_type": "VAEDecode", "inputs": {"samples": ["md", 0], "vae": ["vae", 0]}}),
    "keep": {"class_type": "SaveLatent", "inputs": {"samples": ["md", 0], "filename_prefix": f"latents/{a.tag}"}},
    "save": {"class_type": "SaveImage", "inputs": {"images": ["dec", 0], "filename_prefix": a.tag}},
}
gf = work / f'{a.tag}_graph.json'
json.dump({"prompt": G, "client_id": "iso-redraw"}, open(gf, 'w'))
sh('scp', '-q', str(work / f'{a.tag}_canvas.png'), f'{HOST}:{REMOTE}/in/')
sh('scp', '-q', str(gf), f'{HOST}:{REMOTE}/')
t0 = time.time()
runner = ("import json,time,urllib.request,sys\nU='http://127.0.0.1:8188'\n"
          f"d=open('{REMOTE}/{gf.name}','rb').read()\n"
          "try: pid=json.load(urllib.request.urlopen(urllib.request.Request(U+'/prompt',d,{'Content-Type':'application/json'})))['prompt_id']\n"
          "except urllib.error.HTTPError as e: sys.exit('rejected: '+e.read().decode()[:3000])\n"
          "t0=time.time()\n"
          "while True:\n"
          "    h=json.load(urllib.request.urlopen(U+'/history/'+pid))\n"
          "    if pid in h:\n"
          "        st=h[pid].get('status',{})\n"
          "        if st.get('status_str')=='error': sys.exit(json.dumps(st)[:4000])\n"
          "        print('done %.0fs'%(time.time()-t0)); break\n"
          "    time.sleep(3)\n")
print(sh('ssh', HOST, f"rm -f {REMOTE}/out/{a.tag}_0*.png; python3 - <<'PY'\n{runner}PY").strip(), f'(total {time.time() - t0:.0f}s)')
sh('scp', '-q', f'{HOST}:{REMOTE}/out/{a.tag}_00001_.png', str(work / f'{a.tag}.png'))
print('wrote', work / f'{a.tag}.png')
