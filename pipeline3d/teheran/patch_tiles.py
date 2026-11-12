#!/usr/bin/env python3
"""테헤란로 부분 굽기: 장면을 고친 타일만 다시 렌더해, 달라진 자리만 앱 자산(assets/teheran/)에 덧입힌다.

전체 굽기(build_assets_th.py)는 64타일 조건 렌더가 다 있어야 하고 팔레트를 새로 뽑아 타일 6천 장이 모두 바뀐다. 한 구역만 고칠 때는
  - 고치기 전 코드·장면으로 렌더한 타일(--base)과 고친 뒤 타일(--new)을 견주어 달라진 화소만 가려내고(ID·깊이가 다르거나, 색이 뭉쳐서 다른 곳 + 둘레 여유),
  - 그 화소만 지금 자산의 팔레트(128색, 그대로 둠)로 양자화해 z8 타일에 넣고, 아래 단계(z4·z2·z1, bg.png, bg_1x.png)는 그 화소가 든 칸만 다시 줄이고,
  - 깊이·분류·수관 맵은 전체 굽기의 step_maps 를 그대로 돌리되(다시 렌더하지 않은 곳은 빈 값) 달라진 칸만 옮긴다.
두 렌더는 같은 OSM 자료·같은 표본 수여야 한다(나무·건물 모양이 장면 순번·ID 로 정해진다). 순서는 patch.sh.

  python patch_tiles.py --base base --new new --tiles 6_1 --assets ../../assets/teheran [--landmark 'key|이름|종류|x,y,z'] [--manifest ../../assets.manifest.json]
  (작업 폴더에서. new/ 에는 그 타일의 classes_05m.png 가 있어야 한다: YD_TILES=6_1 … make_classes_ydF.py)
"""
import argparse, hashlib, json, sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as nd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'yeouido'))
import build_assets_yd as yd

Image.MAX_IMAGE_PIXELS = None
TW, TH, TILE = 2752, 1696, 256


def rgb(p): return np.asarray(Image.open(p).convert('RGB'))
def rg16(p): a = rgb(p); return a[..., 0].astype(np.uint16) * 256 + a[..., 1]


def change_mask(a, i, j):
    """고치기 전·후 타일에서 달라진 화소. ID·깊이는 표본 1개 렌더라 잡음이 없다 → 다르면 다 넣는다.
    색만 다른 곳(새 물체의 그림자, 바뀐 지면 그림)은 렌더 잡음과 섞여 있어, 둘레 11 px 안에서 35 % 넘게 다른 뭉치만 넣는다."""
    b, n = (f'{d}/t_{i}_{j}' for d in (a.base, a.new))
    geo = (rg16(b + '_id.png') != rg16(n + '_id.png')) | (np.abs(rg16(b + '_z.png').astype(np.int32) - rg16(n + '_z.png').astype(np.int32)) > 1)
    col = np.abs(rgb(b + '.png').astype(np.int16) - rgb(n + '.png').astype(np.int16)).sum(-1) > a.thr
    m = geo | (nd.uniform_filter(col.astype(np.float32), 11) > .35)
    m = nd.binary_fill_holes(nd.binary_dilation(m, iterations=a.grow))
    edge = int(m[0].sum() + m[-1].sum() + m[:, 0].sum() + m[:, -1].sum())
    yd.log(f'tile {i}_{j}: changed {m.mean() * 100:.2f} % (geometry {geo.mean() * 100:.2f} %), on tile border {edge} px')
    return m, edge


