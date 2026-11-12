#!/usr/bin/env python3
"""배경 그림 피라미드를 256×256 타일로 자른다 → assets/redraw/tiles/

단계(지도 px 0.5 m 당 그림 px 수 = z): z1 0.5 m, z2 0.25 m, z4 0.125 m, z8 0.0625 m. 모두 같은 카메라·같은 범위.
  z1.png              z1 전체(2752×1696). 뷰어가 시작할 때 통째로 올리는 바탕(항상 있음) → z1 은 타일을 따로 내지 않는다(--z1-tiles 로 낼 수 있음)
  z{2,4,8}_{x}_{y}.png 256 px 타일(가장자리는 작다). 팔레트(P) PNG 를 그대로 유지(재양자화·리샘플 없음)
  manifest.json       단계별 크기·격자, 건너뛴 단색 타일 목록과 색, 파일 형식, 총 용량

단색 타일(지도 밖 배경 등)은 파일을 쓰지 않고 manifest 의 solid 에 [x, y, 색 번호] 로 적는다(colors 에 RGB).
검사: 쓴 타일을 다시 읽어 원본 영역과 RGB 가 바이트 단위로 같은지(= 재조립 결과가 원본과 같음), 모든 칸이 파일이거나 단색으로 기록됐는지.

  python3 make_tiles.py --src work/full [--out assets/redraw/tiles] [--levels 1,2,4,8]
  python3 make_tiles.py --z1 a.png --z2 b.png --z4 c.png --z8 d.png
  --webp-levels 8      그 단계를 WebP 무손실로 쓴다(색 검사는 같다)
  --measure-webp       모든 타일을 WebP 무손실로도 인코딩해 보고 용량만 비교해 출력(파일은 PNG 로 둔다)
--src 에서는 단계마다 p05/p025/p0125/p0625 의 .png → _avg.png 순서로 찾는다.
"""
import argparse
import io
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
TILE = 256
NAMES = {1: 'p05', 2: 'p025', 4: 'p0125', 8: 'p0625'}

_im = None


def _init(path):
    global _im
    _im = Image.open(path)
    _im.load()


def _rgb_bytes(im):
    return im.convert('RGB').tobytes()


def _job(args):
    """한 줄(ty)의 타일을 쓰고 검사한다. → [(tx, ty, 'file'|'solid', 바이트 or 색, webp 바이트)]"""
    z, ty, nx, out, fmt, measure = args
    w, h = _im.size
    res = []
    for tx in range(nx):
        box = (tx * TILE, ty * TILE, min(w, (tx + 1) * TILE), min(h, (ty + 1) * TILE))
        t = _im.crop(box)
        cols = t.getcolors(1)
        if cols is not None:   # 한 색뿐
            c = cols[0][1]
            rgb = t.convert('RGB').getpixel((0, 0))
            res.append((tx, ty, 'solid', list(rgb), 0))
            continue
        name = f'z{z}_{tx}_{ty}.{fmt}'
        if fmt == 'png':
            t.save(out / name, optimize=True)
        else:
            t.convert('RGB').save(out / name, lossless=True, quality=100, method=6)
        back = Image.open(out / name)
        if _rgb_bytes(back) != _rgb_bytes(t):
            raise SystemExit(f'타일 검사 실패(색이 다름): {name}')
        wb = 0
        if measure and fmt == 'png':
            b = io.BytesIO()
            t.convert('RGB').save(b, 'WEBP', lossless=True, quality=100, method=6)
            if _rgb_bytes(Image.open(io.BytesIO(b.getvalue()))) != _rgb_bytes(t):
                raise SystemExit(f'WebP 무손실 왕복에서 색이 바뀜: {name}')
            wb = len(b.getvalue())
        res.append((tx, ty, 'file', (out / name).stat().st_size, wb))
    return res


