#!/usr/bin/env python3
"""픽셀 스냅된 전체 그림과 밑그림의 깊이·클래스를 앱 자산 폴더에 넣는다.

  python3 pipeline/install.py <snap.png> <guide_dir> <app_assets_redraw_dir>

- 그림 범위 밖(클래스 0)은 한 가지 색으로 칠한다(타일마다 다르게 칠해진 빈 곳을 정리).
- bg.png  : 5504x3392 (0.25 m/px), 인덱스 PNG
- bg_1x.png: 2752x1696 (0.5 m/px), 같은 팔레트로 2x2 최빈색 축소
- classes.png, depth_rg8.png: 밑그림에서 복사
"""
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
snap, guide, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
im = Image.open(snap)
assert im.mode == 'P', 'snap.py 가 쓴 인덱스 PNG 여야 한다'
ix = np.array(im)
cls = np.array(Image.open(guide / 'guide_classes.png'))
f = ix.shape[0] // cls.shape[0]
empty = np.repeat(np.repeat(cls == 0, f, axis=0), f, axis=1)
fillc = np.bincount(ix[empty]).argmax()
ix[empty] = fillc
big = Image.fromarray(ix, 'P'); big.putpalette(im.getpalette())
big.save(out / 'bg.png', optimize=True)
# 2x2 블록에서 가장 많은 색(동률이면 어두운 쪽)
pal = np.array(im.getpalette()[:768], np.int32).reshape(-1, 3); lum = pal @ np.array([299, 587, 114])
h, w = ix.shape
b = ix.reshape(h // 2, 2, w // 2, 2).transpose(0, 2, 1, 3).reshape(h // 2, w // 2, 4)
bs = np.sort(b, axis=-1).astype(np.int16)
mode = np.where(bs[..., 1] == bs[..., 2], bs[..., 1], np.where(bs[..., 0] == bs[..., 1], bs[..., 0], np.where(bs[..., 2] == bs[..., 3], bs[..., 2], -1)))
dark = np.take_along_axis(b, lum[b].argmin(axis=-1)[..., None], axis=-1)[..., 0]
small = np.where(mode >= 0, mode, dark).astype(np.uint8)
sm = Image.fromarray(small, 'P'); sm.putpalette(im.getpalette())
sm.save(out / 'bg_1x.png', optimize=True)
shutil.copy(guide / 'guide_classes.png', out / 'classes.png')
shutil.copy(guide / 'depth_rg8.png', out / 'depth_rg8.png')
for n in ('bg.png', 'bg_1x.png', 'classes.png', 'depth_rg8.png'):
    print(n, (out / n).stat().st_size)