def tile_grid(z):
    return -(-yd.W * z // 8 // TILE), -(-yd.H * z // 8 // TILE)


def read_level(tiles, z, x0, y0, x1, y1, pal):
    """단계 z 의 창(그 단계 px, 타일 경계에 맞춘 것)을 색 번호 배열로."""
    out = np.zeros((y1 - y0, x1 - x0), np.uint8)
    for ty in range(y0 // TILE, -(-y1 // TILE)):
        for tx in range(x0 // TILE, -(-x1 // TILE)):
            im = Image.open(tiles / f'z{z}_{tx}_{ty}.png')
            assert im.mode == 'P' and im.getpalette()[:len(pal)] == pal, f'z{z}_{tx}_{ty}: 팔레트가 다르다'
            t = np.asarray(im)
            out[ty * TILE - y0:ty * TILE - y0 + t.shape[0], tx * TILE - x0:tx * TILE - x0 + t.shape[1]] = t
    return out


def write_level(tiles, z, x0, y0, ix, old, pal, changed):
    n = 0
    for ty in range(y0 // TILE, -(-(y0 + ix.shape[0]) // TILE)):
        for tx in range(x0 // TILE, -(-(x0 + ix.shape[1]) // TILE)):
            sl = np.s_[ty * TILE - y0:(ty + 1) * TILE - y0, tx * TILE - x0:(tx + 1) * TILE - x0]
            if np.array_equal(ix[sl], old[sl]): continue
            t = Image.fromarray(ix[sl], 'P'); t.putpalette(pal); p = tiles / f'z{z}_{tx}_{ty}.png'; t.save(p, optimize=True); changed.append(p); n += 1
    return n


def patch_art(a, mask, bbox, cond):
    A = Path(a.assets); tiles = A / 'tiles'; changed = []
    z1 = Image.open(tiles / 'z1.png'); pal = z1.getpalette()[:768]; Pf = np.array(pal, np.float32).reshape(-1, 3)
    S_ = 8 * TILE   # z1 타일 한 장이 덮는 z8 px. 창을 여기에 맞추면 모든 단계에서 타일 경계에 떨어진다
    x0, y0, x1, y1 = bbox[0] // S_ * S_, bbox[1] // S_ * S_, min(yd.W, -(-bbox[2] // S_) * S_), min(yd.H, -(-bbox[3] // S_) * S_)
    m8 = np.asarray(mask[y0:y1, x0:x1]); old8 = read_level(tiles, 8, x0, y0, x1, y1, pal)
    yd._qinit(pal + [0] * (768 - len(pal))); new8 = yd._quant_strip(np.ascontiguousarray(cond[y0:y1, x0:x1]))
    ix8 = np.where(m8, new8, old8); n = write_level(tiles, 8, x0, y0, ix8, old8, pal, changed)
    err = np.sqrt(((Pf[new8[m8]] - np.asarray(cond[y0:y1, x0:x1])[m8].astype(np.float32)) ** 2).sum(-1))
    yd.log(f'z8: {int(m8.sum())} px patched, {n} tiles, palette error mean {err.mean():.1f} p95 {np.percentile(err, 95):.1f}')
    h, w = ix8.shape; full = {}
    for z, f in ((4, 2), (2, 4), (1, 8)):   # step_quant 과 같은 축소: 양자화한 z8 의 f×f 평균 → 같은 팔레트. 달라진 화소가 든 칸만 바꾼다
        hh, ww = h // f * f, w // f * f   # 판 아래·오른쪽 끝의 자투리는 없다(22016·13568 은 8 의 배수)
        q = yd._quant_strip(Pf[ix8[:hh, :ww]].reshape(hh // f, f, ww // f, f, 3).mean((1, 3)).round().astype(np.uint8))
        mf = m8[:hh, :ww].reshape(hh // f, f, ww // f, f).any((1, 3)); X0, Y0 = x0 // f, y0 // f
        if z == 1:
            old = np.asarray(z1)[Y0:Y0 + hh // f, X0:X0 + ww // f]; ix = np.where(mf, q, old); arr = np.asarray(z1).copy(); arr[Y0:Y0 + hh // f, X0:X0 + ww // f] = ix
            for p in (tiles / 'z1.png', A / 'bg_1x.png'): yd.save_p(arr, pal, p); changed.append(p)
        else:
            old = read_level(tiles, z, X0, Y0, X0 + ww // f, Y0 + hh // f, pal); ix = np.where(mf, q, old); n = write_level(tiles, z, X0, Y0, ix, old, pal, changed)
            full[z] = (X0, Y0, ix)
        yd.log(f'z{z}: {int((ix != old).sum())} px changed' + (f', {n} tiles' if z != 1 else ''))
    bg = Image.open(A / 'bg.png'); assert bg.mode == 'P' and bg.getpalette()[:768] == pal; arr = np.asarray(bg).copy()   # bg.png = z2 한 장
    X0, Y0, ix = full[2]; arr[Y0:Y0 + ix.shape[0], X0:X0 + ix.shape[1]] = ix; yd.save_p(arr, pal, A / 'bg.png'); changed.append(A / 'bg.png')
    mf = json.loads((tiles / 'manifest.json').read_text())
    for z, lv in mf['levels'].items(): lv['bytes'] = sum(p.stat().st_size for p in tiles.glob(f'z{z}_*.png'))
    mf['total'] = {'files': sum(lv['files'] for lv in mf['levels'].values()) + 1, 'bytes': sum(lv['bytes'] for lv in mf['levels'].values()) + (tiles / 'z1.png').stat().st_size}
    (tiles / 'manifest.json').write_text(json.dumps(mf, ensure_ascii=False, separators=(',', ':')) + '\n'); changed.append(tiles / 'manifest.json')
    return changed


def patch_maps(a, mask):
    """전체 굽기의 step_maps 를 다시 렌더한 타일만 채운 캐시로 돌리고, 달라진 화소가 든 지도 칸만 자산에 옮긴다."""
    A = Path(a.assets); W_ = Path(a.work); yd.step_maps(a)
    cell = np.asarray(mask).reshape(yd.MH, yd.F, yd.MW, yd.F).any((1, 3)); changed = []
    for n in ('depth_rg8.png', 'classes.png', 'crown.png'):
        old = np.asarray(Image.open(A / n)); new = np.asarray(Image.open(W_ / n)); out = old.copy(); out[cell] = new[cell]
        yd.log(n, int((out != old).reshape(yd.MH, yd.MW, -1).any(-1).sum()), 'cells changed of', int(cell.sum()))
        Image.fromarray(out, Image.open(A / n).mode).save(A / n, optimize=True); changed.append(A / n)
    return changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', required=True, help='고치기 전 코드·장면으로 렌더한 타일 폴더')
    ap.add_argument('--new', required=True, help='고친 뒤 타일 폴더(+ classes_05m.png)')
    ap.add_argument('--tiles', required=True, help='다시 렌더한 타일 i_j 쉼표 목록')
    ap.add_argument('--assets', required=True)
    ap.add_argument('--work', default='patch')
    ap.add_argument('--scene', default='scene.json')
    ap.add_argument('--thr', type=int, default=30, help='색 차이(세 채널 절댓값 합) 문턱')
    ap.add_argument('--grow', type=int, default=6, help='달라진 자리 둘레 여유(px)')
    ap.add_argument('--landmark', action='append', default=[], help="map.json 에 더할 자리 'key|이름|종류|x,y,z'(장면 좌표 m)")
    ap.add_argument('--manifest', help='assets.manifest.json: 바뀐 파일의 sha256 을 고친다')
    ap.add_argument('--check-only', action='store_true', help='달라진 범위만 보고 자산은 건드리지 않는다')
    a = ap.parse_args()
    tl = [tuple(map(int, t.split('_'))) for t in a.tiles.split(',')]
    C = Path(a.work) / 'cache'; C.mkdir(parents=True, exist_ok=True)
    meta = None; ids = {}; edges = 0
    arrs = {n: np.lib.format.open_memmap(C / f'{n}.npy', 'w+', dt, shp) for n, dt, shp in (('cond', np.uint8, (yd.H, yd.W, 3)), ('ids', np.uint16, (yd.H, yd.W)), ('v', np.uint16, (yd.H, yd.W)), ('mask', np.bool_, (yd.H, yd.W)))}
    for i, j in tl:
        t = f'{a.new}/t_{i}_{j}'; m = json.load(open(t + '_meta.json')); mb = json.load(open(f'{a.base}/t_{i}_{j}_meta.json'))
        assert m['depth']['z0'] == mb['depth']['z0'] and m['render_px_m'] == mb['render_px_m'] and m['size'] == [TW, TH], '두 렌더의 판·깊이 기준이 다르다'
        if meta is None: meta = m
        ids.update(m['ids']); sl = np.s_[j * TH:(j + 1) * TH, i * TW:(i + 1) * TW]
        arrs['cond'][sl] = rgb(t + '.png'); arrs['ids'][sl] = rg16(t + '_id.png'); arrs['v'][sl] = rg16(t + '_z.png'); arrs['mask'][sl], e = change_mask(a, i, j); edges += e
    mask = arrs['mask']; ys = np.nonzero(mask.any(1))[0]; xs = np.nonzero(mask.any(0))[0]
    if not len(ys): sys.exit('달라진 화소가 없다')
    bbox = [int(xs[0]), int(ys[0]), int(xs[-1]) + 1, int(ys[-1]) + 1]; yd.log('changed bbox (art px)', bbox, 'tiles', sorted({(x // TW, y // TH) for x in bbox[::2] for y in bbox[1::2]}))
    if edges: yd.log(f'경고: 달라진 화소 {edges} px 가 타일 가장자리에 닿는다 → 이웃 타일도 다시 렌더해 --tiles 에 넣을 것')
    Image.fromarray(np.asarray(mask[bbox[1]:bbox[3], bbox[0]:bbox[2]]).astype(np.uint8) * 255).save(Path(a.work) / 'mask.png')
    if a.check_only: return
    yd.PX, yd.DSTEP = meta['render_px_m'], meta['depth']['step']
    k = np.lib.format.open_memmap(C / 'kcls.npy', 'w+', np.uint8, (yd.H // yd.KF, yd.W // yd.KF)); k[:] = np.asarray(Image.open(Path(a.new) / 'classes_05m.png')); del k
    (C / 'meta.json').write_text(json.dumps({'ids': ids, 'board': meta['board'], 'board_def': meta['board_def'], 'size': [yd.W, yd.H], 'render_px_m': meta['render_px_m'], 'depth': meta['depth']}, ensure_ascii=False))
    for v in arrs.values(): v.flush()
    changed = patch_art(a, mask, bbox, arrs['cond']) + patch_maps(a, mask)
    if a.landmark:
        f = Path(a.assets) / 'map.json'; mj = json.loads(f.read_text()); cam = yd.Cam(yd.load_meta(a))
        for s in a.landmark:
            key, name, kind, xyz = s.split('|'); c = [float(v) for v in xyz.split(',')]; p = cam.proj([c])[0] / yd.F
            mj['landmarks'][key] = {'name': name, 'kind': kind, 'in_canvas': True, 'px': [round(float(p[0]), 1), round(float(p[1]), 1)], 'local_m': c}
        f.write_text(json.dumps(mj, ensure_ascii=False, separators=(',', ':'))); changed.append(f); yd.log('map.json landmarks +', [s.split('|')[0] for s in a.landmark])
    if a.manifest:
        mp = Path(a.manifest); man = json.loads(mp.read_text()); root = Path(a.assets).resolve().parent; n = 0
        for p in sorted(set(changed)):
            key = str(p.resolve().relative_to(root)); sha = hashlib.sha256(p.read_bytes()).hexdigest()
            if key in man['files'] and man['files'][key] != sha: man['files'][key] = sha; n += 1
        mp.write_text(json.dumps(man, indent=1) + '\n'); yd.log('manifest sha256 updated', n)
    yd.log('patched files', len(set(changed)))


if __name__ == '__main__':
    main()