def find_src(src, z):
    for n in (NAMES[z] + '.png', NAMES[z] + '_avg.png'):
        if (src / n).exists():
            return src / n
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src')
    for z in (1, 2, 4, 8):
        ap.add_argument(f'--z{z}')
    ap.add_argument('--out', default='assets/redraw/tiles')
    ap.add_argument('--levels', default='1,2,4,8')
    ap.add_argument('--z1-tiles', action='store_true')
    ap.add_argument('--webp-levels', default='')
    ap.add_argument('--measure-webp', action='store_true')
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 4)
    a = ap.parse_args()
    levels = [int(v) for v in a.levels.split(',') if v]
    webp = {int(v) for v in a.webp_levels.split(',') if v}
    srcs = {}
    for z in levels:
        p = getattr(a, f'z{z}')
        p = Path(p) if p else (find_src(Path(a.src), z) if a.src else None)
        if not p or not p.exists():
            sys.exit(f'z{z} 원본이 없습니다(--src 또는 --z{z})')
        srcs[z] = p
    if 1 not in srcs:
        sys.exit('z1(바탕) 이 필요합니다')
    base = Image.open(srcs[1])
    W, H = base.size
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in list(out.glob('z*_*_*.*')) + [out / 'z1.png', out / 'manifest.json']:
        if old.exists():
            old.unlink()
    base.save(out / 'z1.png', optimize=True)
    if _rgb_bytes(Image.open(out / 'z1.png')) != _rgb_bytes(base):
        sys.exit('z1.png 검사 실패')

    man = {'note': 'make_tiles.py 가 만든다. 지도 px(0.5 m) 당 그림 px = z. 단색 타일은 파일 없이 solid 에 [x, y, 색 번호].',
           'tile': TILE, 'map': [W, H], 'base': 'z1.png', 'levels': {}, 'colors': []}
    color_ix = {}
    total = {'files': 1, 'bytes': (out / 'z1.png').stat().st_size, 'webp_bytes': 0}
    for z in sorted(levels):
        if z == 1 and not a.z1_tiles:
            continue
        im = Image.open(srcs[z])
        w, h = im.size
        if (w, h) != (W * z, H * z):
            sys.exit(f'z{z} 크기가 {W * z}×{H * z} 가 아닙니다: {w}×{h}')
        if im.mode != 'P':
            print(f'경고: z{z} 가 팔레트 PNG 가 아닙니다({im.mode})', file=sys.stderr)
        nx, ny = -(-w // TILE), -(-h // TILE)
        fmt = 'webp' if z in webp else 'png'
        solid, nfile, nbytes, wbytes = [], 0, 0, 0
        with ProcessPoolExecutor(a.jobs, initializer=_init, initargs=(str(srcs[z]),)) as ex:
            for row in ex.map(_job, [(z, ty, nx, out, fmt, a.measure_webp) for ty in range(ny)]):
                for tx, ty, kind, v, wb in row:
                    if kind == 'solid':
                        k = tuple(v)
                        if k not in color_ix:
                            color_ix[k] = len(man['colors'])
                            man['colors'].append(v)
                        solid.append([tx, ty, color_ix[k]])
                    else:
                        nfile += 1
                        nbytes += v
                        wbytes += wb
        if nfile + len(solid) != nx * ny:
            sys.exit(f'z{z}: 빠진 칸이 있습니다')
        man['levels'][str(z)] = {'size': [w, h], 'grid': [nx, ny], 'format': fmt, 'files': nfile, 'bytes': nbytes, 'solid': solid}
        total['files'] += nfile
        total['bytes'] += nbytes
        total['webp_bytes'] += wbytes
        extra = f', WebP 무손실이면 {wbytes / 1e6:.1f} MB' if wbytes else ''
        print(f'z{z}: {nx}×{ny} 칸, 파일 {nfile}, 단색 {len(solid)}, {nbytes / 1e6:.1f} MB ({fmt}){extra}')
    man['total'] = {'files': total['files'], 'bytes': total['bytes']}
    (out / 'manifest.json').write_text(json.dumps(man, separators=(',', ':')) + '\n')
    print(f'합계: 파일 {total["files"]}(z1.png 포함), {total["bytes"] / 1e6:.1f} MB → {out}')


if __name__ == '__main__':
    main()
