#!/usr/bin/env python3
"""새 파이프라인(Blender 조건 렌더 + 양식 패스) 결과를 앱 자산(assets/redraw/)으로 굽는다.

입력(6.25 cm/px, 22016×13568, 카메라 = 옛 자산과 같음, 0.5 m 로 줄이면 2752×1696)
  --raw   양식 결과 raw.png (RGB)
  --pass  조건 렌더 폴더: cond.png, cond_id.png(R·256+G = 물체 id), cond_z.png(깊이 2040 + v×0.025 m), meta.json(id → 종류)
  --ground-class  지면 분류 ground_class.png(prep_ground.py; 3 도로 4 광장·보행 5 잔디 6 모래 7 바탕 12 노면표시 14 물 15 궁궐 마당)
  --osm   osm_raw.json(궁 경계 relation 5501517), --camera 카메라 json
작업 폴더 --work 에 단계별 결과를 쓴다(CPU 만, 프로세스 16 이하).

단계(순서대로, `all` 은 cache→lock→quant→maps→tiles)
  cache  큰 PNG 를 한 번 풀어 npy(mmap)로 둔다          → work/cache/{raw,cond,ids,v,gcls}.npy, palace.npy
  lock   궁궐 지면 잠금: 궁 구역 안 '지면' 픽셀에서 양식 결과가 그 지면 종류의 기준색과 크게 다른 덩어리(지어낸 건물·소품)를
         그 종류의 기준색(밝은 면·그늘 면 색을 조건 렌더의 그림자 비율로 섞은 색)으로 다시 칠한다 → work/cache/locked.npy, lock_stats.json, sheets/
  quant  팔레트 양자화(디더 없음) + 피라미드 → work/p0625.png(z8) p0125.png(z4) p025.png(z2) p05.png(z1), palette.json
  maps   depth_rg8.png, classes.png, crown.png (2752×1696) → work/
  tiles  make_tiles.py 로 work/tiles/ + bg.png(z2 전체) + bg_1x.png(z1 과 같은 것)

  python build_assets.py all --raw RAW --pass PASS --work WORK [--ground-class G] [--osm O] [--camera C] [--make-tiles M]
  python build_assets.py lock --work WORK --crop x0,y0,x1,y1      # 시험: 한 구역만 잠금하고 시트만 쓴다
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as nd

Image.MAX_IMAGE_PIXELS = None
W, H, PX = 22016, 13568, 0.0625
F = 8                       # 지도 px(0.5 m) 하나 = 8×8 그림 px
MW, MH = W // F, H // F     # 2752 × 1696
HERE = Path(__file__).resolve().parent
T0 = time.time()


def log(*a):
    print(f'[{time.time() - T0:7.1f}s]', *a, flush=True)


# ───────────────────────── 카메라 · 높이 ─────────────────────────
class Cam:
    def __init__(s, path):
        c = json.load(open(path))
        s.ex, s.ey, s.vd = (np.array(c[k], np.float64) for k in ('screen_x_axis', 'screen_y_axis', 'view_dir'))
        s.cx, s.cy, s.cl = c['cx'], c['cy'], np.array(c['cam_location'], np.float64)
        s.cvd = float(s.cl @ s.vd)

    def proj(s, xy):
        xy = np.asarray(xy, np.float64)
        return np.stack([(xy @ s.ex[:2] - s.cx) / PX + W / 2, H / 2 - (xy @ s.ey[:2] - s.cy) / PX], 1)

    def ground_depth(s, py, scale=1.0):
        """화면 행 py(그림 px, 배율 scale = 지도 px 당 그림 px 의 역수 아님: px 크기 = PX*scale) 중심의 z=0 평면 깊이"""
        Hs = H / scale
        v = (Hs / 2 - (np.asarray(py, np.float64) + 0.5)) * PX * scale + s.cy
        return -v * s.ey[2] / s.vd[2] - s.cvd

    def height(s, depth, py0, scale=1.0):
        """depth(2D, 행 py0 부터) → z=0 위 높이(m)"""
        dg = s.ground_depth(np.arange(py0, py0 + depth.shape[0]), scale)[:, None]
        return (s.vd[2] * (depth - dg)).astype(np.float32)


def palace_raster(osm_path, cam):
    """경복궁 경계(OSM relation 5501517)를 그림 px 로 칠한 마스크(bool, H×W)"""
    sys.path.insert(0, str(HERE))
    import osm_blds
    from shapely.geometry import LineString
    from shapely.ops import polygonize, unary_union
    raw = json.load(open(osm_path))['elements']
    rel = [e for e in raw if e['type'] == 'relation' and e['id'] == 5501517]
    ls = [LineString([osm_blds.tm5186(q['lon'], q['lat']) for q in m['geometry']]) for m in rel[0]['members'] if m.get('geometry') and m.get('role') in ('outer', '')]
    poly = unary_union(list(polygonize(unary_union(ls))))
    im = Image.new('L', (W, H), 0)
    dr = ImageDraw.Draw(im)
    for g in (poly.geoms if poly.geom_type == 'MultiPolygon' else [poly]):
        dr.polygon([tuple(p) for p in cam.proj(np.array(g.exterior.coords))], fill=1)
    return np.asarray(im).astype(bool)


# ───────────────────────── cache ─────────────────────────
def rg16(path):
    a = np.asarray(Image.open(path).convert('RGB'))
    return a[..., 0].astype(np.uint16) * 256 + a[..., 1]


def step_cache(a):
    C = Path(a.work) / 'cache'
    C.mkdir(parents=True, exist_ok=True)
    P = Path(a.pass_dir)
    jobs = [('raw', lambda: np.asarray(Image.open(a.raw).convert('RGB'))),
            ('cond', lambda: np.asarray(Image.open(P / 'cond.png').convert('RGB'))),
            ('ids', lambda: rg16(P / 'cond_id.png')),
            ('v', lambda: rg16(P / 'cond_z.png')),
            ('gcls', lambda: np.asarray(Image.open(a.ground_class))),
            ('palace', lambda: palace_raster(a.osm, Cam(a.camera)))]
    for name, fn in jobs:
        x = fn()
        assert x.shape[:2] == (H, W), (name, x.shape)
        np.save(C / f'{name}.npy', x)
        log('cache', name, x.shape, x.dtype)
        del x
    (C / 'meta.json').write_text(json.dumps(json.load(open(P / 'meta.json'))))
    (C / 'inputs.json').write_text(json.dumps({'raw': str(a.raw), 'pass': str(P), 'ground_class': str(a.ground_class), 'osm': str(a.osm), 'camera': str(a.camera)}, ensure_ascii=False, indent=1))


def cache(a, name):
    return np.load(Path(a.work) / 'cache' / f'{name}.npy', mmap_mode='r')


def type_lut(meta, kinds):
    lut = np.zeros(65536, bool)
    for k, v in meta.items():
        if v in kinds:
            lut[int(k)] = True
    return lut


# ───────────────────────── lock(궁궐 지면 잠금) ─────────────────────────
# 광화문 앞(월대·앞 잔디): 궁 경계 다각형 밖이라 따로 넣는다. 그림 px 다각형(6.25 cm). 도로(지면 분류 3·12)는 넣지 않는다.
GW_FRONT = [(5200, 9000), (7400, 9000), (7400, 10500), (5200, 10500)]
LUM = np.array([0.299, 0.587, 0.114], np.float32)
ROAD_CODES = (3, 12)


def disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def hue_class(c):
    """조건 렌더 색 → 0 회색, 1 초록, 2 따뜻한 색(모래·흙·석재), 3 파랑"""
    c = c.astype(np.int16)
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    out = np.full(r.shape, 2, np.uint8)
    out[(np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)) < 18] = 0
    out[(g > r + 12) & (g > b + 12)] = 1
    out[(b > r + 15) & (b >= g)] = 3
    return out


def color_lut(cond, raw, mask, step=3):
    """조건 렌더 색 → 양식 결과 색 대응표. 조건 색(채널당 5 비트, 그늘 포함)이 같은 지면 픽셀들의 양식 결과 평균(1차 평균에서 먼 값은 빼고 다시 평균).
    지어낸 물체는 소수라 평균을 끌지 못한다. 칸에 표본이 적으면 4 비트·3 비트 칸으로 물러난다."""
    m = mask[::step, ::step]
    c = cond[::step, ::step][m].astype(np.int32)
    r = raw[::step, ::step][m].astype(np.float64)
    luts = []
    for bits in (5, 4, 3):
        sh = 8 - bits
        key = ((c[:, 0] >> sh) << (2 * bits)) | ((c[:, 1] >> sh) << bits) | (c[:, 2] >> sh)
        nb = 1 << (3 * bits)
        cnt = np.bincount(key, minlength=nb)
        mean = np.stack([np.bincount(key, r[:, i], nb) for i in range(3)], 1) / np.maximum(cnt, 1)[:, None]
        ok = np.sqrt(((r - mean[key]) ** 2).sum(1)) < 60          # 한 번 깎는다
        cnt2 = np.bincount(key[ok], minlength=nb)
        mean2 = np.stack([np.bincount(key[ok], r[ok, i], nb) for i in range(3)], 1) / np.maximum(cnt2, 1)[:, None]
        luts.append((bits, np.where(cnt2[:, None] >= 40, mean2, np.nan).astype(np.float32)))
    return luts


def lut_apply(luts, cond):
    c = cond.astype(np.int32)
    out = np.full(c.shape, np.nan, np.float32)
    for bits, lut in luts:
        sh = 8 - bits
        key = ((c[..., 0] >> sh) << (2 * bits)) | ((c[..., 1] >> sh) << bits) | (c[..., 2] >> sh)
        miss = np.isnan(out[..., 0])
        out[miss] = lut[key[miss]]
    miss = np.isnan(out[..., 0])
    out[miss] = cond[miss]
    return out


def ground_masks(cond, ids, v, gcls, pal, y0, x0, meta, cam, P):
    h, w = ids.shape
    hgt = cam.height(2040.0 + v.astype(np.float32) * 0.025, y0)
    per = 2 * PX / cam.ey[2]                      # 수평 판정: 화면 위로 1 px 갈 때 높이 변화(수직 벽 = 1)
    slope = np.zeros_like(hgt)
    slope[1:-1] = (hgt[:-2] - hgt[2:]) / per
    platy = type_lut(meta, ('palace', 'khs'))[ids] & (hgt < P['plat_h']) & (np.abs(slope) < 0.25) & (hgt > 0.15)   # 기단·월대 윗면
    ground = (ids == 1) | platy
    im = Image.new('L', (w, h), 0)
    ImageDraw.Draw(im).polygon([(x - x0, y - y0) for x, y in GW_FRONT], fill=1)
    front = np.asarray(im).astype(bool)
    # 궁 경계를 25 m 넓힌 곳(담 바깥 보도·잔디: 예행 결과는 담 밖 보도에도 문을 지었다) + 광화문 앞(도로 위에도 문을 지었다)
    p8 = nd.binary_dilation(np.asarray(pal[F // 2::F, F // 2::F]), disk(P['zone_pad_cells']))
    near = np.repeat(np.repeat(p8, F, 0), F, 1)[:h, :w]
    # 도로 분류(지면 분류 3·12)는 OSM 도로 폭으로 칠해 보도까지 덮으므로 빼지 않는다(담 밖 보도에 지은 문이 도로 분류 위에 있었다).
    # 도로의 차선·횡단보도는 조건 렌더에 있으므로 대응표 색이 그것을 따른다.
    zone = near | front
    return ground, platy, zone


def sidewalk_mask(ids, gcls, meta, near, r=92):
    """담길 보도 띠(리드 추가 11-11): 궁 둘레 담(meta 'wall')에 차도가 바로 붙은 곳 → 담에서 r px(약 2.7 m) 안의 차도 지면을 보도로.
    새 지면에는 효자로 쪽 담 옆 보도가 없어 러너 담길이 끊겼다."""
    wl = np.zeros(65536, bool)
    for k, t in meta.items():
        if t == 'wall':
            wl[int(k)] = True
    w = wl[ids] & near
    if not w.any():
        return np.zeros(ids.shape, bool)
    cand = (ids == 1) & np.isin(gcls, ROAD_CODES)
    if not cand.any():
        return cand
    return (nd.distance_transform_edt(~w) <= r) & cand


def chroma_dist(a, b):
    """밝기 차와 색조 차(3배 가중)를 합친 거리: 베이지 지면에 칠한 연두 잔디처럼 밝기가 비슷해도 색이 다른 것을 잡는다"""
    la, lb = a @ LUM, b @ LUM
    dc = (a - la[..., None]) - (b - lb[..., None])
    return np.sqrt((la - lb) ** 2 + 3.0 * (dc ** 2).sum(-1))


def lock_region(raw, cond, ids, v, gcls, pal, y0, x0, meta, cam, P, luts):
    """한 구역(배열은 그 구역 크기)을 잠근다 → (새 그림, 바꾼 마스크, 정보, 거리, 구역)"""
    ground, platy, zone = ground_masks(cond, ids, v, gcls, pal, y0, x0, meta, cam, P)
    E = lut_apply(luts, cond)
    rawf = raw.astype(np.float32)
    d = chroma_dist(rawf, E)
    d_all = d.copy()
    d[~ground] = 0
    ds = nd.uniform_filter(d, P['win'])
    protect = nd.binary_dilation(~ground, disk(P['keep_px']))   # 건물·담·나무 등 지면이 아닌 물체의 가장자리(처마 선·윤곽선) 보존
    # 구역은 씨앗: 편차 덩어리를 구역 밖까지 이어 잡고, 구역과 충분히 겹치는 덩어리는 통째로 칠한다
    # (구역 경계에서 자르면 경계가 직선 이음매로 남는다 — 예행 결과는 세종대로 교차로의 도로를 광장 띠로 칠했고 그 띠가 광화문 앞 상자 밖으로 이어졌다)
    m = (ds > P['thr']) & ground & ~protect
    m = nd.binary_opening(m, disk(P['open_px']))
    lab, n = nd.label(m)
    keep = np.zeros(n + 1, bool)
    big = []
    if n:
        sz = nd.sum(m, lab, range(n + 1))
        inz = nd.sum(m & zone, lab, range(n + 1))
        keep = (inz >= P['min_px']) & ((inz >= 0.3 * sz) | (inz >= P['seed_px'])) & (sz <= P['max_px'])
        keep[0] = False
        big = [(int(i), int(sz[i]), int(inz[i])) for i in np.nonzero((inz >= P['min_px']) & (sz > P['max_px']))[0] if i]
    blob = keep[lab]
    region = nd.binary_dilation(blob, disk(P['grow_px'] + 2))
    fill = nd.binary_dilation(blob, disk(P['grow_px'])) & ground & ~protect
    fill = nd.binary_fill_holes(fill) & ground & ~protect & region
    # D2 (리드 11-12): 광화문 월대 윗면은 문턱과 관계없이 통째로 채운다(연두·베이지 거리가 문턱 근처라 일부만 잡혀 얼룩이 됐다)
    h_, w_ = ids.shape
    im = Image.new('L', (w_, h_), 0)
    ImageDraw.Draw(im).polygon([(x - x0, y - y0) for x, y in GW_FRONT], fill=1)
    wol = platy & np.asarray(im).astype(bool) & ~protect
    clean = ground & zone & ~fill & ~wol & ~protect & (ds < P['thr'] * 0.5)
    fill = fill | wol
    # D1 (리드 11-12): 도로 지면에는 잔무늬를 옮겨 붙이지 않는다(차선·그림자·소품이 섞인 잔무늬가 유령 무늬와 칸 띠가 됐다). 월대는 결을 약하게
    road = (ids == 1) & np.isin(gcls, ROAD_CODES)
    tw = np.where(road[fill], 0.0, np.where(wol[fill], 0.3, P['tex']))[:, None]
    out = raw.copy()
    out[fill] = np.clip(E[fill] + texture(raw, E, clean, fill, y0, x0) * tw, 0, 255).astype(np.uint8)
    # D3 (리드 11-12): 담 면에 지어낸 진열창·문 → 담 id 에서 기대색과 크게 다른 덩어리만 기대색으로(처마 선은 담 id 가 아니라 그대로)
    wl = np.zeros(65536, bool)
    for k, t in meta.items():
        if t == 'wall': wl[int(k)] = True
    wall = wl[ids] & zone
    mw = (nd.uniform_filter(np.where(wall, d_all, 0), P['win']) > P.get('wall_thr', 70.0)) & wall
    mw = nd.binary_opening(mw, disk(2))
    labw, nw = nd.label(mw)
    if nw:
        szw = nd.sum(mw, labw, range(nw + 1)); kw = szw >= P.get('wall_min_px', 250); kw[0] = False
        fw = nd.binary_dilation(kw[labw], disk(3)) & wall
        out[fw] = np.clip(E[fw], 0, 255).astype(np.uint8)
        fill = fill | fw
    # tree lock (리드 추가 11-11): 수목 id 위에 지어낸 전각·지붕 조각 → 조건 렌더 기대색으로 되돌린다
    tree = (ids >= 22000) & zone
    mt = (nd.uniform_filter(np.where(tree, d_all, 0), P['win']) > P.get('tree_thr', 70.0)) & tree
    mt = nd.binary_opening(mt, disk(2))
    labt, nt = nd.label(mt)
    if nt:
        szt = nd.sum(mt, labt, range(nt + 1)); kt = szt >= P.get('tree_min_px', 400); kt[0] = False
        ft = nd.binary_dilation(kt[labt], disk(4)) & (ids >= 22000)
        out[ft] = np.clip(E[ft], 0, 255).astype(np.uint8)
        fill = fill | ft
    sw = sidewalk_mask(ids, gcls, meta, zone)
    if sw.any():
        ref = ground & (gcls == 4) & zone & ~fill & ~sw
        col = np.median(out[ref][::17], 0) if ref.sum() > 5000 else np.array([226, 214, 190], np.float32)
        rs = np.random.default_rng(7)
        n = (rs.integers(-5, 6, ids.shape)[sw])[:, None]
        out[sw] = np.clip(col[None] + n, 0, 255).astype(np.uint8)
        edge = sw & ~nd.binary_erosion(sw, disk(2)) & nd.binary_dilation((ids == 1) & np.isin(gcls, ROAD_CODES) & ~sw, disk(2))
        out[edge] = np.clip(col * 0.72, 0, 255).astype(np.uint8)      # 연석 선
        fill = fill | sw
    # D3b (리드 11-12): 광화문 모델(khs) 담 면의 지어낸 파란 진열창 — 조건 렌더는 파랗지 않은데 그림이 파란 덩어리만 기대색으로
    khs_f = type_lut(meta, ('khs',))[ids] & np.asarray(im).astype(bool)
    rr, cc = raw.astype(np.int16), cond.astype(np.int16)
    blu = khs_f & (rr[..., 2] - rr[..., 0] > 25) & ~(cc[..., 2] - cc[..., 0] > 15)
    blu = nd.binary_opening(blu, disk(1))
    # 눈으로 확인한 지어낸 물체 상자(그림 px x0,y0,x1,y1): 조건 렌더에 없는 것. 담 면(기와 아래 밝은 면)만 기대색으로
    lc = cond.astype(np.float32) @ LUM
    for bx0, by0, bx1, by1 in MANUAL_FIX:
        X0, Y0, X1, Y1 = max(bx0 - x0, 0), max(by0 - y0, 0), max(bx1 - x0, 0), max(by1 - y0, 0)
        if X1 <= X0 or Y1 <= Y0: continue
        bm = np.zeros(ids.shape, bool); bm[Y0:Y1, X0:X1] = True
        blu |= bm & (ids > 1) & (lc > 90)
    labb, nb = nd.label(blu)
    if nb:
        szb = nd.sum(blu, labb, range(nb + 1)); kb = szb >= 150; kb[0] = False
        fb = nd.binary_dilation(kb[labb], disk(3)) & khs_f
        out[fb] = np.clip(E[fb], 0, 255).astype(np.uint8)
        fill = fill | fb
    info = {'_blobs': int(keep.sum()), '_fill_px': int(fill.sum()), 'platform_px': int(platy.sum()), 'skipped_huge_components': big}
    return out, fill, info, ds, zone


def texture(raw, E, clean, fill, y0, x0, T=96):
    """채울 자리의 결: 같은 조건 색 칸 대응표로 만든 평평한 색 위에, 가까운 깨끗한 지면의 잔무늬(양식 결과 − 기대색)를 T px 주기로 옮겨 붙인다.
    각 T×T 칸마다 깨끗한 픽셀 비율이 가장 높은 이웃 칸(8방향, 최대 4칸 거리)의 잔무늬를 쓴다."""
    res = raw.astype(np.float32) - E
    res = np.clip(res, -40, 40)
    h, w = fill.shape
    out = np.zeros((h, w, 3), np.float32)
    ny, nx = -(-h // T), -(-w // T)
    cf = np.zeros((ny, nx), np.float32)
    for j in range(ny):
        for i in range(nx):
            cf[j, i] = clean[j * T:(j + 1) * T, i * T:(i + 1) * T].mean()
    for j in range(ny):
        for i in range(nx):
            blk = fill[j * T:(j + 1) * T, i * T:(i + 1) * T]
            if not blk.any():
                continue
            best, bj, bi = 0.9, -1, -1
            for r in range(1, 5):
                for dj in range(-r, r + 1):
                    for di in range(-r, r + 1):
                        if max(abs(dj), abs(di)) != r:
                            continue
                        jj, ii = j + dj, i + di
                        if 0 <= jj < ny and 0 <= ii < nx and cf[jj, ii] > best and (jj + 1) * T <= h and (ii + 1) * T <= w:
                            best, bj, bi = cf[jj, ii], jj, ii
                if bj >= 0:
                    break
            if bj < 0:
                continue
            src = res[bj * T:(bj + 1) * T, bi * T:(bi + 1) * T] * clean[bj * T:(bj + 1) * T, bi * T:(bi + 1) * T, None]
            hh, ww = blk.shape
            out[j * T:j * T + hh, i * T:i * T + ww] = src[:hh, :ww]
    return out[fill]


MANUAL_FIX = [(5895, 9420, 5995, 9515)]   # 광화문 서쪽 담 면의 진열창(리드 11-12, 조건 렌더는 돌 담)
PARAMS = {'thr': 42.0, 'win': 9, 'keep_px': 5, 'open_px': 3, 'min_px': 900, 'grow_px': 4, 'plat_h': 2.6, 'tex': 0.7, 'zone_pad_cells': 50, 'seed_px': 20000, 'max_px': 4000000}
# 확인 자리(그림 px): 광화문 일대, 근정전 마당
CHECKS = {'gwang': (5200, 9000, 7400, 10500), 'geunjeong': (8400, 6800, 11200, 9000)}


def sheet(path, panels, scale=2):
    ims = [Image.fromarray(np.asarray(p)).reduce(scale) if scale > 1 else Image.fromarray(np.asarray(p)) for p in panels]
    w, h = ims[0].size
    out = Image.new('RGB', (w * 2 + 8, h * 2 + 8), (255, 255, 255))
    for i, im in enumerate(ims[:4]):
        out.paste(im.convert('RGB'), ((i % 2) * (w + 8), (i // 2) * (h + 8)))
    out.save(path)


def overlay(img, mask, col=(255, 0, 255)):
    o = np.asarray(img).copy()
    edge = mask & ~nd.binary_erosion(mask, disk(2))
    o[mask] = (o[mask] * 0.55 + np.array(col) * 0.45).astype(np.uint8)
    o[edge] = col
    return o


def lock_box(pal):
    """궁 경계 + 광화문 앞을 덮는 상자(여백 800 px)"""
    ys, xs = np.nonzero(pal[::16, ::16])
    M = 800   # 구역 팽창(25 m = 400 px)보다 넉넉히, 8 의 배수
    bx0 = max(0, min(xs.min() * 16, GW_FRONT[0][0]) - M); bx1 = min(W, max(xs.max() * 16 + 16, GW_FRONT[1][0]) + M)
    by0 = max(0, min(ys.min() * 16, GW_FRONT[0][1]) - M); by1 = min(H, max(ys.max() * 16 + 16, GW_FRONT[2][1]) + M)
    return int(bx0), int(by0), int(bx1), int(by1)


def get_luts(a, raw, cond, ids, v, gcls, pal, meta, cam, P):
    f = Path(a.work) / 'cache' / 'lock_lut.npz'
    if f.exists():
        z = np.load(f)
        return [(int(b), z[f'l{b}']) for b in (5, 4, 3)]
    bx0, by0, bx1, by1 = lock_box(pal)
    # 대응표는 넓게: 상자 전체의 지면(구역 밖 포함)
    sl = (slice(by0, by1), slice(bx0, bx1))
    ground, _, _ = ground_masks(cond[sl], ids[sl], v[sl], gcls[sl], pal[sl], by0, bx0, meta, cam, P)
    luts = color_lut(cond[sl], raw[sl], ground)
    np.savez(f, **{f'l{b}': l for b, l in luts})
    log('lut bins filled', {b: int((~np.isnan(l[:, 0])).sum()) for b, l in luts})
    return luts


def step_lock(a):
    W_ = Path(a.work)
    S = W_ / 'sheets'
    S.mkdir(parents=True, exist_ok=True)
    meta = json.loads((W_ / 'cache' / 'meta.json').read_text())
    cam = Cam(a.camera)
    raw, cond, ids, v, gcls, pal = (cache(a, n) for n in ('raw', 'cond', 'ids', 'v', 'gcls', 'palace'))
    P = dict(PARAMS)
    luts = get_luts(a, raw, cond, ids, v, gcls, pal, meta, cam, P)
    if a.crop:
        x0, y0, x1, y1 = map(int, a.crop.split(','))
        sl = (slice(y0, y1), slice(x0, x1))
        out, fill, info, ds, zone = lock_region(raw[sl], cond[sl], ids[sl], v[sl], gcls[sl], pal[sl], y0, x0, meta, cam, P, luts)
        tag = f'crop_{x0}_{y0}'
        sheet(S / f'{tag}.png', [cond[sl], raw[sl], out, overlay(raw[sl], fill)])
        Image.fromarray(np.clip(ds, 0, 255).astype(np.uint8)).reduce(2).save(S / f'{tag}_dist.png')
        log(tag, 'fill px', int(fill.sum()), f'{fill.sum() * PX * PX:.1f} m²', 'blobs', info['_blobs'])
        return
    bx0, by0, bx1, by1 = lock_box(pal)
    log('lock box', (bx0, by0, bx1, by1))
    sl = (slice(by0, by1), slice(bx0, bx1))
    out, fill, info, ds, zone = lock_region(raw[sl], cond[sl], ids[sl], v[sl], gcls[sl], pal[sl], by0, bx0, meta, cam, P, luts)
    locked = np.lib.format.open_memmap(W_ / 'cache' / 'locked.npy', mode='w+', dtype=np.uint8, shape=(H, W, 3))
    locked[:] = raw
    locked[sl] = out
    locked.flush()
    fm = np.zeros((H, W), bool)
    fm[sl] = fill
    np.save(W_ / 'cache' / 'lock_mask.npy', fm)
    zm = np.zeros((H, W), bool)
    zm[sl] = zone
    Image.fromarray((zm[4::8, 4::8] * 120 + fm[4::8, 4::8] * 135).astype(np.uint8)).save(W_ / 'lock_mask_05m.png')
    per = {}
    for name, (x0, y0, x1, y1) in CHECKS.items():
        s2 = (slice(y0, y1), slice(x0, x1))
        sheet(S / f'lock_{name}.png', [cond[s2], raw[s2], locked[s2], overlay(raw[s2], fm[s2])])
        per[name] = {'box': [x0, y0, x1, y1], 'fill_px': int(fm[s2].sum()), 'fill_m2': round(float(fm[s2].sum()) * PX * PX, 1)}
    # 전체 축소 시트(1/4): 왼쪽 원래, 오른쪽 잠금 뒤 + 바꾼 곳 표시
    r4 = np.asarray(Image.fromarray(np.ascontiguousarray(raw[sl])).reduce(4))
    l4 = np.asarray(Image.fromarray(np.ascontiguousarray(out)).reduce(4))
    f4 = fill[2::4, 2::4][:r4.shape[0], :r4.shape[1]]
    both = np.concatenate([overlay(r4, f4), np.full((r4.shape[0], 16, 3), 255, np.uint8), l4], 1)
    Image.fromarray(both).save(S / 'lock_overview.png')
    st = {'params': P, 'box': [bx0, by0, bx1, by1], 'zone_px': int(zone.sum()), 'zone_m2': round(float(zone.sum()) * PX * PX, 1),
          'fill_px': int(fill.sum()), 'fill_m2': round(float(fill.sum()) * PX * PX, 1), 'blobs': info['_blobs'], 'platform_px': info['platform_px'], 'skipped_huge_components': info['skipped_huge_components'], 'checks': per}
    (W_ / 'lock_stats.json').write_text(json.dumps(st, ensure_ascii=False, indent=1))
    log('lock: fill', st['fill_m2'], 'm² of zone', st['zone_m2'], 'm², blobs', st['blobs'])


# ───────────────────────── quant(팔레트 + 피라미드) ─────────────────────────
# 옛 snap.py(0.25 m 그림을 2×2 다수결로 0.5 m 격자에 스냅 + 64색)와 finish.py(타일마다 클래스 평균색 맞추기)는 적용하지 않는다:
#  - 새 그림은 6.25 cm 에서 그린 픽셀아트라 z8 이 원본 해상도다(블록 스냅을 하면 z8 세부가 사라진다).
#  - 공유 latent 로 이은 한 장이라 타일 톤 차가 없다(seam/NOTES.md).
#  - 옛 96색 팔레트로 스냅하면 새 그림의 색(밝은 잔디·따뜻한 마당)이 옛 색으로 끌려간다 → 새 그림에서 팔레트를 뽑는다(--colors, 기본 128).
#  셰이더 색 키(render.js isGreen·isBlue·isGlass·기와 무채색 판정)는 문턱값 판정이라 팔레트 일치가 필요 없다 → step keys 로 클래스별 통과율을 확인한다.
_QP = None


def _qinit(pal):
    global _QP
    _QP = Image.new('P', (1, 1))
    _QP.putpalette(pal)


def _quant_strip(arr):
    q = np.asarray(Image.fromarray(arr).quantize(palette=_QP, dither=Image.Dither.NONE)).copy()
    pal = np.array(_QP.getpalette()[:768]).reshape(-1, 3)
    dup = np.array([i > 0 and (pal[i] == pal[0]).all() for i in range(256)])
    q[dup[q]] = 0
    return q


def quantize_big(rgb, pal, jobs, strip=512):
    from concurrent.futures import ProcessPoolExecutor
    out = np.zeros(rgb.shape[:2], np.uint8)
    with ProcessPoolExecutor(jobs, initializer=_qinit, initargs=(pal,)) as ex:
        ys = list(range(0, rgb.shape[0], strip))
        for y, q in zip(ys, ex.map(_quant_strip, (np.ascontiguousarray(rgb[y:y + strip]) for y in ys))):
            out[y:y + strip] = q
    return out


def save_p(ix, pal, path):
    o = Image.fromarray(ix, 'P')
    o.putpalette(pal)
    o.save(path, compress_level=9)


def step_quant(a):
    W_ = Path(a.work)
    src = W_ / 'cache' / 'locked.npy'
    rgb = np.load(src if src.exists() else W_ / 'cache' / 'raw.npy', mmap_mode='r')
    small = Image.fromarray(np.ascontiguousarray(rgb[::4, ::4]))
    pimg = small.quantize(colors=a.colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE, kmeans=3)
    pal = pimg.getpalette()[:a.colors * 3]
    pal = pal + pal[:3] * (256 - a.colors)      # 남는 칸은 0번 색 복사(검정 0 으로 채우면 어두운 색이 그 칸으로 간다) → 아래에서 0 번으로 되돌린다
    log('palette', a.colors)
    ix8 = quantize_big(rgb, pal, a.jobs)
    save_p(ix8, pal, W_ / 'p0625.png')
    P = np.array(pal, np.float32).reshape(-1, 3)
    err = {}
    for name, f in (('p0125', 2), ('p025', 4), ('p05', 8)):
        rq = P[ix8].reshape(H // f, f, W // f, f, 3).mean((1, 3)).round().astype(np.uint8)   # 양자화한 z8 을 BOX 로 줄여 같은 팔레트로
        ix = quantize_big(rq, pal, a.jobs)
        save_p(ix, pal, W_ / f'{name}.png')
        log(name, ix.shape)
    e = np.sqrt(((P[ix8[::7, ::7]] - rgb[::7, ::7].astype(np.float32)) ** 2).sum(-1))
    err = {'mean': float(e.mean()), 'p95': float(np.percentile(e, 95))}
    # 비교: 옛 96색 팔레트로 스냅했을 때의 오차
    old = W_ / 'old_palette.json'
    if old.exists():
        op = json.loads(old.read_text())
        oq = np.asarray(Image.fromarray(np.ascontiguousarray(rgb[::7, ::7])).quantize(palette=_pimg(op), dither=Image.Dither.NONE))
        oq = np.where(oq >= len(op) // 3, 0, oq)
        oe = np.sqrt(((np.array(op, np.float32).reshape(-1, 3)[oq] - rgb[::7, ::7].astype(np.float32)) ** 2).sum(-1))
        err['old96_mean'] = float(oe.mean())
        err['old96_p95'] = float(np.percentile(oe, 95))
    (W_ / 'palette.json').write_text(json.dumps({'colors': a.colors, 'palette': pal[:a.colors * 3], 'rgb_error_z8': err}))
    log('quant error', err)


def _pimg(pal):
    im = Image.new('P', (1, 1))
    im.putpalette(list(pal) + list(pal[:3]) * ((768 - len(pal)) // 3))
    return im


# ───────────────────────── maps(depth_rg8 · classes · crown) ─────────────────────────
APP_CLS = {'none': 0, 'ground': 1, 'road': 2, 'green': 3, 'water': 4, 'court': 5, 'roof': 6, 'wall': 7, 'proof': 8, 'pwall': 9, 'tree': 10, 'walk': 11}


def pixel_classes(cond, ids, v, gcls, pal_in, pal_near, y0, meta, cam):
    """그림 px 마다 앱 클래스(0–11). 규칙은 pipeline/make_guide.py:237-273 를 새 패스에 옮긴 것:
    지면(id 1) = 지면 분류(도로 2, 광장·보행 11, 잔디 3, 물 4, 궁 경계 안 바탕·모래·마당 5, 그 밖 1; 조건 렌더가 초록이면 3. 파랑 판정은 쓰지 않는다: 그늘이 푸르게 렌더돼 물로 잡힌다)
    기단·월대 윗면(궁궐 id, 2.6 m 아래 수평면) = 5(광화문 월대 = 국가유산청 모델은 11), 나무 = 10
    건물 = 지붕 6/벽 7, 궁궐·국가유산청 = 8/9, 담 = 궁 둘레면 8/9 아니면 6/7.  벽 = 화면 위로 갈 때 높이 변화 / 수직 벽의 변화가 0.55~2.2."""
    hgt = cam.height(2040.0 + v.astype(np.float32) * 0.025, y0)
    per = 2 * PX / cam.ey[2]
    slope = np.zeros_like(hgt)
    slope[1:-1] = (hgt[:-2] - hgt[2:]) / per
    wall = (slope > 0.55) & (slope < 2.2)
    typ = np.zeros(65536, np.uint8)        # 0 지면 1 건물 2 궁궐 3 담 4 나무
    for k, t in meta.items():
        typ[int(k)] = {'ground': 0, 'tree': 4, 'palace': 2, 'khs': 2, 'wall': 3}.get(t, 1)
    t = typ[ids]
    t[(ids > 1) & (t == 0)] = 1
    c = np.zeros(ids.shape, np.uint8)
    g = ids == 1
    hc = hue_class(cond)
    gc = np.full(gcls.shape, 1, np.uint8)
    gc[np.isin(gcls, (6, 7, 15)) & pal_in] = 5     # 궁 경계 안의 바탕·모래·마당만 궁궐 마당(담 밖 보도·광화문 앞은 1·11: 담길 러너·해치가 찾는다)
    gc[gcls == 15] = 5
    gc[np.isin(gcls, (3, 12))] = 2
    gc[gcls == 4] = 11
    gc[gcls == 5] = 3
    gc[gcls == 14] = 4
    # 광화문 앞(GW_FRONT 상자): 국가유산청 모델의 포장 지면(월대 앞 광장·보도)이 id 1·지면 분류 '바탕'으로 들어온다 → 보행 광장 11(옛 맵과 같다)
    fr = np.zeros(gcls.shape, bool)
    (fx0, fy0), (fx1, fy1) = GW_FRONT[0], GW_FRONT[2]
    if y0 < fy1 and y0 + gcls.shape[0] > fy0:
        fr[max(0, fy0 - y0):max(0, fy1 - y0), fx0:fx1] = True
    gc[fr & np.isin(gcls, (4, 6, 7)) & ~pal_in] = 11
    gc[(hc == 1) & ~np.isin(gcls, (3, 12))] = 3
    gc[sidewalk_mask(ids, gcls, meta, pal_near)] = 11
    c[g] = gc[g]
    b = t == 1
    c[b] = np.where(wall[b], 7, 6)
    pw = (t == 2) | ((t == 3) & pal_near)
    c[pw] = np.where(wall[pw], 9, 8)
    ow = (t == 3) & ~pal_near
    c[ow] = np.where(wall[ow], 7, 6)
    plat = (t == 2) & (hgt < 2.6) & (np.abs(slope) < 0.25) & (hgt > 0.15)
    c[plat] = 5
    # 광화문 월대(국가유산청 모델 = meta 'khs')의 윗면은 보행 광장 11: 옛 make_guide 의 광화문 월대 예외와 같다(해치·수문장 자리를 찾는 클래스)
    khs = np.zeros(65536, bool)
    for k, t_ in meta.items():
        if t_ == 'khs':
            khs[int(k)] = True
    c[plat & khs[ids]] = 11
    c[t == 4] = 10
    return c


def step_maps(a):
    W_ = Path(a.work)
    meta = json.loads((W_ / 'cache' / 'meta.json').read_text())
    cam = Cam(a.camera)
    cond, ids, v, gcls, pal = (cache(a, n) for n in ('cond', 'ids', 'v', 'gcls', 'palace'))
    # 궁 둘레(담 판정용): 궁 경계 30 m 팽창
    pal_near = nd.binary_dilation(np.asarray(pal[::8, ::8]), disk(60))
    depth_v = np.zeros((MH, MW), np.uint16)
    cls = np.zeros((MH, MW), np.uint8)
    R = np.ones((MH, MW), np.uint8)
    G = np.zeros((MH, MW), np.uint8)
    clip = 0
    flat_px = 0
    BAND = 64 * F   # 64 지도 행씩
    for y0 in range(0, H, BAND):
        y1 = min(H, y0 + BAND)
        sl = (slice(y0, y1), slice(0, W))
        my0, my1 = y0 // F, y1 // F
        vv = np.asarray(v[sl])
        idb = np.asarray(ids[sl])
        # 깊이: 칸(8×8)의 가장 가까운 면 = 최솟값 → 2060 + q×0.02 로 다시 인코딩(2060 m 보다 가까운 면은 0 으로 자른다)
        # 지면(id 1)은 z=0 평면 깊이로 편다: 국가유산청 광화문 모델의 지면 메시가 z=0 위로 최대 1.3 m 떠 있는데(잔디 중앙값 0.44 m),
        # 앱은 평지를 가정해 사람·차를 z=0 에 세우고 높이 0.3 m 넘는 칸을 걷기 칸에서 뺀다. 다른 곳의 지면은 이미 z=0(±1 cm).
        dd = 2040.0 + vv.astype(np.float32) * 0.025
        gd = cam.ground_depth(np.arange(y0, y1)).astype(np.float32)[:, None]
        g1 = idb == 1
        flat_fix = int((g1 & (np.abs(dd - gd) > 0.2)).sum())
        dd = np.where(g1, gd, dd)
        d = dd.reshape(my1 - my0, F, MW, F).min((1, 3)).astype(np.float64)
        q = np.round((d - 2060.0) / 0.02)
        clip += int((q < 0).sum())
        flat_px += flat_fix
        depth_v[my0:my1] = np.clip(q, 0, 65534).astype(np.uint16)
        pn = np.repeat(np.repeat(pal_near[my0:my1], F, 0), F, 1)
        cb = np.asarray(cond[sl])
        pc = pixel_classes(cb, idb, vv, np.asarray(gcls[sl]), np.asarray(pal[sl]), pn, y0, meta, cam)
        cnt = np.stack([(pc == k).reshape(my1 - my0, F, MW, F).sum((1, 3)) for k in range(12)], -1)
        # 다수결. 동률이면 앞(작은 번호)보다 건물·나무 쪽(큰 번호)을 고른다 → 가장자리 칸이 가림 쪽으로
        cls[my0:my1] = (cnt * 16 + np.arange(12)).argmax(-1).astype(np.uint8)
        # 수관: 나무 id(22000+) 픽셀 중 줄기(조건 렌더가 붉은 갈색)를 뺀 비율, 그루 번호는 칸 안 가장 큰 나무 id 의 해시
        tr = (idb >= 22000) & (idb < 30000) & (pc == 10)
        trunk = (cb[..., 0].astype(np.int16) > cb[..., 1].astype(np.int16) + 6)
        cr = tr & ~trunk
        frac = cr.reshape(my1 - my0, F, MW, F).mean((1, 3))
        has = frac > 0.04
        rr = np.ones(frac.shape, np.uint8)
        rr[has] = 2 + np.round(frac[has] * 253).astype(np.uint8)
        R[my0:my1] = rr
        tid = np.where(cr, idb, 0).reshape(my1 - my0, F, MW, F).max((1, 3)).astype(np.uint64)
        hsh = ((tid * 2654435761) >> 11) % 255 + 1
        G[my0:my1] = np.where(has & (tid > 0), hsh, 0).astype(np.uint8)
        log('maps rows', my0, my1)
    rg = np.zeros((MH, MW, 3), np.uint8)
    rg[..., 0] = depth_v >> 8
    rg[..., 1] = depth_v & 255
    Image.fromarray(rg, 'RGB').save(W_ / 'depth_rg8.png', optimize=True)
    Image.fromarray(cls, 'L').save(W_ / 'classes.png', optimize=True)
    Image.fromarray(np.dstack([R, G, np.zeros_like(R)]), 'RGB').save(W_ / 'crown.png', optimize=True)
    st = {'depth_clipped_cells(<2060m)': clip, 'ground_px_flattened(|dz|>0.2m along view)': flat_px, 'classes': {int(k): int(n) for k, n in zip(*np.unique(cls, return_counts=True))},
          'crown_cells': int((R > 1).sum()), 'crown_trees_cells_G': int(len(np.unique(G[G > 0])))}
    (W_ / 'maps_stats.json').write_text(json.dumps(st, indent=1))
    # 보기용: 클래스 색칠
    col = np.array([(188, 196, 206), (205, 198, 182), (86, 90, 98), (126, 176, 92), (78, 138, 182), (214, 198, 160), (176, 176, 170), (222, 212, 196),
                    (52, 84, 104), (150, 62, 48), (62, 122, 58), (196, 184, 160)], np.uint8)
    Image.fromarray(col[cls]).save(W_ / 'classes_vis.png')
    log('maps', st)


# ───────────────────────── keys(셰이더 색 키 점검) ─────────────────────────
def step_keys(a):
    """render.js 의 색 판정을 클래스별로 돌려 본다: 녹지(3)·수목(10)은 isGreen, 녹지는 밝기 ≥0.56(lawnG), 수목은 <0.56, 수면(4)은 isBlue,
    궁궐 지붕(8)은 기와색(채도 <0.08, 밝기 <0.40), 건물 벽(7)은 isGlass 비율(밤 창문). 비교용으로 옛 자산(--old)도 같은 방식으로 잰다."""
    W_ = Path(a.work)
    res = {}
    for tag, bgp, clp in (('new', W_ / 'p0125.png', W_ / 'classes.png'), ('old', Path(a.old) / 'bg.png' if a.old else None, Path(a.old) / 'classes.png' if a.old else None)):
        if bgp is None or not bgp.exists():
            continue
        im = np.asarray(Image.open(bgp).convert('RGB')).astype(np.float32) / 255
        cl = np.asarray(Image.open(clp))
        f = im.shape[0] // cl.shape[0]
        cu = np.repeat(np.repeat(cl, f, 0), f, 1)
        r, g, b = im[..., 0], im[..., 1], im[..., 2]
        lum = im @ np.array([.3, .59, .11], np.float32)
        green = g - np.maximum(r, b) > 0.07
        blue = (b > r * 1.25) & (b > g)
        mx, mn = im.max(-1), im.min(-1)
        sat = mx - mn                      # render.js 와 같은 정의(최대 − 최소)
        glass = (r * 1.12 <= b) & (lum >= 0.10) & (lum < 0.62)
        tile = (sat < 0.08) & (lum < 0.40)
        out = {}
        for k, nm in ((3, 'green'), (10, 'tree'), (4, 'water'), (8, 'palace_roof'), (6, 'roof'), (7, 'wall'), (5, 'court'), (1, 'ground'), (2, 'road'), (11, 'walk')):
            m = cu == k
            if m.sum() == 0:
                continue
            out[nm] = {'px': int(m.sum()), 'isGreen': round(float(green[m].mean()), 3), 'lawnG(l>=.56)': round(float((green & (lum >= 0.56))[m].mean()), 3),
                       'isBlue': round(float(blue[m].mean()), 3), 'tile': round(float(tile[m].mean()), 3), 'isGlass': round(float(glass[m].mean()), 3),
                       'lum_med': round(float(np.median(lum[m])), 3)}
        res[tag] = out
    (W_ / 'keys.json').write_text(json.dumps(res, indent=1))
    for k in res.get('new', {}):
        print(k, 'new', res['new'][k], '\n   old', res.get('old', {}).get(k))


# ───────────────────────── tiles ─────────────────────────
def step_tiles(a):
    W_ = Path(a.work)
    T = W_ / 'tiles'
    r = subprocess.run([sys.executable, a.make_tiles, '--z1', str(W_ / 'p05.png'), '--z2', str(W_ / 'p025.png'), '--z4', str(W_ / 'p0125.png'), '--z8', str(W_ / 'p0625.png'),
                        '--out', str(T), '--jobs', str(a.jobs)])
    if r.returncode:
        sys.exit(f'make_tiles 실패({r.returncode})')
    import shutil
    shutil.copy(W_ / 'p025.png', W_ / 'bg.png')       # z2 전체(0.25 m)
    shutil.copy(W_ / 'p05.png', W_ / 'bg_1x.png')     # z1 과 같은 것
    log('tiles + bg.png + bg_1x.png')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('step', choices=['all', 'cache', 'lock', 'quant', 'maps', 'keys', 'tiles'])
    ap.add_argument('--raw')
    ap.add_argument('--pass', dest='pass_dir')
    ap.add_argument('--work', required=True)
    ap.add_argument('--ground-class', default=str(HERE / 'ground_class.png'))
    ap.add_argument('--osm', default=str(HERE.parent / 'redraw' / 'osm_raw.json'))
    ap.add_argument('--camera', default=str(HERE.parent / 'redraw' / 'hires' / 'camera' / 'nw45w_x8_0p0625_camera.json'))
    ap.add_argument('--crop')
    ap.add_argument('--colors', type=int, default=128)
    ap.add_argument('--make-tiles', default=str(HERE / 'make_tiles.py'))
    ap.add_argument('--jobs', type=int, default=16)
    ap.add_argument('--old', help='keys 비교용 옛 assets/redraw 폴더(bg.png, classes.png)')
    a = ap.parse_args()
    steps = ['cache', 'lock', 'quant', 'maps', 'tiles', 'keys'] if a.step == 'all' else [a.step]
    for s in steps:
        t = time.time()
        globals()['step_' + s](a)
        log(f'step {s} done in {time.time() - t:.0f}s')


if __name__ == '__main__':
    main()
