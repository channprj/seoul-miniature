#!/usr/bin/env python3
"""다시 그린 그림(0.25 m/px, 부드러운 가장자리)을 진짜 픽셀 격자로 스냅한다.

  python3 pipeline/snap.py <in.png> <out.png> [--colors 64] [--block 2]

1) 전체 그림에서 뽑은 N색 팔레트로 양자화(디더 없음)  2) block×block 칸마다 가장 많은 색 하나로 채운다(동률이면 어두운 색 → 윤곽선 유지).
결과는 (W/block)×(H/block) 인덱스 PNG. block=2 이면 지도 px(0.5 m)와 1:1 이라 사람·차 스프라이트와 픽셀 크기가 같다.
"""
import argparse
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('out'); ap.add_argument('--colors', type=int, default=64); ap.add_argument('--block', type=int, default=2)
a = ap.parse_args()
im = Image.open(a.src).convert('RGB')
B = a.block
pal_img = im.resize((im.width // 4, im.height // 4), Image.BOX).quantize(colors=a.colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE, kmeans=4)
q = im.quantize(palette=pal_img, dither=Image.Dither.NONE)
idx = np.asarray(q)
pal = np.array(q.getpalette()[:a.colors * 3], np.float64).reshape(-1, 3)
lum = pal @ np.array([0.299, 0.587, 0.114])
H, W = idx.shape[0] // B * B, idx.shape[1] // B * B
blk = idx[:H, :W].reshape(H // B, B, W // B, B).transpose(0, 2, 1, 3).reshape(H // B, W // B, B * B)
# 칸 안에서 색별 득표 수 − 밝기 가산(동률 깨기)
score = np.zeros(blk.shape, np.float64)
for i in range(B * B):
    score[..., i] = (blk == blk[..., i:i + 1]).sum(axis=-1) - lum[blk[..., i]] / 1000.0
pick = np.take_along_axis(blk, score.argmax(axis=-1)[..., None], axis=-1)[..., 0]
out = Image.fromarray(pick.astype(np.uint8), 'P'); out.putpalette(q.getpalette())
out.save(a.out, optimize=True)
print('wrote', a.out, out.size, 'colors', len(np.unique(pick)))
