#!/usr/bin/env python3
"""생성된 타일의 색을 클래스별로 맞춘 뒤(타일마다 톤이 달라 조각보처럼 보이는 것을 줄인다) 이어 붙인다.

  python3 pipeline/finish.py <guide_dir> <work_dir> <tag> [--amount 0.8] [--colors 0]

각 타일에서 클래스(도로·잔디·건물 지붕 등)별 평균색을 구하고, 전체 타일의 중앙값 쪽으로 평균만 옮긴다(무늬·명암은 그대로).
--colors N 을 주면 전체 그림에서 뽑은 N색 팔레트로 양자화한다(디더 없음).
결과: <work_dir>/<tag>_final.png
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ap = argparse.ArgumentParser()
ap.add_argument('guide'); ap.add_argument('work'); ap.add_argument('tag')
ap.add_argument('--amount', type=float, default=0.8); ap.add_argument('--colors', type=int, default=0); ap.add_argument('--scale', type=int, default=2)
a = ap.parse_args()
guide, work = Path(a.guide), Path(a.work)
meta = json.load(open(work / 'in' / f'{a.tag}_tiles.json'))
cls = np.array(Image.open(guide / 'guide_classes.png'))
S, tw, th = a.scale, meta['tw'], meta['th']
KS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

def up(c):
    return np.repeat(np.repeat(c, S, axis=0), S, axis=1)

tiles = []
for t in meta['tiles']:
    f = sorted((work / 'gen').glob(f"{a.tag}_r{t['r']}c{t['c']}_*.png"))[-1]
    im = np.asarray(Image.open(f).convert('RGB').resize((tw, th), Image.LANCZOS), np.float64)
    c = up(cls[t['y'] // S:(t['y'] + th) // S, t['x'] // S:(t['x'] + tw) // S])
    means = {k: im[c == k].mean(axis=0) for k in KS if (c == k).sum() > 4000}
    tiles.append((t, im, c, means))

target = {}
for k in KS:
    ms = [m[k] for _, _, _, m in tiles if k in m]
    if ms: target[k] = np.median(np.array(ms), axis=0)
print('target', {k: v.round().tolist() for k, v in target.items()})

out = work / 'gen_h'; out.mkdir(exist_ok=True)
for t, im, c, means in tiles:
    for k, m in means.items():
        d = (target[k] - m) * a.amount
        if np.abs(d).max() < 1.5: continue
        im[c == k] += d
    Image.fromarray(np.clip(im, 0, 255).astype(np.uint8)).save(out / f"{a.tag}_r{t['r']}c{t['c']}_00001_.png")

final = work / f'{a.tag}_final.png'
r = subprocess.run([sys.executable, str(Path(__file__).parent / 'tiles.py'), 'merge', str(work / 'in' / f'{a.tag}_tiles.json'), str(out), a.tag, str(final)], capture_output=True, text=True)
print(r.stdout, r.stderr)
if a.colors:
    im = Image.open(final).convert('RGB')
    pal = im.resize((im.width // 4, im.height // 4), Image.BOX).quantize(colors=a.colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE, kmeans=3)
    im.quantize(palette=pal, dither=Image.Dither.NONE).convert('RGB').save(final, optimize=True)
    print('quantized to', a.colors)
