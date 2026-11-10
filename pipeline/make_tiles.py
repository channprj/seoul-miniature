#!/usr/bin/env python3
"""bg.png(5504×3392, 0.25 m/px)를 256×256 타일로 자른다 → assets/redraw/tiles/z2_<x>_<y>.png

휴대폰 경로(절반 해상도 그림)가 확대했을 때 보이는 칸만 원본 해상도로 받아 오는 데 쓴다(app/src/bgtiles.js).
- 팔레트(P 모드) PNG 를 그대로 유지한다. 재양자화·리샘플 없음 → 픽셀이 bg.png 와 바이트 단위로 같다.
- 가장자리 타일은 256 보다 작다(그림 크기 그대로).
- 'z2' = 지도 px 당 2 그림 px.

  python3 pipeline/make_tiles.py [assets/redraw/bg.png] [assets/redraw/tiles]
"""
import sys
from pathlib import Path

from PIL import Image

TILE = 256


def main():
    src = Path(sys.argv[1] if len(sys.argv) > 1 else 'assets/redraw/bg.png')
    out = Path(sys.argv[2] if len(sys.argv) > 2 else 'assets/redraw/tiles')
    im = Image.open(src)
    im.load()
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob('z2_*.png'):
        old.unlink()
    w, h = im.size
    nx, ny = -(-w // TILE), -(-h // TILE)
    n = 0
    for ty in range(ny):
        for tx in range(nx):
            box = (tx * TILE, ty * TILE, min(w, (tx + 1) * TILE), min(h, (ty + 1) * TILE))
            im.crop(box).save(out / f'z2_{tx}_{ty}.png', optimize=True)
            n += 1
    # 검사: 다시 붙여서 원본과 같아야 한다
    chk = Image.new(im.mode, im.size)
    if im.mode == 'P':
        chk.putpalette(im.getpalette())
    for ty in range(ny):
        for tx in range(nx):
            chk.paste(Image.open(out / f'z2_{tx}_{ty}.png'), (tx * TILE, ty * TILE))
    a, b = im.convert('RGB').tobytes(), chk.convert('RGB').tobytes()
    if a != b:
        sys.exit('타일을 다시 붙인 결과가 원본과 다릅니다')
    size = sum(f.stat().st_size for f in out.glob('z2_*.png'))
    print(f'{n} 타일 ({nx}×{ny}, {TILE} px), {size / 1e6:.1f} MB, 모드 {im.mode} → {out}')


if __name__ == '__main__':
    main()
