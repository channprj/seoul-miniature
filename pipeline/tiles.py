#!/usr/bin/env python3
"""밑그림을 겹치는 타일로 자르고(split), 생성 결과를 다시 이어 붙인다(merge).

독립 타일은 이음새가 보여 실패한 적이 있다. 여기서는 모든 타일이 같은 밑그림(위치·색이 고정된 블록아웃)과
같은 전역 초안(init)을 조건으로 받고, 넓은 겹침을 가중 평균한다.

  split: python3 tiles.py split <src.png> <outdir> <prefix> [--scale 2] [--tw 1408] [--th 1024] [--ov 224] [--resample nearest|lanczos]
  merge: python3 tiles.py merge <tiles.json> <generated_dir> <gen_prefix> <out.png>
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def grid(total, size, ov):
    if total <= size:
        return [0]
    n = math.ceil((total - ov) / (size - ov))
    step = (total - size) / (n - 1)
    return [round(i * step) for i in range(n)]


def split(a):
    src = Image.open(a.src).convert('RGB')
    rs = Image.NEAREST if a.resample == 'nearest' else Image.LANCZOS
    big = src.resize((src.width * a.scale, src.height * a.scale), rs) if a.scale != 1 else src
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    xs, ys = grid(big.width, a.tw, a.ov), grid(big.height, a.th, a.ov)
    tiles = []
    for r, y in enumerate(ys):
        for c, x in enumerate(xs):
            t = big.crop((x, y, x + a.tw, y + a.th))
            name = f'{a.prefix}_r{r}c{c}.png'
            t.save(out / name)
            tiles.append({'r': r, 'c': c, 'x': x, 'y': y, 'file': name})
    meta = {'W': big.width, 'H': big.height, 'tw': a.tw, 'th': a.th, 'ov': a.ov, 'tiles': tiles}
    json.dump(meta, open(out / f'{a.prefix}_tiles.json', 'w'), indent=1)
    print(f'{len(tiles)} tiles ({len(ys)}x{len(xs)}) of {a.tw}x{a.th} from {big.size}')


def merge(a):
    meta = json.load(open(a.tiles))
    W, H, tw, th, ov = meta['W'], meta['H'], meta['tw'], meta['th'], meta['ov']
    acc = np.zeros((H, W, 3), np.float64)
    wsum = np.zeros((H, W, 1), np.float64)
    # 가장자리로 갈수록 0 에 가까워지는 가중치(겹침 폭만큼 선형 램프)
    def ramp(n):
        # 겹침 한가운데의 좁은 띠(fw px)에서만 섞는다. 겹침 전체를 섞으면 서로 다른 디테일이 겹쳐 유령상이 생긴다.
        r = np.ones(n)
        fw = min(a.feather, ov)
        k = np.full(ov, 1e-4); lo = (ov - fw) // 2
        k[lo:lo + fw] = np.linspace(0, 1, fw + 2)[1:-1]; k[lo + fw:] = 1
        r[:ov] = k; r[-ov:] = k[::-1]
        return r
    w2 = (ramp(th)[:, None] * ramp(tw)[None, :])[..., None]
    gen = Path(a.gendir)
    for t in meta['tiles']:
        cands = sorted(gen.glob(f"{a.genprefix}_r{t['r']}c{t['c']}_*.png"))
        if not cands:
            raise SystemExit(f"missing tile r{t['r']}c{t['c']}")
        im = Image.open(cands[-1]).convert('RGB')
        if im.size != (tw, th):
            im = im.resize((tw, th), Image.LANCZOS)
        y, x = t['y'], t['x']
        acc[y:y + th, x:x + tw] += np.asarray(im, np.float64) * w2
        wsum[y:y + th, x:x + tw] += w2
    out = np.clip(acc / np.maximum(wsum, 1e-6), 0, 255).astype(np.uint8)
    Image.fromarray(out).save(a.out)
    print('wrote', a.out, out.shape)


p = argparse.ArgumentParser()
sub = p.add_subparsers(dest='cmd', required=True)
s = sub.add_parser('split')
s.add_argument('src'); s.add_argument('outdir'); s.add_argument('prefix')
s.add_argument('--scale', type=int, default=2); s.add_argument('--tw', type=int, default=1408); s.add_argument('--th', type=int, default=1024)
s.add_argument('--ov', type=int, default=224); s.add_argument('--resample', default='nearest')
m = sub.add_parser('merge')
m.add_argument('tiles'); m.add_argument('gendir'); m.add_argument('genprefix'); m.add_argument('out')
m.add_argument('--feather', type=int, default=8)
a = p.parse_args()
split(a) if a.cmd == 'split' else merge(a)
