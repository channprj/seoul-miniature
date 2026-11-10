#!/usr/bin/env python3
"""이어 붙인 전체 그림을 창 단위로 색 검사한다(run_tiles.py 의 타일 검사와 같은 규칙).

  python3 pipeline/qa_full.py <guide_dir> <full.png> [--scale 4]
"""
import argparse, math
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

Image.MAX_IMAGE_PIXELS = None
ap = argparse.ArgumentParser(); ap.add_argument('guide'); ap.add_argument('full'); ap.add_argument('--scale', type=int, default=4)
a = ap.parse_args()
S = a.scale
cls = np.array(Image.open(Path(a.guide) / 'guide_classes.png'))
full = Image.open(a.full).convert('RGB')
small = np.asarray(full.resize((cls.shape[1], cls.shape[0]), Image.BOX), np.float64)
gw, gh = 1408 // S, 1024 // S

def qa(c, im):
    bad = []
    def mean(k):
        mk = c == k
        return im[mk].mean(axis=0) if mk.sum() > 400 else None
    r = mean(2)
    if r is not None and (r[2] - r[0] > 22 or r.max() - r.min() > 45 or r.mean() > 150): bad.append(f'road colour {r.round()}')
    w = mean(4)
    if w is not None and w[2] - w[0] < 20: bad.append(f'water colour {w.round()}')
    g = mean(3)
    if g is not None and not (g[1] > g[0] + 8 and g[1] > g[2] + 8): bad.append(f'lawn colour {g.round()}')
    e = mean(0)
    if e is not None and (e.max() - e.min() > 60): bad.append(f'empty background painted {e.round()}')
    wd = np.asarray(Image.fromarray(((c == 4) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))) > 0
    blue = (im[..., 2] - im[..., 0] > 55) & (im[..., 2] > 130) & (im[..., 1] > 90)
    frac = (blue & ~(wd | (c == 0) | (c == 6) | (c == 7))).sum() / c.size
    if frac > 0.008: bad.append(f'invented water {frac:.3f}')
    return bad

H, W = cls.shape
nx, ny = math.ceil(W / gw), math.ceil(H / gh)
fails = 0
for j in range(ny):
    for i in range(nx):
        x, y = min(i * gw, W - gw), min(j * gh, H - gh)
        c = cls[y:y + gh, x:x + gw]
        if (c != 0).mean() <= 0.02: continue
        bad = qa(c, small[y:y + gh, x:x + gw])
        if bad: fails += 1; print(f'window guide ({x},{y}): {bad}')
print(f'{nx * ny} windows checked, {fails} failed')
