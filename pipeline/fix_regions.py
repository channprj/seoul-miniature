#!/usr/bin/env python3
"""지정한 곳만 다시 그려 전체 그림에 합성한다(landmarks.py 와 같은 방식, 대상은 JSON 으로 준다).

  python3 pipeline/fix_regions.py <guide_dir> <work_dir> <targets.json> <full_in.png> <full_out.png> [--seed 5] [--reuse]

targets.json = [{"key": "ticket", "ids": [1103], "zoom": 0.5, "desc": "..."},                       # 그 건물 픽셀만 교체
                {"key": "lawn", "rect": [x0, y0, x1, y1], "zoom": 1, "desc": "...", "ground": true}]  # rect 안의 건물 아닌 픽셀만 교체
좌표는 밑그림 px. 밑그림은 읽기만 한다.
"""
import argparse, json, os, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
from prompts import prompt_for, HEAD  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
HOST = os.environ.get('GEN_SSH_HOST', 'genbox'); REMOTE = os.environ.get('GEN_REMOTE_DIR', '/srv/gen/redraw')
TW, TH, S = 1408, 1024, 4
ap = argparse.ArgumentParser()
ap.add_argument('guide'); ap.add_argument('work'); ap.add_argument('targets'); ap.add_argument('full_in'); ap.add_argument('full_out')
ap.add_argument('--seed', type=int, default=5); ap.add_argument('--reuse', action='store_true'); ap.add_argument('--tag', default='fx')
ap.add_argument('--up', type=int, default=14); ap.add_argument('--grow', type=int, default=5)
a = ap.parse_args()
guide, work = Path(a.guide), Path(a.work)
(work / 'in').mkdir(parents=True, exist_ok=True); (work / 'gen').mkdir(exist_ok=True)
T = json.load(open(a.targets))
gcol = Image.open(guide / 'guide_color.png').convert('RGB')
cls = np.array(Image.open(guide / 'guide_classes.png')); kinds = np.array(Image.open(guide / 'guide_kinds.png')); bid = np.array(Image.open(guide / 'guide_bid.png'))
H, W = cls.shape

def sh(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0: raise SystemExit(f"failed: {' '.join(cmd)[:300]}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r.stdout

jobs = []
for t in T:
    if 'ids' in t:
        ys, xs = np.where(np.isin(bid, t['ids']) & (cls >= 6) & (cls <= 9))
        bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max(), ys.max()
    else:
        bx0, by0, bx1, by1 = t['rect']
    k = t.get('zoom', 1)
    cw, ch = int(TW // S * k), int(TH // S * k)
    x0 = int(min(max(0, round((bx0 + bx1) / 2 - cw / 2)), W - cw)); y0 = int(min(max(0, round((by0 + by1) / 2 - ch / 2)), H - ch))
    t['win'] = (x0, y0, cw, ch)
    name = f"{a.tag}_{t['key']}"
    gcol.crop((x0, y0, x0 + cw, y0 + ch)).resize((TW, TH), Image.NEAREST).save(work / 'in' / f'{name}.png')
    base = prompt_for(cls[y0:y0 + ch, x0:x0 + cw], kinds[y0:y0 + ch, x0:x0 + cw])
    jobs.append({'name': name, 'image': f'{name}.png', 'seed': t.get('seed', a.seed), 'steps': 8, 'prompt': HEAD + t['desc'] + ' ' + base[len(HEAD):]})
jf = work / f'{a.tag}_jobs.json'
json.dump(jobs, open(jf, 'w'), indent=1)
if not a.reuse:
    sh('scp', '-q', *[str(work / 'in' / j['image']) for j in jobs], f'{HOST}:{REMOTE}/in/')
    sh('scp', '-q', str(jf), f'{HOST}:{REMOTE}/')
    print(sh('ssh', HOST, f"cd {REMOTE} && rm -f " + ' '.join(f"out/{j['name']}_0*.png" for j in jobs) + f" && python3 gen_run.py {jf.name}"))
    sh('scp', '-q', *[f"{HOST}:{REMOTE}/out/{j['name']}_00001_.png" for j in jobs], str(work / 'gen') + '/')

full = np.asarray(Image.open(a.full_in).convert('RGB'), np.float32).copy()
for t in T:
    x0, y0, cw, ch = t['win']
    Wk, Hk = cw * S, ch * S
    gen = np.asarray(Image.open(work / 'gen' / f"{a.tag}_{t['key']}_00001_.png").convert('RGB').resize((Wk, Hk), Image.LANCZOS), np.float32)
    c, b = cls[y0:y0 + ch, x0:x0 + cw], bid[y0:y0 + ch, x0:x0 + cw]
    cu = np.repeat(np.repeat(c, S, axis=0), S, axis=1)
    ys, xs = y0 * S, x0 * S
    base = full[ys:ys + Hk, xs:xs + Wk]
    for kc in (1, 2, 3, 5, 11):                      # 바탕과 평균색 맞춤
        w = cu == kc
        if w.sum() > 3000: gen[w] += base[w].mean(axis=0) - gen[w].mean(axis=0)
    if t.get('ground'):
        rx0, ry0, rx1, ry1 = t['rect']
        mk = np.zeros((ch, cw), bool); mk[max(0, ry0 - y0):ry1 - y0, max(0, rx0 - x0):rx1 - x0] = True
        mk &= ~((c >= 6) & (c <= 9)) & (c != 2)
        blur = S * 3
    else:
        mk = np.isin(b, t['ids']) & (c >= 6) & (c <= 9)
        m0 = mk.copy()
        for d in range(1, t.get('up', a.up) + 1): mk[:-d] |= m0[d:]
        mk = np.asarray(Image.fromarray((mk * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * a.grow + 1))) > 0
        blur = S * 1.5
    al = np.asarray(Image.fromarray((mk * 255).astype(np.uint8)).resize((Wk, Hk), Image.NEAREST).filter(ImageFilter.GaussianBlur(blur)), np.float32)[..., None] / 255.0
    edge = np.ones((Hk, Wk), np.float32); e = 24
    edge[:e] = edge[-e:] = 0; edge[:, :e] = edge[:, -e:] = 0
    al *= edge[..., None]
    full[ys:ys + Hk, xs:xs + Wk] = base * (1 - al) + gen * al
Image.fromarray(np.clip(full, 0, 255).astype(np.uint8)).save(a.full_out)
print('wrote', a.full_out)
