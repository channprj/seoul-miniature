#!/usr/bin/env python3
"""[10차] 지면·나무 잠금(밤섬 포함)·강물 단색(step lock 의 ground_water_full, 시험은 gtest --crop). 9차 판은 build_assets_yd_v9.py.
[8차] 지붕 잠금·랜드마크 벽 잠금(step lock 의 roof_lock_full, 시험은 rooftest). 7차 판은 build_assets_yd_v7.py.
[5차] 판 F(θ=180, 12.5 cm 직접 렌더 halfF/)로 바꿈: 깊이 기준 D0 를 meta 에서 읽고, 카메라·앵커·경로가 meta 의 판을 따른다.
잠금에 교량 잠금·호안/선착장 잠금을 더했다(step lock 의 zone). 4차(판 C) 원본은 build_assets_yd_v4.py.
[4차] 여의도 판 C(절반 해상도 12.5 cm/px) 조건 렌더 + 양식 패스 결과를 앱 자산(assets/yeouido/)으로 굽는다.
경복궁 판 gyeongbokgung/build_assets.py 를 본떴다. 픽셀 규격은 경복궁과 같다(캔버스 22016×13568, 지도 2752×1696 = 8×8 px 칸).
다른 점: 그림 px 12.5 cm, 지도 칸 1 m. 궁궐 바닥 잠금 대신 **강물 잠금**. 깊이 상수 1141 + v×0.05. 지면 분류는 half/classes_05m.png(0.5 m).

입력
  --raw   양식 결과 raw.png (RGB, 22016×13568). 자리표시 세트는 half/cond.png 를 그대로 넣는다.
  --pass  half/ 폴더: cond.png, cond_id.png(R·256+G), cond_z.png(깊이 z0 + v×step, meta.json), meta.json, classes_05m.png
  --scene scene.json, --movers C_movers.json (map.json 용)
단계(`all` = cache→lock→quant→maps→tiles→mapjson→keys)
  cache   큰 PNG 를 npy(mmap)로                         → work/cache/{raw,cond,ids,v,kcls}.npy
  lock    강물 잠금: 강물(지면 id 1 · 분류 5 · 수면 높이)에서 양식 결과가 기대색(cond 색 → raw 색 대응표)과 크게 다른 덩어리
          (지어낸 배·섬·다리)를 기대색 + 가까운 깨끗한 수면의 잔물결 결로 다시 칠한다. 교량·선착장·호안 id/분류와 그 둘레 5 px 는 건드리지 않는다.
          → work/cache/locked.npy, lock_stats.json, sheets/
          [8차] 지붕 잠금: tower·landmark 옥상은 전부 cond(포스터라이즈 + 1 px 어두운 선), 아파트 옥상·랜드마크 벽은 cond 와 크게 다른 덩어리만
          (랜드마크 벽은 40% 넘게 다르면 벽 전체). 끄기 --no-roof. 통계 lock_stats.json 의 roof, 시트 sheets/lock_roof*.png
  quant   128색 팔레트 양자화 + BOX 피라미드 → work/p0625.png(z8 = 12.5 cm 원본) p0125.png(z4) p025.png(z2) p05.png(z1 = 1 m)
  maps    depth_rg8.png, classes.png(앱 0–11), crown.png (2752×1696, 1 m 칸), id_stats.json
  tiles   make_tiles.py → work/tiles/ + bg.png(z2) + bg_1x.png(z1)
  mapjson map.json(이름, 크기, m/px, 깊이 상수, 카메라, 분류 사상표, 랜드마크 앵커, 이동 경로 px)
  keys    셰이더 색 키 통과율(참고)

  python build_assets_yd.py all --raw RAW --pass half --work WORK [--placeholder]
  python build_assets_yd.py lock --work WORK --crop x0,y0,x1,y1 [--inject] [--local-lut]   # 시험: 한 구역만 잠그고 시트만 쓴다
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as nd

Image.MAX_IMAGE_PIXELS = None
W, H, PX = 22016, 13568, 0.125
F = 8                       # 지도 칸(1 m) 하나 = 8×8 그림 px
MW, MH = W // F, H // F     # 2752 × 1696
KF = 4                      # 분류 맵(0.5 m) 한 칸 = 4×4 그림 px
D0, DSTEP = 1141.0, 0.05    # 앱 깊이 맵: depth = D0 + v×DSTEP (v = R·256+G, 65535 = 없음). 조건 렌더 깊이 패스와 같은 상수(임시 세트 _yd_interim 과도 같다). 경복궁은 2060 + v×0.02
WL = -1.8                   # 한강 수면 높이(gen_area)
HERE = Path(__file__).resolve().parent
T0 = time.time()
LUM = np.array([0.299, 0.587, 0.114], np.float32)


def log(*a):
    print(f'[{time.time() - T0:7.1f}s]', *a, flush=True)


# ───────────────────────── 카메라 · 높이 ─────────────────────────
class Cam:
    """판 C 카메라. 화면 좌표(m): u = P·EX, v = P·EY. 그림 px: X = (u − SX0)/PX, Y = (SY1 − v)/PX. 깊이 = (P − cam_ref)·VD."""

    def __init__(s, meta):
        sys.path.insert(0, str(HERE))
        import cam as ydcam
        b = meta['board_def']
        s.board = meta.get('board', 'C')
        s.ex, s.ey, s.vd = (np.asarray(v, np.float64) for v in ydcam.axes(b['theta']))
        s.theta, s.SX0, s.SY1 = b['theta'], b['SX0'], b['SY1']
        s.cl = np.array(meta['depth']['cam_ref'], np.float64)
        assert np.allclose(s.vd, meta['depth']['view_dir'], atol=1e-6)
        s.cvd = float(s.cl @ s.vd)
        s.z0, s.step = meta['depth']['z0'], meta['depth']['step']
        s.cx, s.cy = s.SX0 + W * PX / 2, s.SY1 - H * PX / 2      # 캔버스 가운데의 화면 좌표(앱 camera json 의 cx, cy)

    def proj(s, p):
        p = np.atleast_2d(np.asarray(p, np.float64))
        if p.shape[1] == 2:
            p = np.concatenate([p, np.zeros((len(p), 1))], 1)
        return np.stack([(p @ s.ex - s.SX0) / PX, (s.SY1 - p @ s.ey) / PX], 1)

    def unproj(s, X, Y, z=0.0):
        u = s.SX0 + X * PX - s.ex[2] * z
        v = s.SY1 - Y * PX - s.ey[2] * z
        x, y = np.linalg.solve(np.array([[s.ex[0], s.ex[1]], [s.ey[0], s.ey[1]]]), [u, v])
        return [float(x), float(y), float(z)]

    def ground_depth(s, py):
        """그림 행 py 중심의 z=0 평면 깊이"""
        v = s.SY1 - (np.asarray(py, np.float64) + 0.5) * PX
        return -v * s.ey[2] / s.vd[2] - s.cvd

    def height(s, v16, py0):
        """깊이 패스 값(2D, 행 py0 부터) → z=0 위 높이(m)"""
        d = s.z0 + v16.astype(np.float32) * s.step
        dg = s.ground_depth(np.arange(py0, py0 + d.shape[0])).astype(np.float32)[:, None]
        return (np.float32(s.vd[2]) * (d - dg)).astype(np.float32)

    def app_json(s):
        look = {135.0: '북동쪽에서 남서쪽을', 180.0: '북쪽에서 남쪽을(화면 위 = 남, 오른쪽 = 서)', 90.0: '동쪽에서 서쪽을'}.get(float(s.theta), f'방위 θ={s.theta} 로')
        return {'name': f'yeouido_{s.board}_theta{int(round(s.theta))}', 'theta_deg': s.theta, 'elevation_deg_from_horizontal': 35.0, 'blender_rot_x_deg': 55.0,
                'note': f'ortho, 카메라가 {look} 본다(θ={s.theta:g}), 고도 35°. 경복궁(nw45w)과 같은 식, 다른 방위',
                'res': [MW, MH], 'm_per_px_screen': PX * F, 'cx': s.cx, 'cy': s.cy, 'cam_location': s.cl.tolist(), 'view_dir': s.vd.tolist(),
                'screen_x_axis': s.ex.tolist(), 'screen_y_axis': s.ey.tolist(),
                'projection': 'px=(P.ex-cx)/m+W/2; py=H/2-(P.ey-cy)/m; depth=(P-cam_location).view_dir  (P = scene.json 지역 좌표 m, m = m_per_px_screen)',
                'sun_euler_deg': [50, 0, s.theta - 73]}


def rg16(path):
    a = np.asarray(Image.open(path).convert('RGB'))
    return a[..., 0].astype(np.uint16) * 256 + a[..., 1]


# ───────────────────────── cache ─────────────────────────
def step_cache(a):
    C = Path(a.work) / 'cache'
    C.mkdir(parents=True, exist_ok=True)
    P = Path(a.pass_dir)
    jobs = [('raw', lambda: np.asarray(Image.open(a.raw).convert('RGB')), (H, W)),
            ('cond', lambda: np.asarray(Image.open(P / 'cond.png').convert('RGB')), (H, W)),
            ('ids', lambda: rg16(P / 'cond_id.png'), (H, W)),
            ('v', lambda: rg16(P / 'cond_z.png'), (H, W)),
            ('kcls', lambda: np.asarray(Image.open(P / 'classes_05m.png')), (H // KF, W // KF))]
    for name, fn, shp in jobs:
        x = fn()
        assert x.shape[:2] == shp, (name, x.shape, shp)
        np.save(C / f'{name}.npy', x)
        log('cache', name, x.shape, x.dtype)
        del x
    meta = json.load(open(P / 'meta.json'))
    assert abs(meta.get('render_px_m', 0) - PX) < 1e-9 and meta['size'] == [W, H], 'half/meta.json 이 12.5 cm 22016×13568 이 아니다'
    (C / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False))
    (C / 'inputs.json').write_text(json.dumps({'raw': str(a.raw), 'pass': str(P), 'placeholder': bool(a.placeholder)}, ensure_ascii=False, indent=1))


def cache(a, name):
    return np.load(Path(a.work) / 'cache' / f'{name}.npy', mmap_mode='r')


def load_meta(a):
    global D0
    m = json.loads((Path(a.work) / 'cache' / 'meta.json').read_text())
    D0 = float(m['depth']['z0'])            # [5차] 깊이 기준은 판마다 다르다(C 1141). 앱 깊이 맵은 조건 렌더 깊이 패스와 같은 상수를 쓴다
    assert abs(m['depth']['step'] - DSTEP) < 1e-12
    return m


def up(k, y0, y1):
    """분류 맵(0.5 m)을 그림 행 y0..y1 로 키운다"""
    return np.repeat(np.repeat(np.asarray(k[y0 // KF:-(-y1 // KF)]), KF, 0), KF, 1)[y0 % KF:y0 % KF + (y1 - y0), :W]


# ───────────────────────── lock(강물 잠금) ─────────────────────────
PARAMS = {'thr': 42.0, 'win': 9, 'keep_px': 5, 'open_px': 3, 'min_px': 400, 'grow_px': 4, 'tex': 0.7, 'max_px': 40000000, 'wl_tol': 0.25}


def sq(m, r, fn):
    return fn(m.view(np.uint8) if m.dtype == bool else m, size=2 * r + 1).astype(bool)


def water_mask(ids, v, kc, y0, cam, P):
    """강물 픽셀: 지면 id 1 이고, 분류 5(강물; 0.5 m 칸 가장자리는 한 칸 넓혀 본다)이고, 높이가 수면(WL ± tol)인 곳.
    교량·선착장·부잔교·배 같은 물체 id, 호안 경사(수면보다 높음)는 들어가지 않는다."""
    hgt = cam.height(v, y0)
    return (ids == 1) & kc & (np.abs(hgt - WL) < P['wl_tol'])


def river_cells(kcls):
    return nd.maximum_filter((np.asarray(kcls) == 5).view(np.uint8), size=3).astype(bool)


def color_lut(cond, raw, mask, step=3):
    """조건 렌더 색 → 양식 결과 색 대응표(채널당 5·4·3 비트 칸, 한 번 깎은 평균). 지어낸 물체는 소수라 평균을 끌지 못한다."""
    m = mask[::step, ::step]
    return lut_from_samples(cond[::step, ::step][m], raw[::step, ::step][m])


def lut_from_samples(c, r, min_cnt=40):
    c = np.asarray(c).astype(np.int32)
    r = np.asarray(r).astype(np.float64)
    luts = []
    for bits in (5, 4, 3):
        sh = 8 - bits
        key = ((c[:, 0] >> sh) << (2 * bits)) | ((c[:, 1] >> sh) << bits) | (c[:, 2] >> sh)
        nb = 1 << (3 * bits)
        cnt = np.bincount(key, minlength=nb)
        mean = np.stack([np.bincount(key, r[:, i], nb) for i in range(3)], 1) / np.maximum(cnt, 1)[:, None]
        ok = np.sqrt(((r - mean[key]) ** 2).sum(1)) < 60
        cnt2 = np.bincount(key[ok], minlength=nb)
        mean2 = np.stack([np.bincount(key[ok], r[ok, i], nb) for i in range(3)], 1) / np.maximum(cnt2, 1)[:, None]
        luts.append((bits, np.where(cnt2[:, None] >= min_cnt, mean2, np.nan).astype(np.float32)))
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


def chroma_dist(a, b):
    la, lb = a @ LUM, b @ LUM
    dc = (a - la[..., None]) - (b - lb[..., None])
    return np.sqrt((la - lb) ** 2 + 3.0 * (dc ** 2).sum(-1))


def texture(raw, E, clean, fill, T=96):
    """채울 자리의 잔물결 결: 가까운 깨끗한 수면 칸(T×T, 8방향 최대 4칸)의 잔무늬(양식 결과 − 기대색)를 옮겨 붙인다 → (h,w,3)"""
    res = np.clip(raw.astype(np.float32) - E, -40, 40)
    h, w = fill.shape
    out = np.zeros((h, w, 3), np.float32)
    ny, nx = -(-h // T), -(-w // T)
    cf = np.zeros((ny, nx), np.float32)
    ff = np.zeros((ny, nx), bool)
    for j in range(ny):
        for i in range(nx):
            ff[j, i] = fill[j * T:(j + 1) * T, i * T:(i + 1) * T].any()
    if not ff.any():
        return out
    for j in range(ny):
        for i in range(nx):
            cf[j, i] = clean[j * T:(j + 1) * T, i * T:(i + 1) * T].mean()
    for j, i in zip(*np.nonzero(ff)):
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
        hh, ww = fill[j * T:(j + 1) * T, i * T:(i + 1) * T].shape
        out[j * T:j * T + hh, i * T:i * T + ww] = src[:hh, :ww]
    return out


def lock_region(raw, cond, ids, v, kc, y0, cam, P, luts):
    """한 구역을 잠근다(배열은 그 구역 크기) → (새 그림, 바꾼 마스크, 정보, 거리, 강물 마스크)"""
    water = water_mask(ids, v, kc, y0, cam, P)
    h = raw.shape[0]
    ds = np.zeros(raw.shape[:2], np.float32)
    S, HALO = 1024, 16
    for s0 in range(0, h, S):                      # 거리는 띠로 나눠 계산(메모리)
        a0, a1 = max(0, s0 - HALO), min(h, s0 + S + HALO)
        d = chroma_dist(raw[a0:a1].astype(np.float32), lut_apply(luts, cond[a0:a1]))
        d[~water[a0:a1]] = 0
        ds[s0:min(h, s0 + S)] = nd.uniform_filter(d, P['win'])[s0 - a0:s0 - a0 + min(S, h - s0)]
    protect = sq(~water, P['keep_px'], nd.maximum_filter)        # 강물이 아닌 것(교량·교각·선착장·호안·강변)의 가장자리 보존
    m = (ds > P['thr']) & water & ~protect
    m = sq(sq(m, P['open_px'], nd.minimum_filter), P['open_px'], nd.maximum_filter) & m
    lab, n = nd.label(m)
    big = []
    blob = np.zeros(m.shape, bool)
    nb = 0
    if n:
        sz = np.bincount(lab.ravel(), minlength=n + 1)
        keep = (sz >= P['min_px']) & (sz <= P['max_px'])
        keep[0] = False
        big = [(int(i), int(sz[i])) for i in np.nonzero(sz > P['max_px'])[0] if i]
        blob = keep[lab]
        nb = int(keep.sum())
    del lab
    fill = sq(blob, P['grow_px'], nd.maximum_filter) & water & ~protect
    if fill.any():
        fill = nd.binary_fill_holes(fill) & water & ~protect
    out = np.array(raw)
    clean = water & ~fill & ~protect & (ds < P['thr'] * 0.5)
    S2, PAD = 1920, 480
    for s0 in range(0, h, S2):
        s1 = min(h, s0 + S2)
        if not fill[s0:s1].any():
            continue
        a0, a1 = max(0, s0 - PAD), min(h, s1 + PAD)
        E = lut_apply(luts, cond[a0:a1])
        tex = texture(raw[a0:a1], E, clean[a0:a1], fill[a0:a1])
        f = fill[s0:s1]
        out[s0:s1][f] = np.clip(E[s0 - a0:s1 - a0][f] + tex[s0 - a0:s1 - a0][f] * P['tex'], 0, 255).astype(np.uint8)
    info = {'blobs': nb, 'fill_px': int(fill.sum()), 'water_px': int(water.sum()), 'skipped_huge_components': big}
    return out, fill, info, ds, water


# ───────────────────────── lock(교량 · 호안/선착장 잠금, 5차) ─────────────────────────
# 양식 패스가 다리 위에 상가를 짓고 선착장을 도로+건물로 바꾼 시험 결과(ydt/ydu_riv.png) 때문에 더했다.
#  bridge: 교량 물체 id(meta kind 'bridge:*' — 상판·교각·난간) 픽셀.  bank: 지면 id 1 이고 분류 13(호안)·16(선착장·부잔교)인 픽셀.
#  구역마다 cond 색 → raw 색 대응표를 따로 만들고, 기대색과 크게 다른 덩어리를 **기대색**으로 되돌린다(차선·난간은 cond 에 있으므로 기대색에 그대로 남는다. 결은 붙이지 않는다).
#  되돌린 덩어리에 붙은 강물 가장자리(강물 잠금이 보존한 둘레 5 px)는 강물 기대색으로 메운다.
# [6차] 5차 방식(9 px 평균 거리 > thr 인 곳 전부)은 양식 패스가 그린 난간·횡단보도·차선까지 민무늬 기대색으로 덮었다. 경복궁 build_assets.py 의 덩어리 방식대로
#  '속이 찬 덩어리'만 되돌린다: 픽셀 거리(3 px 평균) > thr → 닫기(close_px, 창문 틈 메움) → 열기(core_px: 9×9 px = 1.1 m 보다 가는 띠·줄무늬는 사라진다 — 난간, 차선, 횡단보도)
#  → 성분(min_px 이상) → grow_px 만큼 키우되 5차의 느슨한 마스크(9 px 평균 거리 > thr) 안에서만 채움. 덩어리에서 grow_px 넘게 떨어진 난간·횡단보도는 남는다.
# [11차] 교량: 10차의 '강 교량 전체 되돌림'을 끄고(난간·차선 픽셀아트가 렌더 결이 됐다) 덩어리 방식으로 돌아가되, r4 서강·마포 상판의 회색 상가 조각이 잡히게
#  임계 42→24, 열기 core 2→4(9×9 px = 1.1 m 보다 가는 난간·차선은 덩어리가 되지 않는다), min 200→400. 벽돌색 씨앗(ghost_seeds)에 닿는 덩어리는 크기 조건 없이.
ZPARAMS = {'bridge': {'thr': 24.0, 'win': 9, 'close_px': 1, 'core_px': 4, 'min_px': 400, 'grow_px': 10},
           'bank': {'thr': 42.0, 'win': 9, 'close_px': 1, 'core_px': 4, 'min_px': 400, 'grow_px': 10}, 'ring_px': 8}
ZCOL = {'bridge': (255, 0, 255), 'bank': (255, 200, 0), 'ring': (0, 255, 255), 'ghost': (255, 0, 0), 'span': (120, 0, 255)}


ZWHOLE = None       # [10차] 강 교량 id 표(step_lock 이 river_bridge_lut 로 채운다). None 이면 덩어리만


def river_bridge_lut(ids, kcls, blut, frac=0.3):
    """교량 id 가운데 화소의 frac 이상이 강물(분류 5, 3칸 넓힘) 위·옆에 있는 것 → 표. 상판 위에 지어낸 상가가 덩어리 방식으로 다 지워지지 않아 전체를 기대색으로 되돌린다"""
    i4 = np.asarray(ids[2::4, 2::4])
    near = nd.maximum_filter((np.asarray(kcls) == 5).view(np.uint8), size=41).astype(bool)
    b = blut[i4]
    tot = np.bincount(i4[b], minlength=65536)
    nw = np.bincount(i4[b & near], minlength=65536)
    return (tot > 0) & (nw >= frac * tot)


def bridge_lut(meta):
    b = np.zeros(65536, bool)
    for k, t in meta['ids'].items():
        if t.split(':')[0] == 'bridge':
            b[int(k)] = True
    return b


def zone_masks(ids, kfull, blut):
    return {'bridge': blut[ids], 'bank': (ids == 1) & ((kfull == 13) | (kfull == 16))}


def zone_lock_region(r, c, ids, v, kfull, rcu, y0, cam, P, zluts, wluts, blut, ZP=ZPARAMS):
    """한 구역(배열은 그 구역 크기)의 교량·호안/선착장을 잠근다 → (새 그림, {구역: 바꾼 마스크}, [덩어리 (구역, px, cy, cx)])"""
    out = np.array(r)
    fills, blobs = {}, []
    zm = zone_masks(ids, kfull, blut)
    anyf = np.zeros(ids.shape, bool)
    seeds = ghost_seeds(np.asarray(r), np.asarray(c), ids, kfull, HOSTL)[0] if HOSTL is not None else None      # [11차] 상판 위 지어낸 상가의 벽돌 씨앗
    fills['ghost'] = np.zeros(ids.shape, bool)
    for zn, z in zm.items():
        fills[zn] = np.zeros(ids.shape, bool)
        if not z.any() or zluts.get(zn) is None:
            continue
        p = ZP[zn]
        E = lut_apply(zluts[zn], np.asarray(c)[z])
        d = np.zeros(ids.shape, np.float32)
        d[z] = chroma_dist(np.asarray(r)[z].astype(np.float32), E)
        loose = (nd.uniform_filter(d, p['win']) > p['thr']) & z
        m = (nd.uniform_filter(d, 3) > p['thr']) & z
        if p.get('close_px'):
            m = sq(sq(m, p['close_px'], nd.maximum_filter), p['close_px'], nd.minimum_filter) & z
        m = sq(sq(m, p['core_px'], nd.minimum_filter), p['core_px'], nd.maximum_filter) & m
        fs = seeds & z if seeds is not None else None
        if fs is not None and fs.any():
            m |= fs
        lab, n = nd.label(m)
        sz = np.bincount(lab.ravel(), minlength=n + 1)
        keep = sz >= p['min_px']
        fk = np.zeros(n + 1, bool)
        if fs is not None and fs.any():
            fk = np.bincount(lab[fs], minlength=n + 1) > 0
            fk[0] = False
            keep |= fk
        keep[0] = False
        whole = ZWHOLE[ids] & z if zn == 'bridge' and ZWHOLE is not None else None     # [10차] 강을 건너는 교량은 id 화소 전부를 기대색으로
        if not keep.any() and (whole is None or not whole.any()):
            continue
        if keep.any():
            for i, (cy_, cx_) in zip(np.nonzero(keep)[0], nd.center_of_mass(m, lab, np.nonzero(keep)[0])):
                blobs.append((zn, int(sz[i]), float(cy_), float(cx_)))
        f = sq(keep[lab], p['grow_px'], nd.maximum_filter) & (loose | keep[lab])
        if fk.any():
            gh = grow_up(sq(fk[lab], BRICK['grow_px'], nd.maximum_filter), BRICK['roof_up']) & loose
            f |= gh
            fills['ghost'] |= (gh | fk[lab]) & z
        f = nd.binary_fill_holes(f) & z
        if whole is not None:
            f |= whole
        Ef = np.zeros(ids.shape + (3,), np.float32)
        Ef[z] = E
        out[f] = np.clip(Ef[f], 0, 255).astype(np.uint8)
        fills[zn] = f
        anyf |= f
    fills['ring'] = np.zeros(ids.shape, bool)
    if anyf.any():
        ring = sq(anyf, ZP['ring_px'], nd.maximum_filter) & water_mask(ids, v, rcu, y0, cam, P)
        if ring.any():
            out[ring] = np.clip(lut_apply(wluts, np.asarray(c)[ring]), 0, 255).astype(np.uint8)
            fills['ring'] = ring
    return out, fills, blobs


# [12차] 교량 경간 단위 되돌림. r6 서강대교: 양식 패스가 상판 옆에 다른 도로·광장을 그려 덩어리 방식이 상판의 일부(광장과 겹친 곳)만 기대색으로 바꿨다 →
#  상판이 한 칸 어두운 판 + raw 의 엇갈린 차선이 흰 점으로 흩어짐. 덩어리가 닿은 교량 id 는 그 경간(교각 사이) 전체를 cond 기대색으로 바꾸고(차선은 cond 의 것),
#  색은 그 id 의 깨끗한(채우지 않은) 화소에서 잰 raw − 기대색 중앙값만큼 옮겨 이웃 경간과 밝기를 맞춘다.
#  경간: 깊이 패스로 화소의 3D 점(지도 x·y, 높이)을 되살려 상판 id 의 긴 축(t)에 투영. 같은 상자 안 교량 화소 중 상판 윗면보다 pier_dz 넘게 낮고
#  상판 폭(s)에서 side_m(쌍둥이 상판 몫) 안에 있는 것 = 교각 → t 로 묶은 중심이 경간 경계. 교각이 없으면 fallback_m 간격.
#  교각 사이가 max_span_m 넘으면 fallback_m 이하로 나눈다. 고른 경간 안에서도 가장자리 rim_px 띠(난간)는 덩어리가 닿지 않았으면 raw.
#  경간 고르기: 상판 안쪽(inner_px 깎음)에서 덩어리 채움이 hit_px 이상이고 그 경간 안쪽의 hit_frac 이상(난간 줄을 따라 자란 채움은 세지 않는다).
#  hit_px 를 낮게(60) 둔 까닭: 채움 조각이 몇 개만 있어도 그 경간은 raw 차선이 끊겨 흰 점으로 남는다(r6 서강대교 아래 경간들).
SPAN = {'on': True, 'min_px': 400, 'pier_dz': 3.5, 'pier_gap_m': 3.0, 'pier_min_px': 60, 'side_m': 12.0, 'inner_px': 8, 'hit_px': 60, 'hit_frac': 0.0, 'fallback_m': 40.0, 'shift_m': 60.0, 'gap_spans': 2, 'rim_px': 6, 'max_span_m': 60.0,
        'shift_clip': 25.0, 'shift_tol': 30.0, 'clean_min': 2000, 'pad': 96}


def _map_xy(cam, X, Y, h):
    """그림 화소(X, Y; 정수 좌표) + 높이 h(m) → 지도 좌표(m)"""
    A = np.linalg.inv(np.array([[cam.ex[0], cam.ex[1]], [cam.ey[0], cam.ey[1]]]))
    u = cam.SX0 + (X + 0.5) * PX - cam.ex[2] * h
    vv = cam.SY1 - (Y + 0.5) * PX - cam.ey[2] * h
    return A[0, 0] * u + A[0, 1] * vv, A[1, 0] * u + A[1, 1] * vv


def bridge_span_one(k, r, c, idb, vb, y0, x0, cam, blut, zl, fm, SP=SPAN, dbg=None):
    """교량 id k 하나(배열은 그 상자, 원점 y0·x0). fm = 덩어리 채움 마스크 → (바꿀 마스크, 새 색 (n,3) uint8, 정보) 또는 None"""
    m = idb == k
    if not (m & fm).any():
        return None
    h = cam.height(vb, y0)
    ok = vb != 65535
    bm = blut[idb] & ok
    yy, xx = np.nonzero(bm)
    mx, my = _map_xy(cam, xx + x0, yy + y0, h[yy, xx])
    isk = m[yy, xx]
    P = np.stack([mx[isk], my[isk]], 1)
    cen = P.mean(0)
    w_, V = np.linalg.eigh(np.cov((P - cen).T))
    ax, nx_ = V[:, 1], V[:, 0]
    t = (np.stack([mx, my], 1) - cen) @ ax
    sv = (np.stack([mx, my], 1) - cen) @ nx_
    tk, sk, hk = t[isk], sv[isk], h[yy, xx][isk]
    t0, t1 = float(tk.min()), float(tk.max())
    nb = int(np.ceil(t1 - t0)) + 1
    bi = np.clip((tk - t0).astype(int), 0, nb - 1)
    top = np.full(nb, -1e9, np.float32)
    np.maximum.at(top, bi, hk)
    good = top > -1e8
    if good.any():           # 빈 칸은 가까운 칸 값
        idx = nd.distance_transform_edt(~good, return_distances=False, return_indices=True)[0]
        top = top[idx]
    s_lo, s_hi = np.percentile(sk, 2) - SP['side_m'], np.percentile(sk, 98) + SP['side_m']
    ta = np.clip((t - t0).astype(int), 0, nb - 1)
    inside = (t >= t0 - 1) & (t <= t1 + 1) & (sv >= s_lo) & (sv <= s_hi)
    pier = inside & (h[yy, xx] < top[ta] - SP['pier_dz'])
    pt = np.sort(t[pier])
    piers = []
    if len(pt):
        cuts = np.nonzero(np.diff(pt) > SP['pier_gap_m'])[0] + 1
        for g in np.split(pt, cuts):
            if len(g) >= SP['pier_min_px']:
                piers.append(float(np.median(g)))
    piers = [p for p in piers if t0 + 1 < p < t1 - 1]
    if piers:
        bounds = [t0 - 1] + piers + [t1 + 1]
    else:
        n_ = max(1, int(round((t1 - t0) / SP['fallback_m'])))
        bounds = list(np.linspace(t0 - 1, t1 + 1, n_ + 1))
    bb = [bounds[0]]           # 교각 사이가 max_span_m 보다 길면(육상 고가·램프는 교각이 가려 잘 안 잡힌다) fallback_m 이하 조각으로
    for b0, b1 in zip(bounds[:-1], bounds[1:]):
        if b1 - b0 > SP['max_span_m']:
            n_ = int(np.ceil((b1 - b0) / SP['fallback_m']))
            bb += list(np.linspace(b0, b1, n_ + 1)[1:])
        else:
            bb.append(b1)
    bounds = bb
    seg = np.searchsorted(np.asarray(bounds[1:-1]), tk)             # 상판 화소의 경간 번호
    segimg = np.full(m.shape, -1, np.int32)
    segimg[yy[isk], xx[isk]] = seg
    timg = np.full(m.shape, np.nan, np.float32)
    timg[yy[isk], xx[isk]] = tk
    inner = sq(m, SP['inner_px'], nd.minimum_filter)                  # 난간·가장자리 줄(덩어리 grow 가 닿는 곳)이 아닌 상판 안쪽만 센다
    hits = np.bincount(segimg[inner & fm], minlength=len(bounds) - 1)
    size = np.maximum(np.bincount(segimg[inner], minlength=len(bounds) - 1), 1)
    sel = np.nonzero((hits >= SP['hit_px']) & (hits >= SP['hit_frac'] * size))[0]
    if len(sel) > 1:            # 고른 경간 사이에 낀 경간(gap_spans 개 이하)도 — 바꾼 경간 사이 raw 한 칸이 밝은 판으로 남았다
        ss = set(int(i) for i in sel)
        for i0, i1 in zip(sel[:-1], sel[1:]):
            if 1 < i1 - i0 <= SP['gap_spans'] + 1:
                ss.update(range(int(i0) + 1, int(i1)))
        sel = np.array(sorted(ss))
    if dbg is not None:
        dbg.update(seg=segimg, inner=inner, bounds=bounds, hits=hits, size=size)
    if not len(sel):
        return None
    R = m & np.isin(segimg, sel)
    if SP['rim_px']:            # 상판 가장자리 띠(난간)는 덩어리가 닿지 않은 곳이면 raw 픽셀아트 그대로 — 10차 '교량 전체'에서 난간이 렌더 결이 된 것을 되풀이하지 않게
        outer = sq(~blut[idb], SP['rim_px'], nd.maximum_filter)      # 바깥 가장자리만(쌍둥이 상판 사이 중앙분리대 쪽은 아님)
        R &= ~outer | sq(fm, 4, nd.maximum_filter)
    E = lut_apply(zl['bridge'], c[R]) if zl.get('bridge') is not None else c[R].astype(np.float32)
    clean = m & ~R & ~sq(fm, 4, nd.maximum_filter)
    near = np.zeros(m.shape, bool)              # 색 이동은 바꾼 경간 앞뒤 shift_m 안의 깨끗한 화소에서(교량 raw 색이 길이 따라 달라 id 전체 중앙값은 한 칸 어긋났다)
    for i in sel:
        near |= (timg >= bounds[i] - SP['shift_m']) & (timg <= bounds[i + 1] + SP['shift_m'])
    if (clean & near).sum() >= SP['clean_min']:
        clean &= near
    shift = np.zeros(3, np.float32)
    if clean.sum() >= SP['clean_min']:      # 밝기만(세 채널 같은 값): 깨끗한 화소 중 기대색과 가까운 것(상판다운 것)만 — raw 의 물·광장 조각이 섞여 색이 파랗게 끌리지 않게
        ec = lut_apply(zl['bridge'], c[clean]) if zl.get('bridge') is not None else c[clean].astype(np.float32)
        rc_ = r[clean].astype(np.float32)
        okc = chroma_dist(rc_, ec) < SP['shift_tol']
        if okc.sum() >= SP['clean_min']:
            shift[:] = np.clip(np.median(rc_[okc] @ LUM - ec[okc] @ LUM), -SP['shift_clip'], SP['shift_clip'])
    new = np.clip(E + shift, 0, 255).astype(np.uint8)
    info = {'id': int(k), 'len_m': round(t1 - t0, 1), 'piers': len(piers), 'spans': len(bounds) - 1, 'spans_replaced': [int(i) for i in sel],
            'px': int(R.sum()), 'hit_px': [int(hits[i]) for i in sel], 'hit_frac': [round(float(hits[i] / size[i]), 3) for i in sel],
            'all_hits': [[int(hits[i]), int(size[i])] for i in range(len(hits)) if hits[i]], 'shift': [round(float(x), 1) for x in shift], 'clean_px': int(clean.sum())}
    return R, new, info


def bridge_spans(raw, cond, ids, v, cam, blut, zl, fm_get, kset, SP=SPAN):
    """전체(또는 t11 구역): kset 의 교량 id 마다 상자(i4 기준)를 잡아 bridge_span_one → [(ys, xs, R, new, info)]. fm_get(ys, xs) = 그 상자의 덩어리 채움 마스크"""
    i4 = np.asarray(ids[::4, ::4])
    lab = np.where(np.isin(i4, list(kset)), i4, 0).astype(np.int32)
    res = []
    for k, sl in enumerate(nd.find_objects(lab), 1):
        if sl is None or k not in kset:
            continue
        p = SP['pad']
        ys = slice(max(0, sl[0].start * 4 - p), min(H, sl[0].stop * 4 + p))
        xs = slice(max(0, sl[1].start * 4 - p), min(W, sl[1].stop * 4 + p))
        idb = np.asarray(ids[ys, xs])
        o = bridge_span_one(k, np.asarray(raw[ys, xs]), np.asarray(cond[ys, xs]), idb, np.asarray(v[ys, xs]), ys.start, xs.start, cam, blut, zl, fm_get(ys, xs), SP)
        if o is not None:
            res.append((ys, xs) + o)
            log('bridge span', o[2])
    return res


def zone_luts(raw, cond, ids, kcls, blut, rows=None, cols=slice(None), step=3, B=2048):
    """구역별 cond → raw 대응표(전 구역 표본을 띠로 모음)"""
    y0, y1 = rows or (0, ids.shape[0])
    smp = {'bridge': ([], []), 'bank': ([], [])}
    for s0 in range(y0, y1, B):
        s1 = min(y1, s0 + B)
        s0a = s0 + (-s0) % step
        zm = zone_masks(np.asarray(ids[s0a:s1:step, cols])[:, ::step], up(kcls, s0, s1)[s0a - s0::step, cols][:, ::step], blut)
        cb, rb = np.asarray(cond[s0a:s1:step, cols])[:, ::step], np.asarray(raw[s0a:s1:step, cols])[:, ::step]
        for zn, z in zm.items():
            if z.any():
                smp[zn][0].append(cb[z])
                smp[zn][1].append(rb[z])
    out = {}
    for zn, (cs, rs) in smp.items():
        out[zn] = lut_from_samples(np.concatenate(cs), np.concatenate(rs)) if cs else None
        log('zone lut', zn, 'samples', sum(len(x) for x in cs), 'bins', {b: int((~np.isnan(l[:, 0])).sum()) for b, l in (out[zn] or [])})
    return out


# ───────────────────────── [11차] 지어낸 건물 직접 검출 · 정자 · 벽 면 분할 ─────────────────────────
# 10차 지면 잠금 뒤에도 둔치에 지어낸 집이 남은 까닭(dunchi2): cond 의 공원 정자(park_pavilion: 연못가 정자, 흰 천막) 위에 양식 패스가 벽돌집을 그렸고,
#  지면 잠금은 물체 id 둘레 6 px 를 보존하므로 정자 id + 둘레의 집은 그대로·반쯤 남았다. 연못(분류 17)은 잠금 구역 밖이라 연못 자리에 그린 광장도 남았다.
#  (1) 벽돌 씨앗: 건물 id 가 아닌 곳(지면·나무·교량·정자)에서 raw 가 벽돌색(적갈색)이고 cond 는 그 둘레 3 px 안에 벽돌색이 없는 화소 → 열기 → 300 px 이상 성분.
#      건물 id(저층·아파트·타워·랜드마크·역) 둘레 10 px 는 뺀다(cond 에 있는 저층 벽돌집의 처마). 지면·교량 잠금에서 이 씨앗에 닿는 덩어리는 크기·core 조건 없이 채우고,
#      지붕은 벽 위에 그려지므로 씨앗 위로 roof_up px 까지 느슨한 마스크 안을 같이 채운다.
#  (2) 정자: 화소의 brick 이상이 씨앗 벽돌색이거나 far 이상이 cond 와 크게 다르면 '지어낸 집이 된 정자' → 정자 id 를 cond(포스터라이즈)로 바꾸고 둘레 보존을 푼다.
#  (3) 벽 면 분할(랜드마크 벽·아파트 벽): 깊이 패스의 가로 기울기(면의 방향)가 같은 이어진 화소 = 한 면. 일부만 바꿀 때는 면 전체를 바꾸거나 안 바꾼다.
BRICK = {'h': (3.0, 28.0), 's': (0.33, 0.82), 'v': (0.18, 0.80), 'cond_px': 3, 'open_px': 2, 'min_px': 300, 'bld_px': 10, 'adj_px': 28, 'adj_frac': 0.3,
         'roof_up': 56, 'grow_px': 12, 'near_px': 40, 'near_thr': 20.0, 'dark': 14.0, 'comp_px': 64, 'ring_px': 24, 'ring_min': 200, 'var': 14.0, 'var_road': 255.0, 'ring_tol': 40.0,
         'ring_lut': True}
HOST_BLD = 9
PAV = {'brick': 0.12, 'far': 0.5, 'thr': 60.0, 'colors': 8}
FACE = {'jump': 1.0, 'win': 9, 'tol': 0.04, 'merge': 0.025, 'min_px': 800, 'all': 0.3, 'blob': 0.2, 'apt_brick': 0.2, 'apt_min_px': 1500,
        'rec_frac': 0.02, 'rec_close': 2, 'rec_light': 140.0, 'rec_k': (0.62, 1.15), 'rec_face': True}
# [12차] 랜드마크 5차 재질(툰 3단 음영·창 격자, halfF3)을 입힌 건물: 벽 전체를 cond 로. 이름(meta ids 의 종류) 또는 id. 페어몬트(15239)는 종류가 tower 라 id 로
MAT_LM_KINDS = ('landmark:parc1', 'landmark:parc2', 'landmark:63', 'landmark:63_podium', 'landmark:ifc1', 'landmark:ifc2', 'landmark:ifc3', 'landmark:conrad',
                'landmark:lg', 'landmark:fki', 'landmark:fki_hall', 'landmark:assembly', 'landmark:hyundai', 'landmark:KRX한국거래소서울사무소', 'landmark:church')
MAT_LM_IDS = (15239,)
MATLM = None        # mat_lm_lut(meta); --mat-lm 일 때 step_lock·t11 이 채운다


def mat_lm_lut(meta):
    t = np.zeros(65536, bool)
    for k, kind in meta['ids'].items():
        if kind in MAT_LM_KINDS:
            t[int(k)] = True
    for k in MAT_LM_IDS:
        if str(k) in meta['ids']:
            t[k] = True
    return t


def set_mat_lm(a, meta):
    """--mat-lm auto|on|off (auto = cache 의 pass 가 halfF3 이후일 때만 켠다) → 전역 MATLM, RPARAMS['mcolors']"""
    global MATLM
    mode = getattr(a, 'mat_lm', 'auto')
    if mode == 'auto':
        try:
            ps = json.loads((Path(a.work) / 'cache' / 'inputs.json').read_text())['pass']
        except Exception:
            ps = str(getattr(a, 'pass_dir', ''))
        mode = 'on' if Path(ps).name not in ('half', 'halfF', 'halfF2', 'halfF_pre_lm', 'halfF_pre_roof') else 'off'
    MATLM = mat_lm_lut(meta) if mode == 'on' else None
    if getattr(a, 'mcolors', 0):
        RPARAMS['mcolors'] = a.mcolors
    log('mat-lm', mode, int(MATLM.sum()) if MATLM is not None else 0, 'ids, mcolors', RPARAMS.get('mcolors', RPARAMS['wcolors']))
HOSTL = None        # host_lut(meta); step_lock·t11 이 채운다


def brick_mask(rgb, P=BRICK):
    """적갈색(벽돌·붉은 벽) 화소: 색상 3–28°, 채도·명도 범위"""
    a = np.asarray(rgb).astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx = r
    d = r - b
    h = 60 * (g - b) / np.maximum(d, 1e-3)
    s = d / np.maximum(mx, 1e-3)
    v = mx / 255
    return (r >= g) & (g >= b) & (h >= P['h'][0]) & (h <= P['h'][1]) & (s >= P['s'][0]) & (s <= P['s'][1]) & (v >= P['v'][0]) & (v <= P['v'][1])


def host_lut(meta):
    """id → 1 지면 / 2 나무 / 3 교량 / 4 정자 / 9 건물(저층·아파트·타워·랜드마크·역)"""
    hl = np.zeros(65536, np.uint8)
    hl[1] = 1
    for k, t in meta['ids'].items():
        hl[int(k)] = {'ground': 1, 'tree': 2, 'bridge': 3, 'park_pavilion': 4}.get(t.split(':')[0], HOST_BLD)
    return hl


SHAPE = {'thr': 55.0, 'open_px': 4, 'min_px': 1500, 'edge': 40.0, 'edge_frac': 0.10, 'dark': 60.0, 'dark_frac': 0.015}
GKIND = ('brick', 'light', 'gray', 'other')


def ghost_seeds(r, c, ids, kfull, hl, P=BRICK, d=None, SP=SHAPE):
    """건물 id 가 없는 곳의 지어낸 건물 → (씨앗 마스크, [(px, cy, cx, host, 색 종류)])
    (가) 벽돌 씨앗: raw 적갈색 & cond 둘레 3 px 에 적갈색 없음 → 열기 → 300 px 이상.
    (나) [11차 리드 요청] 모양 씨앗(d = 기대색 거리를 줄 때만; 지면·나무·정자 자리): 기대색과 크게 다르고(3 px 평균 > thr) 녹색이 아닌 화소 → 9×9 열기 → 1500 px 이상이고
         경계(밝기 차 > edge 인 화소; 창·외곽선)가 edge_frac 이상, 어두운 선(밝기 < dark)이 dark_frac 이상인 덩어리 — 흰 상가·회색 빌라·노란 집.
    둘 다 건물 id 둘레 bld_px 는 빼고, 덩어리의 adj_frac 넘게 건물 adj_px 안이면(건물을 id 밖으로 넘겨 그린 것) 버린다. 색 종류: 벽돌/밝은색/회색/기타."""
    host = hl[ids]
    host[(ids == 1) & (kfull == 5)] = 0            # 강물은 강물 단색이 덮는다
    bld = host == HOST_BLD
    near = sq(bld, P['bld_px'], nd.maximum_filter)
    adj = sq(bld, P['adj_px'], nd.maximum_filter)      # 건물 바로 옆 덩어리는 양식 패스가 그 건물을 id 밖으로 넘겨 그린 것 — 지어낸 집이 아니다
    bm = brick_mask(r, P)
    s = bm & ~sq(brick_mask(c, P), P['cond_px'], nd.maximum_filter) & (host > 0) & (host < HOST_BLD) & ~near
    s = sq(sq(s, P['open_px'], nd.minimum_filter), P['open_px'], nd.maximum_filter) & s
    out = np.zeros(ids.shape, bool)

    def _keep(m, min_px, extra=None):
        lab, n = nd.label(m)
        if not n:
            return np.zeros(m.shape, bool)
        sz = np.bincount(lab.ravel(), minlength=n + 1)
        k = (sz >= min_px) & (np.bincount(lab[m & adj], minlength=n + 1) < P['adj_frac'] * sz)
        if extra is not None:
            k &= extra(lab, n, sz)
        k[0] = False
        return k[lab]
    out |= _keep(s, P['min_px'])
    if d is not None:
        rf = np.asarray(r).astype(np.float32)
        lum = rf @ LUM
        green = (rf[..., 1] > rf[..., 0] + 8) & (rf[..., 1] > rf[..., 2] + 8)
        cand = (nd.uniform_filter(d, 3) > SP['thr']) & np.isin(host, (1, 2, 4)) & ~near & ~green
        cand = sq(sq(cand, SP['open_px'], nd.minimum_filter), SP['open_px'], nd.maximum_filter) & cand
        e = np.zeros(ids.shape, bool)
        dx = np.abs(lum[:, 1:] - lum[:, :-1]) > SP['edge']
        e[:, 1:] |= dx
        dy = np.abs(lum[1:] - lum[:-1]) > SP['edge']
        e[1:] |= dy
        dk = lum < SP['dark']

        def ok(lab, n, sz):
            return ((np.bincount(lab[e], minlength=n + 1) >= SP['edge_frac'] * sz) &
                    (np.bincount(lab[dk], minlength=n + 1) >= SP['dark_frac'] * sz))
        out |= _keep(cand, SP['min_px'], ok)
    if not out.any():
        return out, []
    lab, n = nd.label(out)
    idx = np.arange(1, n + 1)
    sz = np.bincount(lab.ravel(), minlength=n + 1)
    hc = np.bincount((lab[out] * 16 + host[out]).ravel(), minlength=(n + 1) * 16).reshape(n + 1, 16)
    brf = np.bincount(lab[out & bm], minlength=n + 1) / np.maximum(sz, 1)
    rr = np.asarray(r).astype(np.float32)
    med = np.stack([nd.median(rr[..., ch], lab, idx) for ch in range(3)], -1) if n else np.zeros((0, 3))
    res = []
    for i, (cy_, cx_) in zip(idx, nd.center_of_mass(out, lab, idx)):
        mx, mn = med[i - 1].max(), med[i - 1].min()
        sat, val = (mx - mn) / max(mx, 1.0), mx / 255
        kind = 'brick' if brf[i] > 0.15 else ('light' if val >= 0.72 and sat < 0.35 else ('gray' if sat < 0.18 else 'other'))
        res.append((int(sz[i]), float(cy_), float(cx_), int(hc[i].argmax()), kind))
    return out, res


def grow_up(m, n):
    """각 열에서 m 화소 위로 n px 까지(화면 위 = 지붕 쪽)"""
    C = np.zeros((m.shape[0] + 1,) + m.shape[1:], np.int32)
    np.cumsum(m, 0, out=C[1:])
    y = np.arange(m.shape[0])
    return (C[np.minimum(y + n + 1, m.shape[0])] - C[y]) > 0


def fake_pavilions(raw, cond, ids, meta, P=PAV):
    """정자 id 마다 raw 가 벽돌색인 몫·cond 와 크게 다른 몫 → (가짜 표 lut, 정보)"""
    pav = kind_lut(meta, 'park_pavilion')
    box = {}
    B = 2048
    for s0 in range(0, H, B):
        idb = np.asarray(ids[s0:s0 + B])
        for k, sl in enumerate(nd.find_objects(np.where(pav[idb], idb, 0).astype(np.int32)), 1):
            if sl is None:
                continue
            b = box.get(k)
            y0_, y1_, x0_, x1_ = sl[0].start + s0, sl[0].stop + s0, sl[1].start, sl[1].stop
            box[k] = (y0_, y1_, x0_, x1_) if b is None else (min(b[0], y0_), max(b[1], y1_), min(b[2], x0_), max(b[3], x1_))
    lut = np.zeros(65536, bool)
    info = {}
    for k, (y0_, y1_, x0_, x1_) in sorted(box.items()):
        s2 = (slice(y0_, y1_), slice(x0_, x1_))
        m = np.asarray(ids[s2]) == k
        r, c = np.asarray(raw[s2]), np.asarray(cond[s2])
        br = (brick_mask(r) & ~sq(brick_mask(c), BRICK['cond_px'], nd.maximum_filter))[m].mean()
        far = (chroma_dist(r[m].astype(np.float32), c[m].astype(np.float32)) > P['thr']).mean()
        fake = bool(br >= P['brick'] or far >= P['far'])
        lut[k] = fake
        info[f"{k} {meta['ids'][str(k)]}"] = {'px': int(m.sum()), 'brick': round(float(br), 3), 'far': round(float(far), 3), 'fake': fake, 'canvas_xy': [x0_, y0_]}
    return lut, info


def pavilion_fill(c, ids, fp, P=PAV):
    """가짜 정자 화소를 cond(정자마다 K색 포스터라이즈 + 윤곽·색 경계 어두운 선)로 → (h,w,3) uint8"""
    out = np.zeros(c.shape, np.uint8)
    lab = np.where(fp, ids, 0).astype(np.int32)
    for k, sl in enumerate(nd.find_objects(lab), 1):
        if sl is None:
            continue
        m = lab[sl] == k
        z = np.zeros(m.shape, np.float32)
        new = _stylize(m, np.asarray(c[sl]), z, m, m, np.zeros(m.shape, bool), P['colors'], RPARAMS)
        out[sl][m] = new[m]
    return out


def wall_faces(wm, vv, P=FACE):
    """벽 마스크 wm 을 면으로 나눈다(깊이의 가로 기울기가 같은 이어진 화소; 기울기가 비슷한 이웃 면은 합침) → 라벨(0 = 벽 아님)"""
    z = np.asarray(vv).astype(np.float32) * DSTEP
    gx = np.zeros(z.shape, np.float32)
    ok = np.zeros(z.shape, bool)
    gx[:, 1:] = z[:, 1:] - z[:, :-1]
    ok[:, 1:] = wm[:, 1:] & wm[:, :-1] & (np.abs(gx[:, 1:]) < P['jump'])
    num = nd.uniform_filter1d(np.where(ok, gx, 0), P['win'], axis=1)
    den = nd.uniform_filter1d(ok.astype(np.float32), P['win'], axis=1)
    gs = np.where(den > 0.3, num / np.maximum(den, 1e-3), np.nan)
    e = ~wm
    dx = np.nan_to_num(np.abs(gs[:, 1:] - gs[:, :-1]), nan=9.0) > P['tol']
    dx |= np.abs(z[:, 1:] - z[:, :-1]) > P['jump']
    e[:, 1:] |= dx
    e[:, :-1] |= dx
    dy = np.nan_to_num(np.abs(gs[1:] - gs[:-1]), nan=9.0) > P['tol']
    dy |= np.abs(z[1:] - z[:-1]) > P['jump']
    e[1:] |= dy
    e[:-1] |= dy
    lab, n = nd.label(wm & ~e)
    if not n:
        return wm.astype(np.int32)
    sz = np.bincount(lab.ravel(), minlength=n + 1)
    small = sz < P['min_px']
    small[0] = True
    if small[1:].all():
        return wm.astype(np.int32)
    lab[small[lab]] = 0
    iy, ix = nd.distance_transform_edt(lab == 0, return_distances=False, return_indices=True)
    lab = np.where(wm, lab[iy, ix], 0)
    # 기울기 평균이 비슷한 이웃 면 합치기(가로 띠·이음매에서 쪼개진 같은 면)
    fin = wm & np.isfinite(gs)
    cnt = np.bincount(lab[fin], minlength=n + 1)
    mean = np.bincount(lab[fin], weights=gs[fin], minlength=n + 1) / np.maximum(cnt, 1)
    par = np.arange(n + 1)

    def root(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for a_, b_ in ((lab[:, :-1], lab[:, 1:]), (lab[:-1], lab[1:])):
        d = (a_ != b_) & (a_ > 0) & (b_ > 0)
        for p_, q_ in np.unique(np.stack([a_[d], b_[d]], 1), axis=0) if d.any() else ():
            if cnt[p_] and cnt[q_] and abs(mean[p_] - mean[q_]) < P['merge']:
                rp, rq = root(p_), root(q_)
                if rp != rq:
                    par[max(rp, rq)] = min(rp, rq)
    rt = np.array([root(i) for i in range(n + 1)])
    return rt[lab]


def face_select(lab, z, frac_px, blob=None, all_=FACE['all'], bl=FACE['blob']):
    """면마다 frac_px(바뀌어야 할 화소)의 몫이 all_ 이상이거나 blob 덩어리가 면의 bl 이상 덮으면 그 면 전체 → (마스크, [(면 px, 몫)])"""
    L = lab[z]
    nL = int(lab.max()) + 1
    tot = np.bincount(L, minlength=nL)
    fr = np.bincount(L, weights=frac_px[z].astype(np.float32), minlength=nL) / np.maximum(tot, 1)
    sel = fr >= all_
    if blob is not None:
        sel |= (np.bincount(L, weights=blob[z].astype(np.float32), minlength=nL) / np.maximum(tot, 1)) >= bl
    sel[0] = False
    info = [(int(tot[i]), round(float(fr[i]), 3)) for i in np.nonzero(sel)[0]]
    return sel[lab] & z, info


# ───────────────────────── lock(지붕 잠금 · 랜드마크 벽 잠금, 8차) ─────────────────────────
# 사용자 지시: 옥상(헬리패드·기계실·설비)은 양식 패스에 다시 그리게 하지 않고 Blender 조건 렌더(cond)를 정본으로 쓴다.
#  지붕 구역 = 건물 id(tower·landmark:*·apartment) 화소 중 (1) 수평·경사면: 같은 id 이웃과의 높이 변화가 벽(화면 1 px 당 PX/ey.z m)보다 훨씬 작은 화소.
#    가는 띠(창턱·돌림띠, 7×7 px 열기에 사라지는 것)만으로 된 덩어리는 뺀다. (2) 그 면 위에 선 낮은 벽(기계실·파라펫 안쪽·헬리패드 받침·돔):
#    열 방향 벽 줄의 아래 끝이 같은 id 지붕면에 닿고 높이가 cap_m 이하인 것. 건물 정면 벽은 아래 끝이 땅·다른 건물이라 들어가지 않는다.
#  tower·landmark: 지붕 구역 전부를 cond 로 바꾼다.  apartment: 지붕 구역에서 건물별 색 이동(중앙값)을 뺀 거리가 큰 속 찬 덩어리만.
#  landmark 벽: cond 와 직접 견준 거리가 큰 속 찬 덩어리만. 다만 벽 화소의 wall_all(40%) 넘게 다르면 벽 전체(창 경계에서 벽 중간에 지어낸 지붕, 색이 통째로 바뀐 벽, 벽돌·차양).
#  넣는 cond 는 (a) 건물별 K색 포스터라이즈 (b) 지붕 윤곽·높이 단차·강한 색 경계에 1 px 어두운 선 (c) 가장자리는 섞지 않고 끊는다.
RPARAMS = {'wall_lo': 0.55, 'wall_hi': 2.2, 'core_px': 3, 'cap_m': {1: 10.0, 2: 32.0, 3: 10.0}, 'min_px': 200, 'hole_px': 6000,
           'colors': {1: 10, 2: 20, 3: 10}, 'wcolors': 12, 'edge_dz': 0.45, 'edge_col': 60.0, 'dark': 0.4, 'wall_all': 0.4, 'dark_soft': 0.7,
           'wall': {'thr': 60.0, 'win': 9, 'close_px': 2, 'core_px': 8, 'min_px': 4000, 'grow_px': 10},
           'apt': {'thr': 48.0, 'win': 9, 'close_px': 1, 'core_px': 3, 'min_px': 300, 'grow_px': 6}}
RCOL = {'roof': (255, 0, 255), 'wall': (255, 200, 0), 'apt': (0, 255, 255), 'aptwall': (0, 255, 0), 'aptrec': (0, 120, 255)}


def roof_kind_lut(meta):
    """id → 0 잠그지 않음(저층·교량·나무 등) / 1 tower / 2 landmark:* / 3 apartment"""
    rk = np.zeros(65536, np.uint8)
    for k, t in meta['ids'].items():
        h = t.split(':')[0]
        rk[int(k)] = {'tower': 1, 'landmark': 2, 'apartment': 3}.get(h, 0)
    return rk


def _runs_on_flat(wall, flat, cap):
    """열(화면 세로) 방향 벽 줄 가운데, 바로 아래 화소가 flat 이고 길이가 cap 이하인 줄 → 마스크"""
    h, w = wall.shape
    wp = np.zeros((h + 1, w), bool)
    wp[:h] = wall
    fp = np.zeros((h + 1, w), bool)
    fp[:h] = flat
    wf, ff = wp.T.ravel(), fp.T.ravel()
    d = np.diff(np.concatenate([[0], wf.view(np.int8), [0]]))
    st, en = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
    keep = ((en - st) <= cap) & ff[np.minimum(en, len(ff) - 1)]
    acc = np.zeros(len(wf) + 1, np.int32)
    np.add.at(acc, st[keep], 1)
    np.add.at(acc, en[keep], -1)
    return (np.cumsum(acc[:-1]) > 0).reshape(w, h + 1).T[:h]


def roof_zone(m, hgt, per, cap_px, P):
    """한 건물(마스크 m, 높이 hgt) → (지붕 구역, 벽 여부). per = 벽에서 화면 1 px 당 높이 변화(m)"""
    up = np.zeros(m.shape, bool)
    up[1:] = m[1:] & m[:-1]
    dn = np.zeros(m.shape, bool)
    dn[:-1] = m[:-1] & m[1:]
    dh = np.zeros(m.shape, np.float32)
    dh[:-1] = hgt[:-1] - hgt[1:]            # 화소 y 와 그 아래 화소의 높이 차
    su = np.zeros(m.shape, np.float32)
    su[1:] = dh[:-1]
    n = up.astype(np.float32) + dn
    slope = (su * up + dh * dn) / np.maximum(n, 1) / per
    wall = m & ((n == 0) | ((slope > P['wall_lo']) & (slope < P['wall_hi'])))
    flat = m & ~wall
    r = P['core_px']
    core = sq(sq(flat, r, nd.minimum_filter), r, nd.maximum_filter) & flat
    lab, nl = nd.label(flat)
    if nl:
        ok = np.zeros(nl + 1, bool)
        ok[np.unique(lab[core])] = True
        ok[0] = False
        flat = ok[lab]
    zone = flat | _runs_on_flat(wall, flat, cap_px)
    holes = nd.binary_fill_holes(zone) & m & ~zone
    if holes.any():
        lab, nl = nd.label(holes)
        sz = np.bincount(lab.ravel(), minlength=nl + 1)
        zone |= (sz <= P['hole_px'])[lab] & holes
    lab, nl = nd.label(zone)
    if nl:
        sz = np.bincount(lab.ravel(), minlength=nl + 1)
        ok = sz >= P['min_px']
        ok[0] = False
        zone = ok[lab]
    return zone, wall


def _blobs(d, z, p):
    """구역 z 안에서 거리 d 가 큰 '속이 찬 덩어리'(6차 교량 잠금과 같은 순서) → 채울 마스크"""
    loose = (nd.uniform_filter(d, p['win']) > p['thr']) & z
    m = (nd.uniform_filter(d, 3) > p['thr']) & z
    if p.get('close_px'):
        m = sq(sq(m, p['close_px'], nd.maximum_filter), p['close_px'], nd.minimum_filter) & z
    m = sq(sq(m, p['core_px'], nd.minimum_filter), p['core_px'], nd.maximum_filter) & m
    lab, n = nd.label(m)
    if not n:
        return np.zeros(z.shape, bool), 0
    sz = np.bincount(lab.ravel(), minlength=n + 1)
    keep = sz >= p['min_px']
    keep[0] = False
    if not keep.any():
        return np.zeros(z.shape, bool), 0
    f = sq(keep[lab], p['grow_px'], nd.maximum_filter) & (loose | keep[lab])
    return nd.binary_fill_holes(f) & z, int(keep.sum())


def _poster(col, k):
    """(N,3) uint8 → K색 포스터라이즈(중앙값 자르기 + k-means 2회)"""
    if len(col) == 0:
        return col
    im = Image.fromarray(np.ascontiguousarray(col).reshape(1, -1, 3))
    q = im.quantize(colors=k, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE, kmeans=2)
    pal = np.array(q.getpalette()[:k * 3], np.uint8).reshape(-1, 3)
    return pal[np.asarray(q).ravel()]


def _stylize(fill, cond, hgt, m, zone, wall, k, P, roof=True):
    """cond 를 fill 안에서 포스터라이즈하고 어두운 선을 넣는다 → (h,w,3) uint8 (fill 밖은 0)"""
    out = np.zeros(cond.shape, np.uint8)
    # 지붕: 렌더 잡음·가는 결을 3×3 중앙값으로 먼저 눌러 색 경계가 점무늬로 흩어지지 않게. 벽은 1 px 창 격자가 지워지므로 그대로 둔다
    cm = np.stack([nd.median_filter(cond[..., i], 3) for i in range(3)], -1) if roof else cond
    out[fill] = _poster(cm[fill], k)
    # 외톨이 화소(8이웃 중 같은 색이 1개 이하 — 렌더 잡음이 두 색 사이를 오가며 생긴 점무늬)는 가장 가까운 덩어리 색으로
    key = np.where(fill, out[..., 0].astype(np.int32) << 16 | out[..., 1].astype(np.int32) << 8 | out[..., 2], -1)
    kp = np.pad(key, 1, constant_values=-2)
    h_, w_ = key.shape
    same = sum((kp[1 + dy:1 + dy + h_, 1 + dx:1 + dx + w_] == key) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx)
    speck = fill & (same <= 1)
    if speck.any() and (fill & ~speck).any():
        iy, ix = nd.distance_transform_edt(~(fill & ~speck), return_distances=False, return_indices=True)
        out[speck] = out[iy[speck], ix[speck]]
    o = out.astype(np.float32)
    lum = o @ LUM
    hard = np.zeros(fill.shape, bool)
    soft = np.zeros(fill.shape, bool)
    # (1) 윤곽: 지붕 구역의 가장자리(건물 밖 또는 같은 건물의 벽과 닿는 화소)
    er = nd.minimum_filter(zone.view(np.uint8), footprint=np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]])).astype(bool)
    if roof:
        hard |= zone & ~er
    # (2) 높이 단차(설비 상자·헬리패드 받침·파라펫): 높은 쪽 화소. 세로는 벽의 정상 변화(per)를 뺀다
    both = fill[:, 1:] & fill[:, :-1]
    j = both & (np.abs(hgt[:, 1:] - hgt[:, :-1]) > P['edge_dz'])
    hi = hgt[:, 1:] > hgt[:, :-1]
    hard[:, 1:] |= j & hi
    hard[:, :-1] |= j & ~hi
    both = fill[1:] & fill[:-1]
    dv = hgt[:-1] - hgt[1:]
    j = both & ((dv > P['edge_dz'] + 0.35) | (dv < -P['edge_dz']))
    hard[:-1] |= j & (dv > 0)
    hard[1:] |= j & (dv < 0)
    # (3) 강한 색 경계(헬리패드 표시 등): 어두운 쪽 화소를 조금 더 어둡게
    for ax in ((0, 1) if roof else ()):
        a = [slice(None)] * 2
        b = [slice(None)] * 2
        a[ax], b[ax] = slice(1, None), slice(None, -1)
        a, b = tuple(a), tuple(b)
        e = fill[a] & fill[b] & (np.sqrt(((o[a] - o[b]) ** 2).sum(-1)) > P['edge_col'])
        soft[a] |= e & (lum[a] < lum[b])
        soft[b] |= e & (lum[b] <= lum[a])
    # (4) 설비 벽이 지붕면에 닿는 줄(벽 화소 바로 아래가 지붕면)
    c = np.zeros(fill.shape, bool)
    c[:-1] = wall[:-1] & zone[:-1] & zone[1:] & ~wall[1:]
    if roof:
        soft |= c
    hard &= fill
    soft &= fill & ~hard
    out[soft] = (o[soft] * P['dark_soft']).astype(np.uint8)
    out[hard] = (o[hard] * P['dark']).astype(np.uint8)
    return out


def roof_lock_building(raw, cond, ids, hgt, k, kind, per, P=RPARAMS, dbg=None, vv=None):
    """한 건물(id k, 배열은 그 건물 상자)을 잠근다 → (채운 마스크 {roof, wall, apt}, 새 색 (h,w,3), 정보)"""
    m = ids == k
    zone, wall = roof_zone(m, hgt, per, int(P['cap_m'][kind] / per), P)
    rawf, condf = raw.astype(np.float32), cond.astype(np.float32)
    fills = {n: np.zeros(m.shape, bool) for n in RCOL}
    new = np.zeros(raw.shape, np.uint8)
    info = {'zone_px': int(zone.sum())}
    if kind in (1, 2):
        fills['roof'] = zone
    else:
        d = np.zeros(m.shape, np.float32)
        if zone.any():
            sh = np.median(rawf[zone] - condf[zone], 0)        # 건물별 색 이동(양식 패스가 지붕 색을 통째로 옮긴 만큼)
            d[zone] = chroma_dist(rawf[zone] - sh, condf[zone])
            fills['apt'], info['apt_blobs'] = _blobs(d, zone, P['apt'])
            if dbg is not None:
                dbg[zone] = d[zone]
    rz = fills['roof'] | fills['apt']
    if rz.any():
        new[rz] = _stylize(rz, cond, hgt, m, zone, wall, P['colors'][kind], P)[rz]
    if MATLM is not None and MATLM[k]:              # [12차] 재질을 픽셀아트 결로 바꾼 랜드마크(halfF3): 차이와 관계없이 벽 전체를 cond 로(건물별 포스터라이즈 + 1 px 선)
        z = m & ~zone
        if z.any():
            fills['wall'] = z
            new[z] = _stylize(z, cond, hgt, m, zone, wall, P.get('mcolors', P['wcolors']), P, roof=False)[z]
            info['wall_whole'] = info['mat_lm'] = True
    elif kind == 2:
        z = m & ~zone
        d = np.zeros(m.shape, np.float32)
        d[z] = chroma_dist(rawf[z], condf[z])
        if dbg is not None:
            dbg[z] = d[z]
        f, info['wall_blobs'] = _blobs(d, z, P['wall'])
        info['wall_far'] = round(float((d[z] > P['wall']['thr']).mean()), 3) if z.any() else 0.0
        if info['wall_far'] > P['wall_all']:       # 벽의 큰 몫이 cond 와 다르면(색이 통째로 바뀜·창 경계에서 잘려 다시 지어짐) 조각내지 않고 벽 전체를 바꾼다
            f = z
            info['wall_whole'] = True
        elif vv is not None and z.any():           # [11차] 일부만 바꿀 때는 면 단위: 다른 몫이 큰 면이나 덩어리가 크게 덮은 면은 면 전체, 나머지 면은 그대로
            lab = wall_faces(z, vv)
            f, fi = face_select(lab, z, d > P['wall']['thr'], f)
            info['wall_faces'] = fi
        if f.any():
            fills['wall'] = f
            new[f] = _stylize(f, cond, hgt, m, zone, wall, P['wcolors'], P, roof=False)[f]
    if kind == 3 and vv is not None:               # [11차] 아파트 벽의 벽돌: cond 에 없는 적갈색이 큰 몫을 차지한 면을 면 전체 cond 로
        z = m & ~zone
        bm = brick_mask(raw) & ~sq(brick_mask(cond), BRICK['cond_px'], nd.maximum_filter) & z
        if bm.sum() >= FACE['apt_min_px']:
            lab = wall_faces(z, vv)
            f, fi = face_select(lab, z, bm, all_=FACE['apt_brick'])
            if f.any():
                nb = np.bincount(lab[bm], minlength=int(lab.max()) + 1)
                ok = nb >= FACE['apt_min_px']
                f &= ok[lab]
            if FACE['rec_face']:     # [12차] 벽돌 몫이 낮은 면도 다시 칠하지 않고 면 전체를 cond 로 — 재칠은 창 격자 위에 회색 얼룩을 남겼다(r6 L자 동·긴 동 아래쪽)
                tot = np.bincount(lab[z], minlength=int(lab.max()) + 1)
                nb = np.bincount(lab[bm], minlength=len(tot))
                okf = (nb >= FACE['apt_min_px']) & (nb >= FACE['rec_frac'] * np.maximum(tot, 1))
                okf[0] = False
                if okf.any():
                    f = f | (okf[lab] & z)
                    fi = (fi if isinstance(fi, list) else []) + [[int(tot[L]), round(float(nb[L] / tot[L]), 3), 'rec_face'] for L in np.nonzero(okf)[0]]
            if f.any():
                fills['aptwall'] = f
                new[f] = _stylize(f, cond, hgt, m, zone, wall, P['wcolors'], P, roof=False)[f]
                info['aptwall_faces'] = fi
            # 벽돌 몫이 낮은 면(정면의 벽돌 기둥·띠): 면 전체를 렌더 결로 바꾸지 않고, 벽돌 화소만 그 면의 밝은 벽색으로 다시 칠한다(창·선은 raw 그대로)
            rec_info = []
            L_all = lab[z]
            tot = np.bincount(L_all, minlength=int(lab.max()) + 1)
            nb = np.bincount(lab[bm], minlength=len(tot))
            win = raw[..., 2].astype(np.int16) > raw[..., 0].astype(np.int16) + 15
            lum = rawf @ LUM
            for Lf in ([] if FACE['rec_face'] else np.nonzero((nb >= FACE['apt_min_px']) & (nb >= FACE['rec_frac'] * np.maximum(tot, 1)))[0]):
                if Lf == 0:
                    continue
                fm = (lab == Lf) & ~fills['aptwall']
                if not fm.any():
                    continue
                R = sq(sq(bm & fm, FACE['rec_close'], nd.maximum_filter), FACE['rec_close'], nd.minimum_filter) & fm & ~win
                lt = fm & ~win & ~sq(bm, 3, nd.maximum_filter) & (lum > FACE['rec_light'])
                if lt.sum() >= 300:
                    T = np.median(rawf[lt], 0)
                else:
                    T = np.median(condf[fm & ~win], 0)
                k_ = np.clip(lum[R] / max(float(np.median(lum[R])), 1.0), *FACE['rec_k'])
                new[R] = np.clip(T[None] * k_[:, None], 0, 255).astype(np.uint8)
                fills['aptrec'] |= R
                rec_info.append([int(tot[Lf]), round(float(nb[Lf] / tot[Lf]), 3), [int(x) for x in T]])
            if rec_info:
                info['aptrec_faces'] = rec_info
        info['apt_brick_px'] = int(bm.sum())
    info.update({n + '_px': int(f.sum()) for n, f in fills.items()})
    return fills, new, info


def roof_lock_region(raw, cond, ids, v, y0, cam, rk, P=RPARAMS, pad=4, want_dbg=False):
    """한 구역(배열은 그 구역 크기)의 건물 지붕·랜드마크 벽을 잠근다 → (새 그림, {이름: 마스크}, 건물별 정보, 거리 그림)"""
    out = np.array(raw)
    fills = {n: np.zeros(ids.shape, bool) for n in RCOL}
    dbg = np.zeros(ids.shape, np.float32) if want_dbg else None
    per = PX / cam.ey[2]
    infos = {}
    objs = nd.find_objects(np.where(rk[ids] > 0, ids, 0).astype(np.int32))
    for k, sl in enumerate(objs, 1):
        if sl is None:
            continue
        ys = slice(max(0, sl[0].start - pad), min(ids.shape[0], sl[0].stop + pad))
        xs = slice(max(0, sl[1].start - pad), min(ids.shape[1], sl[1].stop + pad))
        s2 = (ys, xs)
        hg = cam.height(np.asarray(v[s2]), y0 + ys.start)
        f, new, info = roof_lock_building(np.asarray(raw[s2]), np.asarray(cond[s2]), np.asarray(ids[s2]), hg, k, int(rk[k]), per, P,
                                          dbg[s2] if want_dbg else None, vv=np.asarray(v[s2]))
        for n, mk in f.items():
            if mk.any():
                fills[n][s2] |= mk
                out[s2][mk] = new[mk]
        infos[k] = info
    return out, fills, infos, dbg


_RW = {}


def _roof_one(job):
    """전체 굽기용 일꾼: 건물 하나(id, 상자)를 잠가 (id, 상자 원점, 구역별 마스크(묶음), 새 색, 정보)를 돌려준다. 배열은 fork 로 물려받은 mmap"""
    k, (by0, by1, bx0, bx1), pad = job
    raw, cond, ids, v, cam, rk = (_RW[n] for n in ('raw', 'cond', 'ids', 'v', 'cam', 'rk'))
    ys, xs = slice(max(0, by0 - pad), min(H, by1 + pad)), slice(max(0, bx0 - pad), min(W, bx1 + pad))
    s2 = (ys, xs)
    hg = cam.height(np.asarray(v[s2]), ys.start)
    f, new, info = roof_lock_building(np.asarray(raw[s2]), np.asarray(cond[s2]), np.asarray(ids[s2]), hg, k, int(rk[k]), PX / cam.ey[2], vv=np.asarray(v[s2]))
    code = np.zeros(f['roof'].shape, np.uint8)
    for i, n in enumerate(RCOL, 1):
        code[f[n]] = i
    anyf = code > 0
    return k, ys.start, xs.start, code, new[anyf], info


def roof_lock_full(a, raw, cond, ids, v, cam, meta, locked, S):
    """캔버스 전체: 건물 id 마다 상자를 구해 일꾼(8 이하)으로 잠그고 locked 에 덮어쓴다 → 통계"""
    import multiprocessing as mp
    rk = roof_kind_lut(meta)
    box = {}
    B = 2048
    for s0 in range(0, H, B):
        idb = np.asarray(ids[s0:s0 + B])
        for k, sl in enumerate(nd.find_objects(np.where(rk[idb] > 0, idb, 0).astype(np.int32)), 1):
            if sl is None:
                continue
            b = box.get(k)
            y0_, y1_, x0_, x1_ = sl[0].start + s0, sl[0].stop + s0, sl[1].start, sl[1].stop
            box[k] = (y0_, y1_, x0_, x1_) if b is None else (min(b[0], y0_), max(b[1], y1_), min(b[2], x0_), max(b[3], x1_))
    log('roof lock: buildings', len(box), {n: sum(1 for k in box if rk[k] == i) for i, n in ((1, 'tower'), (2, 'landmark'), (3, 'apartment'))})
    _RW.update(raw=raw, cond=cond, ids=ids, v=v, cam=cam, rk=rk)
    jobs = sorted(((k, b, 4) for k, b in box.items()), key=lambda j: -(j[1][1] - j[1][0]) * (j[1][3] - j[1][2]))
    tot = {n: 0 for n in RCOL}
    per = {}
    ov = np.zeros((H // 8 + 1, W // 8 + 1), np.uint8)
    with mp.get_context('fork').Pool(min(a.jobs, 8)) as pool:
        for k, y0_, x0_, code, cols, info in pool.imap_unordered(_roof_one, jobs, chunksize=4):
            anyf = code > 0
            if anyf.any():
                blk = locked[y0_:y0_ + code.shape[0], x0_:x0_ + code.shape[1]]
                blk[anyf] = cols
                yy, xx = np.nonzero(anyf)
                ov[(yy + y0_) // 8, (xx + x0_) // 8] = code[yy, xx]
            for n in RCOL:
                tot[n] += info.get(n + '_px', 0)
            per[k] = info
    locked.flush()
    o8 = np.ascontiguousarray(locked[4::8, 4::8]).copy()
    for i, n in enumerate(RCOL, 1):
        o8 = overlay(o8, ov[:o8.shape[0], :o8.shape[1]] == i, RCOL[n])
    Image.fromarray(o8).save(S / 'lock_roof_overview.png')
    big = []
    for k, i in sorted(per.items(), key=lambda t: -(t[1].get('wall_px', 0) + t[1].get('apt_px', 0) + t[1].get('aptwall_px', 0) + t[1].get('aptrec_px', 0)))[:16]:
        if not (i.get('wall_px', 0) + i.get('apt_px', 0) + i.get('aptwall_px', 0) + i.get('aptrec_px', 0)):
            break
        b = box[k]
        cy_, cx_ = (b[0] + b[1]) // 2, (b[2] + b[3]) // 2
        y0c, x0c = int(max(0, min(H - 1200, cy_ - 600))), int(max(0, min(W - 1200, cx_ - 600)))
        s2 = (slice(y0c, y0c + 1200), slice(x0c, x0c + 1200))
        name = f'lock_roof{len(big)}_{k}.png'
        ch = (np.asarray(locked[s2]) != np.asarray(raw[s2])).any(-1)
        sheet(S / name, [cond[s2], raw[s2], locked[s2], overlay(np.asarray(raw[s2]), ch)], scale=1)
        big.append({'sheet': name, 'id': k, 'kind': meta['ids'][str(k)], 'canvas_xy': [x0c, y0c], **i})
    st = {'params': RPARAMS, 'buildings': len(box), 'fill_px': tot, 'fill_m2': {n: round(t * PX * PX, 1) for n, t in tot.items()},
          'wall_whole': [f"{k} {meta['ids'][str(k)]}" for k, i in sorted(per.items()) if i.get('wall_whole')],
          'wall_blobs': {f"{k} {meta['ids'][str(k)]}": [i['wall_blobs'], i['wall_px'], i['wall_far']] for k, i in sorted(per.items()) if i.get('wall_px') and not i.get('wall_whole')},
          'apt_buildings_changed': sum(1 for i in per.values() if i.get('apt_px')),
          'wall_faces': {f"{k} {meta['ids'][str(k)]}": i['wall_faces'] for k, i in sorted(per.items()) if i.get('wall_faces')},
          'aptwall': {f"{k} {meta['ids'][str(k)]}": [i['aptwall_px'], i['aptrec_px'], i['apt_brick_px'], i.get('aptwall_faces'), i.get('aptrec_faces')] for k, i in sorted(per.items()) if i.get('aptwall_px') or i.get('aptrec_px')},
          'largest': big}
    log('roof lock:', st['fill_m2'], 'whole walls', len(st['wall_whole']), 'apt changed', st['apt_buildings_changed'])
    return st


def step_rooftest(a):
    """시험: 양식 결과 조각(--raw, 캔버스 원점 --origin x,y)에 지붕 잠금을 적용하고 전/후·표시 그림을 쓴다. cond·ids·v 는 --work 의 cache 에서 읽는다."""
    meta = load_meta(a)
    cam = Cam(meta)
    cond, ids, v = (cache(a, n) for n in ('cond', 'ids', 'v'))
    r = np.asarray(Image.open(a.raw).convert('RGB'))
    x0, y0 = map(int, a.origin.split(','))
    sl = (slice(y0, y0 + r.shape[0]), slice(x0, x0 + r.shape[1]))
    rk = roof_kind_lut(meta)
    out, fills, infos, dbg = roof_lock_region(r, np.asarray(cond[sl]), np.asarray(ids[sl]), np.asarray(v[sl]), y0, cam, rk, want_dbg=True)
    O = Path(a.out)
    O.mkdir(parents=True, exist_ok=True)
    Image.fromarray(r).save(O / f'{a.name}_before.png')
    Image.fromarray(out).save(O / f'{a.name}_after.png')
    mk = r.copy()
    for n, f in fills.items():
        if f.any():
            mk = overlay(mk, f, RCOL[n])
    Image.fromarray(mk).save(O / f'{a.name}_marks.png')
    Image.fromarray(np.clip(dbg * 2, 0, 255).astype(np.uint8)).save(O / f'{a.name}_dist.png')
    tot = {n: int(f.sum()) for n, f in fills.items()}
    res = {'origin': [x0, y0], 'fill_px': tot, 'fill_m2': {n: round(t * PX * PX, 1) for n, t in tot.items()},
           'buildings': {f"{k} {meta['ids'][str(k)]}": i for k, i in infos.items()}}
    (O / f'{a.name}.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    log(a.name, res['fill_m2'])


# ───────────────────────── lock(지면·나무 잠금 · 밤섬 · 강물 단색, 10차) ─────────────────────────
# 실제 전체 굽기(appF_r4)에서: 밤섬(무인 섬)·한강공원 둔치·샛강 녹지에 양식 패스가 벽돌집·도로를 지어냈고, 강물 잠금 뒤에 네모난 밝고 어두운 조각이 남았다.
#  지면·나무 잠금(경복궁 build_assets.py 지면 잠금을 옮김): 구역 = 지면 id 1 의 분류 2·3·14·15(광장·잔디·공원·습지) + 나무 id(core) 와 분류 0·1·12·13·16(ext).
#    분류 묶음별 cond→raw 대응표의 기대색과 거리(3 px 평균) > thr → 닫기 → 열기(core_px: 17 px = 2.1 m 보다 가는 차선·횡단보도·난간·차는 사라진다) → 성분(min_px 이상,
#    core 화소가 core_frac 이상 — 도시 도로·부지만으로 된 덩어리는 건드리지 않는다) → grow_px 만큼 키워 느슨한 마스크 안에서 채움 = 기대색(+ 지면은 가까운 깨끗한 결).
#    건물·교량 등 물체 id 둘레 keep_px 는 보존(cond 에 있는 저층 건물의 처마·윤곽). 나무 화소는 기대색 + 나무 윤곽 1 px 어두운 선.
#  밤섬(강물·교량에 둘러싸이고 건물 분류가 없는 땅 성분): 섬 안 지면·나무 전부에 낮은 임계(island)로, 열기·크기 제한 거의 없이.
#  강물: 강물 화소 전부를 한 바탕색(raw 강물 중앙값)으로 칠하고, cond 강물의 잔물결(주변 평균보다 밝은 줄)과 그림자(교량 아래)만 2–4단으로 옮긴다. 조각 경계가 없다.
GPARAMS = {'thr': 55.0, 'win': 9, 'keep_px': 6, 'close_px': 1, 'core_px': 8, 'min_px': 2500, 'grow_px': 16, 'loose': 0.6, 'core_frac': 0.5, 'hole_px': 20000,
           'tex': 0.7, 'edge_dark': 0.45,
           'island': {'thr': 30.0, 'win': 9, 'keep_px': 0, 'close_px': 1, 'core_px': 1, 'min_px': 80, 'grow_px': 8, 'loose': 0.5, 'core_frac': 0.0, 'hole_px': 20000}}
G_GROUPS = {'green': (3, 14, 15), 'pave': (2,), 'base': (0, 1, 12, 13, 16), 'tree': (), 'pond': (17,)}      # 묶음 번호 1..5 ([11차] 연못·샛강 수로 = 5)
G_CORE = (1, 2, 4, 5)
G_TREE, G_POND = 4, 5
ISLAND_CLS = (0, 3, 11, 13, 14, 15)
WFLAT = {'shadow': 0.80, 'hi': 7.0, 'hi_sh': 5.0, 'win': 65, 'light': (20, 20, 18), 'k_shadow': 0.78, 'k_shadow_light': 0.86}
GCOL = {'ground': (255, 0, 255), 'tree': (255, 200, 0), 'island': (0, 255, 255), 'ghost': (255, 0, 0), 'pavilion': (0, 0, 255)}
_KG = np.zeros(256, np.uint8)
for _i, (_n, _cs) in enumerate(G_GROUPS.items(), 1):
    for _c in _cs:
        _KG[_c] = _i


def kind_lut(meta, head):
    b = np.zeros(65536, bool)
    for k, t in meta['ids'].items():
        if t.split(':')[0] == head:
            b[int(k)] = True
    return b


def island_cells(kcls):
    """밤섬: 0.5 m 분류 맵에서 강물(5)·교량(10)이 아닌 땅 성분 가운데 판 가장자리에 닿지 않고 건물·도로 분류가 없는 것(400칸 이상) → 2칸 넓힌 마스크"""
    kk = np.asarray(kcls)
    lab, n = nd.label((kk != 5) & (kk != 10))
    out = np.zeros(kk.shape, bool)
    info = []
    for i, sl in enumerate(nd.find_objects(lab), 1):
        if sl is None or sl[0].start == 0 or sl[1].start == 0 or sl[0].stop == kk.shape[0] or sl[1].stop == kk.shape[1]:
            continue
        m = lab[sl] == i
        if m.sum() < 400 or not np.isin(np.unique(kk[sl][m]), ISLAND_CLS).all():
            continue
        out[sl] |= m
        info.append({'cells': int(m.sum()), 'rows_05m': [sl[0].start, sl[0].stop], 'cols_05m': [sl[1].start, sl[1].stop]})
    return nd.maximum_filter(out.view(np.uint8), size=5).astype(bool), info


def ground_groups(ids, kfull, treelut):
    grp = np.where(ids == 1, _KG[kfull], 0).astype(np.uint8)
    grp[treelut[ids]] = G_TREE
    return grp


def get_gluts(a, raw, cond, ids, kcls, treelut):
    """cache/lock_glut.npz 에서 읽되, 묶음이 하나라도 없으면([11차] pond 추가 전 캐시) 다시 만든다"""
    gf = Path(a.work) / 'cache' / 'lock_glut.npz'
    if gf.exists():
        z = np.load(gf)
        if all(f'{n}5' in z for n in G_GROUPS):
            return {n: [(int(b), z[f'{n}{b}']) for b in (5, 4, 3)] for n in G_GROUPS}
    gluts = ground_luts(raw, cond, ids, kcls, treelut)
    np.savez(gf, **{f'{n}{b}': l for n, ls in gluts.items() if ls for b, l in ls})
    return gluts


def ground_luts(raw, cond, ids, kcls, treelut, step=4, B=2048):
    """묶음(green·pave·base·tree)별 cond → raw 대응표"""
    smp = {n: ([], []) for n in G_GROUPS}
    for s0 in range(0, H, B):
        s1 = min(H, s0 + B)
        g = ground_groups(np.asarray(ids[s0:s1:step])[:, ::step], up(kcls, s0, s1)[::step, ::step], treelut)
        cb, rb = np.asarray(cond[s0:s1:step])[:, ::step], np.asarray(raw[s0:s1:step])[:, ::step]
        for i, n in enumerate(G_GROUPS, 1):
            m = g == i
            if i == G_POND:         # [11차] 연못: raw 가 물색(파랑 > 빨강 + 40)인 표본만 — 양식 패스가 연못을 옮겨 그린 자리(잔디·광장)가 표를 회색으로 끈다
                m &= rb[..., 2].astype(np.int16) > rb[..., 0].astype(np.int16) + 40
            if m.any():
                smp[n][0].append(cb[m])
                smp[n][1].append(rb[m])
    out = {}
    for n, (cs, rs) in smp.items():
        out[n] = lut_from_samples(np.concatenate(cs), np.concatenate(rs)) if cs else None
        log('ground lut', n, 'samples', sum(len(x) for x in cs), 'bins', {b: int((~np.isnan(l[:, 0])).sum()) for b, l in (out[n] or [])})
    return out


def _gblobs(d, z, corem, p, force=None, dark=None):
    """[11차] force(벽돌 씨앗)에 닿는 덩어리는 크기·core 조건 없이 채우고, 씨앗 위로 roof_up px 까지(지붕) 느슨한 마스크 안을 같이 채운다 → (채움, 덩어리, 씨앗 채움)"""
    loose = (nd.uniform_filter(d, p['win']) > p['thr'] * p['loose']) & z
    m = (nd.uniform_filter(d, 3) > p['thr']) & z
    if p.get('close_px'):
        m = sq(sq(m, p['close_px'], nd.maximum_filter), p['close_px'], nd.minimum_filter) & z
    m = sq(sq(m, p['core_px'], nd.minimum_filter), p['core_px'], nd.maximum_filter) & m
    force = force & z if force is not None else None
    if force is not None and force.any():
        m |= force
    lab, n = nd.label(m)
    none = np.zeros(z.shape, bool)
    if not n:
        return none, [], none
    sz = np.bincount(lab.ravel(), minlength=n + 1)
    keep = sz >= p['min_px']
    if p['core_frac'] > 0:
        keep &= np.bincount(lab[corem], minlength=n + 1) >= p['core_frac'] * sz
    fk = np.zeros(n + 1, bool)
    if force is not None and force.any():
        fk = np.bincount(lab[force], minlength=n + 1) > 0
        fk[0] = False
    keep[0] = False
    gh = none
    if fk.any():
        # 씨앗에 닿는 덩어리는 씨앗 둘레 comp_px 안만(raw 가 광장 색을 통째로 바꾼 곳에서 광장 전체가 딸려 오지 않게)
        fc = fk[lab] & sq(force, BRICK['comp_px'], nd.maximum_filter)
        gh = (grow_up(sq(force, BRICK['grow_px'], nd.maximum_filter), BRICK['roof_up']) & loose) | sq(fc, p['grow_px'], nd.maximum_filter) & (loose | fc)
    if not keep.any() and not gh.any():
        return none, [], none
    idx = np.nonzero(keep)[0]
    bl = [(int(sz[i]), float(cy_), float(cx_)) for i, (cy_, cx_) in zip(idx, nd.center_of_mass(m, lab, idx))]
    f = sq(keep[lab], p['grow_px'], nd.maximum_filter) & (loose | keep[lab])
    if gh.any():
        near = sq(gh, BRICK['near_px'], nd.maximum_filter) & z          # 지어낸 집 둘레의 그림자·화분·파라솔 조각
        nf = near & (nd.uniform_filter(d, 3) > BRICK['near_thr'])
        if dark is not None:
            nf |= near & dark
        gh |= nf
        f |= gh
    holes = nd.binary_fill_holes(f) & z & ~f
    if holes.any():
        lab, n = nd.label(holes)
        f |= (np.bincount(lab.ravel(), minlength=n + 1) <= p['hole_px'])[lab] & holes
    return f & z, bl, gh & z


def ground_expect(r, c, ids, kfull, gluts, treelut):
    """지면·나무 묶음의 기대색과 거리 → (묶음, 기대색, 거리)"""
    r, c = np.asarray(r), np.asarray(c)
    grp = ground_groups(ids, kfull, treelut)
    E = np.zeros(r.shape, np.float32)
    d = np.zeros(ids.shape, np.float32)
    for i, n in enumerate(G_GROUPS, 1):
        m = grp == i
        if not m.any():
            continue
        if gluts.get(n) is None:
            grp[m] = 0
            continue
        e = lut_apply(gluts[n], c[m])
        E[m] = e
        d[m] = chroma_dist(r[m].astype(np.float32), e)
    return grp, E, d


def ground_lock_region(r, c, ids, kfull, gluts, treelut, P=GPARAMS, strong=None, hl=None, fakepav=None):
    """한 구역(배열은 그 구역 크기)의 지면·나무를 잠근다. strong = 밤섬 마스크(없으면 None), hl = host_lut(벽돌 씨앗), fakepav = 가짜 정자 표
    → (새 그림, {ground, tree, island, ghost, pavilion} 마스크, 덩어리 [(이름, px, cy, cx)])"""
    r, c = np.asarray(r), np.asarray(c)
    out = np.array(r)
    grp = ground_groups(ids, kfull, treelut)
    E = np.zeros(r.shape, np.float32)
    d = np.zeros(ids.shape, np.float32)
    for i, n in enumerate(G_GROUPS, 1):
        m = grp == i
        if not m.any():
            continue
        if gluts.get(n) is None:
            grp[m] = 0
            continue
        e = lut_apply(gluts[n], c[m])
        E[m] = e
        d[m] = chroma_dist(r[m].astype(np.float32), e)
    zone = grp > 0
    corem = np.isin(grp, G_CORE)
    fp = fakepav[ids] if fakepav is not None else np.zeros(ids.shape, bool)
    obj = (ids != 1) & (grp != G_TREE) & ~fp              # [11차] 지어낸 집이 된 정자는 둘레 보존을 푼다
    st = strong & zone if strong is not None else np.zeros(ids.shape, bool)
    gz = zone & ~st & ~sq(obj, P['keep_px'], nd.maximum_filter)
    seeds = ghost_seeds(r, c, ids, kfull, hl, d=d)[0] & gz if hl is not None else None
    f, bl, gh = _gblobs(d, gz, corem, P, force=seeds, dark=(r.astype(np.float32) @ LUM) < (E @ LUM) - BRICK['dark'])
    blobs = [('ground', *b) for b in bl]
    isl = np.zeros(ids.shape, bool)
    if st.any():
        isl, bl, _ = _gblobs(d, st, corem, P['island'])
        blobs += [('island', *b) for b in bl]
    fill = f | isl
    E0 = E
    fl = f & (grp != G_TREE) & (grp != G_POND)
    if fl.any():                # [11차] 채울 자리(지어낸 집 자리 포함): 분류마다 둘레(ring_px) raw 의 중앙값 평색 — 양식 패스가 광장·부지 색을 통째로 옮긴 곳에서
        E = E.copy()            #  기대색이 회색 얼룩이 되거나, 10차처럼 96 px 칸마다 결의 평균이 달라 네모 계단이 생기지 않게
        glab, gn = nd.label(fl)
        tcol = {}                # 분류마다 판(띠) 전체의 기대색 중앙값 — 그늘 없는 대표색
        okall = ~fill & zone & (grp != G_TREE)
        for gi, gsl in enumerate(nd.find_objects(glab), 1):
            if gsl is None:
                continue
            R_ = BRICK['ring_px']
            ys = slice(max(0, gsl[0].start - R_), min(gh.shape[0], gsl[0].stop + R_))
            xs = slice(max(0, gsl[1].start - R_), min(gh.shape[1], gsl[1].stop + R_))
            reg = glab[ys, xs] == gi
            ok_ = ~fill[ys, xs] & zone[ys, xs]
            ring = sq(reg, R_, nd.maximum_filter) & ok_
            gg = np.where(grp[ys, xs] == G_TREE, 255, kfull[ys, xs]).astype(np.int16)     # 분류(0.5 m) 단위 — 묶음 base 는 부지와 도로가 섞인다
            gg[grp[ys, xs] == 0] = -1
            rr, ee = r[ys, xs].astype(np.float32), E[ys, xs]
            sm = np.stack([nd.uniform_filter(ee[..., ch], 9) for ch in range(3)], -1)       # cond 바닥의 렌더 잡음(점무늬)을 눌러 평평하게
            nt = reg & (gg != 255) & (gg != 1)     # 도로는 차선 점선을 지우지 않게 평활하지 않는다
            ee[nt] = sm[nt]
            ring2 = None
            for g_ in np.unique(gg[reg]):
                if g_ in (-1, 255):
                    continue
                rm = ring & (gg == g_)
                if rm.sum() < BRICK['ring_min']:          # 같은 분류 둘레가 모자라면(좁은 보도 띠 등) 판 전체의 같은 분류 — 다른 분류를 섞으면 도로+보도 중간색 띠가 된다
                    if ring2 is None:
                        ring2 = ok_
                    rm = ring2 & (gg == g_)
                if rm.sum() < BRICK['ring_min']:          # 그래도 없으면 기대색(LUT) 그대로
                    continue
                if g_ not in tcol:
                    km = okall & (kfull == g_)
                    tcol[g_] = np.median(E0[km][::max(1, int(km.sum()) // 200000)], 0) if km.any() else None
                lutfb = False
                if tcol[g_] is not None:     # 둘레 raw 중 대표색에 가까운 것만 — 지어낸 건물의 회색 앞마당·그늘이 섞여 갈색 띠가 되지 않게
                    cl = rm & (chroma_dist(rr, tcol[g_]) < BRICK['ring_tol'])
                    if cl.sum() >= BRICK['ring_min']:
                        rm = cl
                    elif BRICK['ring_lut']:      # [12차] 둘레가 통째로 대표색과 멀면(양식 패스가 넓게 그린 교량 밑 그늘·지어낸 그늘) 둘레 raw 대신 cond 의 기대색(LUT) 중앙값
                        lutfb = True             #  — r6 서강대교 둔치 쪽 갈색·회색 판
                tm = reg & (gg == g_)
                if lutfb:                        # 도로는 기대색 그대로(차선), 그 밖은 기대색 중앙값 + cond 명암 ±var
                    e0 = E0[ys, xs][tm]
                    ee[tm] = e0 if g_ == 1 else np.median(e0, 0) + np.clip(ee[tm] - np.median(ee[tm], 0), -BRICK['var'], BRICK['var'])
                    continue
                # 둘레 raw 의 중앙값 + cond 명암을 ±var 로 눌러서(호안 계단 같은 cond 구조는 옅게 남고, raw 에 없는 빌딩 그림자는 거의 끌어오지 않는다)
                vr = BRICK['var_road'] if g_ == 1 else BRICK['var']      # 도로 분류엔 차선·보도 띠(cond 구조)가 들어 있어 명암을 자르지 않는다
                ee[tm] = np.median(rr[rm], 0) + np.clip(ee[tm] - np.median(ee[tm], 0), -vr, vr)
            E[ys, xs] = ee
    if fill.any():
        new = E.copy()
        gf = fill & (grp != G_TREE) & (grp != G_POND)
        if gf.any():
            clean = zone & (grp != G_TREE) & (grp != G_POND) & ~fill & (d < P['thr'] * 0.5)
            tx = texture(r, E0, clean, gf)
            if fl.any():        # 평색 위에는 결의 고주파만(칸 평균을 뺀다)
                hp = tx - np.stack([nd.uniform_filter(tx[..., ch], 33) for ch in range(3)], -1)
                tx[fl] = hp[fl]
            new += tx * P['tex'] * gf[..., None]
        tr = grp == G_TREE
        tp = np.pad(tr, 1, constant_values=True)
        edge = tr & ~(tp[:-2, 1:-1] & tp[2:, 1:-1] & tp[1:-1, :-2] & tp[1:-1, 2:])
        new[edge] *= P['edge_dark']
        out[fill] = np.clip(new[fill], 0, 255).astype(np.uint8)
    if fp.any():
        out[fp] = pavilion_fill(c, ids, fp)[fp]
    return out, {'ground': f & (grp != G_TREE), 'tree': f & (grp == G_TREE), 'island': isl, 'ghost': gh, 'pavilion': fp}, blobs


def water_stats(raw, cond, ids, kcls):
    """강물 바탕색(raw 강물 중앙값)과 cond 강물 밝기 중앙값"""
    w = (np.asarray(kcls) == 5) & (np.asarray(ids[2::4, 2::4]) == 1)
    base = np.median(np.asarray(raw[2::4, 2::4])[w], 0)
    cl = float(np.median(np.asarray(cond[2::4, 2::4])[w].astype(np.float32) @ LUM))
    return [float(x) for x in base], cl


def _mmean(x, m, size):
    den = nd.uniform_filter(m.astype(np.float32), size)
    return nd.uniform_filter(np.where(m, x, 0).astype(np.float32), size) / np.maximum(den, 1e-6)


def water_flat_region(c, ids, v, kc, y0, cam, P, base, clmed, WF=WFLAT):
    """강물 화소의 새 색(구역 크기) → (색 (h,w,3) uint8, 강물 마스크). cond 의 잔물결·그림자만 옮긴다"""
    water = water_mask(ids, v, kc, y0, cam, P)
    col = np.zeros(ids.shape + (3,), np.uint8)
    if not water.any():
        return col, water
    cl = np.asarray(c).astype(np.float32) @ LUM
    shadow = water & (_mmean(cl, water, 5) < WF['shadow'] * clmed)
    shadow = sq(sq(shadow, 2, nd.minimum_filter), 2, nd.maximum_filter) & water
    B = np.array(base, np.float32)
    tone = np.zeros(ids.shape, np.uint8)            # 0 바탕 1 밝은 줄 2 그림자 3 그림자 속 밝은 줄
    for sh, hi, t0 in ((False, WF['hi'], 0), (True, WF['hi_sh'], 2)):
        m = water & (shadow == sh)
        if not m.any():
            continue
        hp = _mmean(cl, m, (1, 5)) - _mmean(cl, m, WF['win'])
        li = m & (hp > hi)
        li = nd.maximum_filter(nd.minimum_filter(li.view(np.uint8), size=(1, 3)), size=(1, 3)).astype(bool) & m
        tone[m] = t0
        tone[li] = t0 + 1
    pal = np.clip(np.stack([B, B + np.array(WF['light'], np.float32), B * WF['k_shadow'], B * WF['k_shadow_light']]), 0, 255).astype(np.uint8)
    col[water] = pal[tone[water]]
    return col, water


_GW = {}


def _ground_strip(s0):
    """전체 굽기용 일꾼: 띠 s0 의 지면·나무 잠금 결과를 locked(mmap r+)의 자기 행에 직접 쓴다"""
    G = _GW
    B, HALO = G['B'], 256
    s1 = min(H, s0 + B)
    a0, a1 = max(0, s0 - HALO), min(H, s1 + HALO)
    idb = np.asarray(G['ids'][a0:a1])
    kf = up(G['kcls'], a0, a1)
    out, fills, blobs = ground_lock_region(G['raw'][a0:a1], G['cond'][a0:a1], idb, kf, G['gluts'], G['treelut'], strong=up(G['isl'], a0, a1),
                                           hl=G['hl'], fakepav=G['fakepav'])
    core = slice(s0 - a0, s1 - a0)
    anyf = (fills['ground'] | fills['tree'] | fills['island'] | fills['pavilion'])[core]
    if anyf.any():
        lk = np.load(G['locked'], mmap_mode='r+')
        blk = np.array(lk[s0:s1])
        blk[anyf] = out[core][anyf]
        lk[s0:s1] = blk
        lk.flush()
    ov = np.zeros(((s1 - s0) // 8, W // 8), np.uint8)
    px = {}
    for i, (n, m) in enumerate(fills.items(), 1):
        mm = m[core]
        px[n] = int(mm.sum())
        ov[mm.reshape(mm.shape[0] // 8, 8, W // 8, 8).any((1, 3))] = i
    return s0, px, ov, [(n, p_, cy_ + a0, cx_) for n, p_, cy_, cx_ in blobs if s0 <= cy_ + a0 < s1]


def _water_strip(s0):
    G = _GW
    B, HALO = G['B'], 96
    s1 = min(H, s0 + B)
    a0, a1 = max(0, s0 - HALO), min(H, s1 + HALO)
    col, water = water_flat_region(G['cond'][a0:a1], np.asarray(G['ids'][a0:a1]), np.asarray(G['v'][a0:a1]), up(G['rc'], a0, a1), a0, G['cam'], G['P'], G['base'], G['clmed'])
    core = slice(s0 - a0, s1 - a0)
    w = water[core]
    if w.any():
        lk = np.load(G['locked'], mmap_mode='r+')
        blk = np.array(lk[s0:s1])
        blk[w] = col[core][w]
        lk[s0:s1] = blk
        lk.flush()
    return s0, int(w.sum())


def ground_water_full(a, raw, cond, ids, v, kcls, rc, cam, meta, P, S, lockedf):
    """캔버스 전체: 지면·나무 잠금(밤섬 포함) → 강물 단색. 띠(1696행)마다 일꾼이 locked 에 직접 쓴다 → 통계"""
    import multiprocessing as mp
    C = Path(a.work) / 'cache'
    treelut = kind_lut(meta, 'tree')
    st = {}
    B = 1696
    strips = list(range(0, H, B))
    isl, iinfo = island_cells(kcls)
    _GW.update(raw=raw, cond=cond, ids=ids, v=v, kcls=kcls, rc=rc, cam=cam, P=P, treelut=treelut, isl=isl, locked=str(lockedf), B=B)
    if not a.no_ground:
        gluts = get_gluts(a, raw, cond, ids, kcls, treelut)
        fpl, fpi = fake_pavilions(raw, cond, ids, meta)
        log('fake pavilions:', [k for k, i in fpi.items() if i['fake']])
        _GW.update(gluts=gluts, hl=host_lut(meta), fakepav=fpl)
        px = {n: 0 for n in GCOL}
        blobs = []
        ov = np.zeros((H // 8, W // 8), np.uint8)
        with mp.get_context('fork').Pool(min(a.jobs, len(strips))) as pool:
            for s0, p_, o, bl in pool.imap_unordered(_ground_strip, strips):
                for n in px:
                    px[n] += p_[n]
                ov[s0 // 8:s0 // 8 + o.shape[0]] = o
                blobs += bl
                log('ground lock rows', s0, p_)
        lk = np.load(lockedf, mmap_mode='r')
        o8 = np.ascontiguousarray(lk[4::8, 4::8]).copy()
        for i, n in enumerate(GCOL, 1):
            o8 = overlay(o8, ov == i, GCOL[n])
        Image.fromarray(o8).save(S / 'lock_ground_overview.png')
        per = []
        for n, p_, cy_, cx_ in sorted(blobs, key=lambda b: -b[1])[:12]:
            y0c, x0c = int(max(0, min(H - 800, cy_ - 400))), int(max(0, min(W - 1200, cx_ - 600)))
            s2 = (slice(y0c, y0c + 800), slice(x0c, x0c + 1200))
            name = f'lock_ground{len(per)}_{n}.png'
            ch = (np.asarray(lk[s2]) != np.asarray(raw[s2])).any(-1)
            sheet(S / name, [cond[s2], raw[s2], lk[s2], overlay(np.asarray(raw[s2]), ch)], scale=1)
            per.append({'sheet': name, 'zone': n, 'px': p_, 'm2': round(p_ * PX * PX, 1), 'canvas_xy': [x0c, y0c]})
        del lk
        st['ground'] = {'params': GPARAMS, 'brick': BRICK, 'pavilions': fpi, 'fill_px': px, 'fill_m2': {n: round(t * PX * PX, 1) for n, t in px.items()},
                        'blobs': {n: sum(1 for b in blobs if b[0] == n) for n in ('ground', 'island')}, 'islands': iinfo, 'largest': per}
        log('ground lock:', st['ground']['fill_m2'], 'blobs', st['ground']['blobs'], 'islands', len(iinfo))
    if not a.no_flat_water:
        base, clmed = water_stats(raw, cond, ids, kcls)
        _GW.update(base=base, clmed=clmed)
        n = 0
        with mp.get_context('fork').Pool(min(a.jobs, len(strips))) as pool:
            for s0, k in pool.imap_unordered(_water_strip, strips):
                n += k
        st['water_flat'] = {'params': WFLAT, 'base_rgb': base, 'cond_lum_median': clmed, 'px': n, 'm2': round(n * PX * PX, 1)}
        log('water flat:', st['water_flat'])
    return st


def step_gtest(a):
    """시험: 캔버스 한 구역(--crop)에 지면·나무 잠금(밤섬 포함)과 강물 단색을 적용해 전/후·표시 그림을 쓴다(--out, --name). 대응표는 캔버스 전체에서 만든 것(cache/lock_glut.npz)"""
    meta = load_meta(a)
    cam = Cam(meta)
    raw, cond, ids, v, kcls = (cache(a, n) for n in ('raw', 'cond', 'ids', 'v', 'kcls'))
    treelut = kind_lut(meta, 'tree')
    gluts = get_gluts(a, raw, cond, ids, kcls, treelut)
    x0, y0, x1, y1 = map(int, a.crop.split(','))
    sl = (slice(y0, y1), slice(x0, x1))
    isl, _ = island_cells(kcls)
    r = np.asarray(raw[sl])
    idb = np.asarray(ids[sl])
    out, fills, blobs = ground_lock_region(r, cond[sl], idb, up(kcls, y0, y1)[:, x0:x1], gluts, treelut, strong=up(isl, y0, y1)[:, x0:x1],
                                           hl=host_lut(meta), fakepav=fake_pavilions(raw, cond, ids, meta)[0])
    base, clmed = water_stats(raw, cond, ids, kcls)
    col, water = water_flat_region(cond[sl], idb, np.asarray(v[sl]), up(river_cells(kcls), y0, y1)[:, x0:x1], y0, cam, PARAMS, base, clmed)
    out[water] = col[water]
    O = Path(a.out)
    O.mkdir(parents=True, exist_ok=True)
    Image.fromarray(r).save(O / f'{a.name}_before.png')
    Image.fromarray(out).save(O / f'{a.name}_after.png')
    mk = r.copy()
    for n, f in fills.items():
        if f.any():
            mk = overlay(mk, f, GCOL[n])
    Image.fromarray(mk).save(O / f'{a.name}_marks.png')
    Image.fromarray(np.asarray(cond[sl])).save(O / f'{a.name}_cond.png')
    res = {'crop': [x0, y0, x1, y1], 'fill_m2': {n: round(float(f.sum()) * PX * PX, 1) for n, f in fills.items()}, 'blobs': len(blobs), 'water_m2': round(float(water.sum()) * PX * PX, 1), 'base': base}
    (O / f'{a.name}.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    log(a.name, res)


def _ghost_strip(s0):
    G = _GW
    B, HALO = 2048, 32
    s1 = min(H, s0 + B)
    a0, a1 = max(0, s0 - HALO), min(H, s1 + HALO)
    src = G['src']
    r_, c_, i_, k_ = np.asarray(src[a0:a1]), np.asarray(G['cond'][a0:a1]), np.asarray(G['ids'][a0:a1]), up(G['kcls'], a0, a1)
    m, comps = ghost_seeds(r_, c_, i_, k_, G['hl'], d=ground_expect(r_, c_, i_, k_, G['gluts'], G['treelut'])[2])
    core = m[s0 - a0:s1 - a0]
    o8 = core.reshape(core.shape[0] // 8, 8, W // 8, 8).any((1, 3))
    return s0, o8, [(p_, cy_ + a0, cx_, h_, k_) for p_, cy_, cx_, h_, k_ in comps if s0 <= cy_ + a0 < s1]


def step_ghost(a):
    """[11차] 전체 판에서 지어낸 건물(건물 id 가 없는 곳의 벽돌색 덩어리 + 모양 씨앗)을 세어 목록·위치 그림으로. --src raw(기본) | locked(잠금 뒤 남은 것)"""
    import multiprocessing as mp
    meta = load_meta(a)
    raw, cond, ids, kcls = (cache(a, n) for n in ('raw', 'cond', 'ids', 'kcls'))
    src = raw if a.src == 'raw' else cache(a, 'locked')
    treelut = kind_lut(meta, 'tree')
    _GW.update(src=src, cond=cond, ids=ids, kcls=kcls, hl=host_lut(meta), treelut=treelut, gluts=get_gluts(a, raw, cond, ids, kcls, treelut))
    ov = np.zeros((H // 8, W // 8), bool)
    comps = []
    with mp.get_context('fork').Pool(min(a.jobs, 8)) as pool:
        for s0, o8, cl in pool.imap_unordered(_ghost_strip, list(range(0, H, 2048))):
            ov[s0 // 8:s0 // 8 + o8.shape[0]] = o8
            comps += cl
    hn = {1: 'ground', 2: 'tree', 3: 'bridge', 4: 'pavilion'}
    i4 = np.asarray(ids[2::4, 2::4])
    kk = np.asarray(kcls)
    rows = []
    for p_, cy_, cx_, h_, k_ in sorted(comps, key=lambda t: -t[0]):
        yy, xx = int(cy_), int(cx_)
        rows.append({'px': p_, 'm2': round(p_ * PX * PX, 1), 'canvas_xy': [xx, yy], 'map_xy_1m': [xx // 8, yy // 8], 'host': hn.get(h_, h_), 'color': k_,
                     'kcls': int(kk[min(yy // KF, kk.shape[0] - 1), min(xx // KF, kk.shape[1] - 1)]), 'id_kind': meta['ids'].get(str(int(i4[min(yy // 4, i4.shape[0] - 1), min(xx // 4, i4.shape[1] - 1)])), '')})
    O = Path(a.work) / f'ghost_{a.src}'
    O.mkdir(parents=True, exist_ok=True)
    byh = {}
    for r_ in rows:
        byh.setdefault(r_['host'], [0, 0.0])
        byh[r_['host']][0] += 1
        byh[r_['host']][1] = round(byh[r_['host']][1] + r_['m2'], 1)
    byc = {k: [sum(1 for r_ in rows if r_['color'] == k), round(sum(r_['m2'] for r_ in rows if r_['color'] == k), 1)] for k in GKIND}
    st = {'src': a.src, 'params': {'brick': BRICK, 'shape': SHAPE}, 'count': len(rows), 'm2': round(sum(r_['m2'] for r_ in rows), 1), 'by_color': byc, 'by_host': byh, 'list': rows}
    (O / 'ghost_list.json').write_text(json.dumps(st, ensure_ascii=False, indent=1))
    o8 = np.ascontiguousarray(src[4::8, 4::8]).copy()
    o8 = overlay(o8, nd.maximum_filter(ov.view(np.uint8), 3).astype(bool), (255, 0, 0))
    im = Image.fromarray(o8)
    dr = ImageDraw.Draw(im)
    kc = {'brick': (255, 0, 0), 'light': (255, 255, 255), 'gray': (40, 40, 40), 'other': (255, 0, 255)}
    for i, r_ in enumerate(rows):
        x, y = r_['map_xy_1m']
        rad = 10 + int(np.sqrt(r_['px']) / 16)
        dr.ellipse([x - rad, y - rad, x + rad, y + rad], outline=kc[r_['color']], width=3)
        if r_['host'] == 'pavilion':
            dr.rectangle([x - rad - 4, y - rad - 4, x + rad + 4, y + rad + 4], outline=(0, 0, 255), width=2)
        if i < 60:
            dr.text((x + rad + 2, y - 6), str(i), fill=(255, 255, 0))
    dr.rectangle([0, 0, 760, 30 + 22 * 5], fill=(0, 0, 0))
    dr.text((8, 6), f"ghost buildings ({a.src}): {len(rows)}  {st['m2']} m2   circle colour = wall colour, blue square = pavilion", fill=(255, 255, 255))
    for j, k in enumerate(GKIND):
        dr.ellipse([8, 30 + 22 * j, 24, 46 + 22 * j], outline=kc[k], width=3)
        dr.text((32, 32 + 22 * j), f"{k}: {byc[k][0]}  ({byc[k][1]} m2)", fill=(255, 255, 255))
    im.save(O / 'ghost_overview.png')
    for f_ in O.glob('ghost*_*.png'):
        f_.unlink()
    shown = rows[:16] + [r_ for k in ('light', 'gray', 'other') for r_ in [x for x in rows if x['color'] == k][:8]]
    for i, r_ in enumerate(shown):
        x, y = r_['canvas_xy']
        y0c, x0c = int(max(0, min(H - 500, y - 250))), int(max(0, min(W - 700, x - 350)))
        s2 = (slice(y0c, y0c + 500), slice(x0c, x0c + 700))
        Image.fromarray(np.concatenate([np.asarray(cond[s2]), np.asarray(src[s2])], 1)).save(O / f"ghost{i:02d}_{r_['color']}.png")
    log('ghost', a.src, st['count'], st['m2'], 'by color', byc, 'by host', byh)


def step_t11(a):
    """[11차] 시험: --crop 구역에 잠금 전부(교량·호안 → 지면·나무·정자·벽돌 씨앗 → 강물 단색 → 지붕·벽)를 적용해 --out 에 전(--before 작업 폴더의 locked)/후 그림"""
    global HOSTL
    meta = load_meta(a)
    cam = Cam(meta)
    raw, cond, ids, v, kcls = (cache(a, n) for n in ('raw', 'cond', 'ids', 'v', 'kcls'))
    HOSTL = host_lut(meta)
    set_mat_lm(a, meta)
    x0, y0, x1, y1 = map(int, a.crop.split(','))
    M = 400
    bx0, by0, bx1, by1 = max(0, x0 - M), max(0, y0 - M), min(W, x1 + M), min(H, y1 + M)
    sl = (slice(by0, by1), slice(bx0, bx1))
    r, c, idb, vb = np.asarray(raw[sl]), np.asarray(cond[sl]), np.asarray(ids[sl]), np.asarray(v[sl])
    kf = up(kcls, by0, by1)[:, bx0:bx1]
    rc = river_cells(kcls)
    kc = up(rc, by0, by1)[:, bx0:bx1]
    blut = bridge_lut(meta)
    C = Path(a.work) / 'cache'
    z = np.load(C / 'lock_zlut.npz')
    zl = {zn: ([(int(b), z[f'{zn}{b}']) for b in (5, 4, 3)] if f'{zn}5' in z else None) for zn in ('bridge', 'bank')}
    z = np.load(C / 'lock_lut.npz')
    wl = [(int(b), z[f'l{b}']) for b in (5, 4, 3)]
    out = r.copy()
    ZP = json.loads(json.dumps(ZPARAMS))
    if a.zp:
        ZP['bridge'].update(json.loads(a.zp))
    o2, zf, _ = zone_lock_region(r, c, idb, vb, kf, kc, by0, cam, PARAMS, zl, wl, blut, ZP)
    zany = zf['bridge'] | zf['bank'] | zf['ring']
    out[zany] = o2[zany]
    zf['span'] = np.zeros(idb.shape, bool)
    if SPAN['on'] and zf['bridge'].any():          # [12차] 덩어리가 닿은 교량 경간 전체
        def fm_get(ys, xs, bf=zf['bridge']):
            f_ = np.zeros((ys.stop - ys.start, xs.stop - xs.start), bool)
            oy0, oy1, ox0, ox1 = max(ys.start, by0), min(ys.stop, by1), max(xs.start, bx0), min(xs.stop, bx1)
            if oy0 < oy1 and ox0 < ox1:
                f_[oy0 - ys.start:oy1 - ys.start, ox0 - xs.start:ox1 - xs.start] = bf[oy0 - by0:oy1 - by0, ox0 - bx0:ox1 - bx0]
            return f_
        ks = set(int(x) for x in np.unique(idb[zf['bridge'] & blut[idb]]))
        for ys, xs, R, new_, info in bridge_spans(raw, cond, ids, v, cam, blut, zl, fm_get, ks):
            full = np.zeros(R.shape + (3,), np.uint8)
            full[R] = new_
            oy0, oy1, ox0, ox1 = max(ys.start, by0), min(ys.stop, by1), max(xs.start, bx0), min(xs.stop, bx1)
            if oy0 < oy1 and ox0 < ox1:
                Rr = R[oy0 - ys.start:oy1 - ys.start, ox0 - xs.start:ox1 - xs.start]
                dst = out[oy0 - by0:oy1 - by0, ox0 - bx0:ox1 - bx0]
                dst[Rr] = full[oy0 - ys.start:oy1 - ys.start, ox0 - xs.start:ox1 - xs.start][Rr]
                zf['span'][oy0 - by0:oy1 - by0, ox0 - bx0:ox1 - bx0] |= Rr
    treelut = kind_lut(meta, 'tree')
    gluts = get_gluts(a, raw, cond, ids, kcls, treelut)
    fpf = C / 'fakepav.npy'
    if fpf.exists():
        fpl = np.load(fpf)
    else:
        fpl = fake_pavilions(raw, cond, ids, meta)[0]
        np.save(fpf, fpl)
    isl, _ = island_cells(kcls)
    og, gfl, _ = ground_lock_region(r, c, idb, kf, gluts, treelut, strong=up(isl, by0, by1)[:, bx0:bx1], hl=HOSTL, fakepav=fpl)
    gany = gfl['ground'] | gfl['tree'] | gfl['island'] | gfl['pavilion']
    out[gany] = og[gany]
    base, clmed = water_stats(raw, cond, ids, kcls)
    col, water = water_flat_region(c, idb, vb, kc, by0, cam, PARAMS, base, clmed)
    out[water] = col[water]
    ro, rf, infos, _ = roof_lock_region(r, c, idb, vb, by0, cam, roof_kind_lut(meta))
    rany = np.zeros(idb.shape, bool)
    for n_, m_ in rf.items():
        rany |= m_
    out[rany] = ro[rany]
    cs = (slice(y0 - by0, y1 - by0), slice(x0 - bx0, x1 - bx0))
    O = Path(a.out)
    O.mkdir(parents=True, exist_ok=True)
    bef = np.asarray(np.load(Path(a.before) / 'cache' / 'locked.npy', mmap_mode='r')[y0:y1, x0:x1]) if a.before else r[cs]
    Image.fromarray(bef).save(O / f'{a.name}_before.png')
    Image.fromarray(out[cs]).save(O / f'{a.name}_after.png')
    mk = r.copy()
    for n_, m_ in list(zf.items()) + list(gfl.items()) + list(rf.items()):
        if m_.any():
            colr = {**ZCOL, **GCOL, **RCOL}[n_]
            mk = overlay(mk, m_, colr)
    Image.fromarray(mk[cs]).save(O / f'{a.name}_marks.png')
    Image.fromarray(c[cs]).save(O / f'{a.name}_cond.png')
    res = {'crop': [x0, y0, x1, y1], 'zone_m2': {k: round(float(m_[cs].sum()) * PX * PX, 1) for k, m_ in zf.items()},
           'ground_m2': {k: round(float(m_[cs].sum()) * PX * PX, 1) for k, m_ in gfl.items()}, 'roof_m2': {k: round(float(m_[cs].sum()) * PX * PX, 1) for k, m_ in rf.items()},
           'buildings': {f"{k} {meta['ids'][str(k)]}": i for k, i in infos.items() if i.get('wall_px') or i.get('aptwall_px') or i.get('apt_brick_px')}}
    (O / f'{a.name}.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    log(a.name, res['zone_m2'], res['ground_m2'], res['roof_m2'])


def overlay_zones(img, fills):
    o = np.asarray(img).copy()
    for zn, m in fills.items():
        if m.any():
            o = overlay(o, m, ZCOL[zn])
    return o


def overlay(img, mask, col=(255, 0, 255)):
    o = np.asarray(img).copy()
    edge = mask & ~sq(mask, 2, nd.minimum_filter)
    o[mask] = (o[mask] * 0.55 + np.array(col) * 0.45).astype(np.uint8)
    o[edge] = col
    return o


def sheet(path, panels, scale=2):
    ims = [Image.fromarray(np.ascontiguousarray(p)).reduce(scale) if scale > 1 else Image.fromarray(np.ascontiguousarray(p)) for p in panels]
    w, h = ims[0].size
    out = Image.new('RGB', (w * 2 + 8, h * 2 + 8), (255, 255, 255))
    for i, im in enumerate(ims[:4]):
        out.paste(im.convert('RGB'), ((i % 2) * (w + 8), (i // 2) * (h + 8)))
    out.save(path)


def inject(raw, water, seed=7):
    """시험용: 강물 위에 지어낸 배·섬·다리 흉내를 그려 넣는다(잠금이 되돌리는지 보려는 것). raw 사본을 돌려준다."""
    im = Image.fromarray(np.array(raw))
    dr = ImageDraw.Draw(im)
    h, w = water.shape
    rs = np.random.RandomState(seed)
    ys, xs = np.nonzero(water[::16, ::16])
    n = 0
    for k in rs.permutation(len(ys))[:400]:
        x, y = int(xs[k]) * 16, int(ys[k]) * 16
        if not (60 < x < w - 260 and 60 < y < h - 160) or not water[y - 40:y + 140:20, x - 40:x + 240:20].all():
            continue
        t = n % 3
        if t == 0:    # 배: 흰 선체 + 붉은 띠
            dr.polygon([(x, y + 20), (x + 120, y), (x + 150, y + 22), (x + 120, y + 48), (x, y + 44)], fill=(238, 236, 228), outline=(40, 44, 52))
            dr.rectangle([x + 30, y + 10, x + 100, y + 30], fill=(190, 60, 48))
        elif t == 1:  # 섬: 모래 + 풀
            dr.ellipse([x, y, x + 200, y + 110], fill=(214, 198, 150), outline=(120, 110, 80))
            dr.ellipse([x + 40, y + 20, x + 160, y + 80], fill=(96, 150, 70))
        else:         # 다리 조각: 회색 상판 + 교각
            dr.polygon([(x, y + 60), (x + 220, y), (x + 230, y + 18), (x + 10, y + 78)], fill=(150, 150, 146), outline=(60, 60, 64))
            dr.rectangle([x + 100, y + 40, x + 118, y + 100], fill=(120, 120, 118))
        n += 1
        if n >= 9:
            break
    return np.asarray(im), n


def step_lock(a):
    W_ = Path(a.work)
    S = W_ / 'sheets'
    S.mkdir(parents=True, exist_ok=True)
    cam = Cam(load_meta(a))
    raw, cond, ids, v, kcls = (cache(a, n) for n in ('raw', 'cond', 'ids', 'v', 'kcls'))
    P = dict(PARAMS)
    if a.thr:
        P['thr'] = a.thr
    meta = load_meta(a)
    blut = bridge_lut(meta)
    ZP = json.loads(json.dumps(ZPARAMS))
    if a.zthr:
        ZP['bridge']['thr'] = ZP['bank']['thr'] = a.zthr
    if a.zp:
        ZP['bridge'].update(json.loads(a.zp))
    zlutf = W_ / 'cache' / 'lock_zlut.npz'
    global ZWHOLE, HOSTL
    HOSTL = host_lut(meta)
    set_mat_lm(a, meta)
    if a.bridge_whole:          # [11차] 기본은 덩어리 + 벽돌 씨앗(난간·차선 픽셀아트를 남긴다). 10차의 강 교량 전체 되돌림은 --bridge-whole
        ZWHOLE = river_bridge_lut(ids, kcls, blut)
        log('river bridges (whole deck → expected):', [f"{k} {meta['ids'][str(k)]}" for k in np.nonzero(ZWHOLE)[0]])

    def get_zluts():
        if zlutf.exists():
            z = np.load(zlutf)
            return {zn: ([(int(b), z[f'{zn}{b}']) for b in (5, 4, 3)] if f'{zn}5' in z else None) for zn in ('bridge', 'bank')}
        zl = zone_luts(raw, cond, ids, kcls, blut)
        np.savez(zlutf, **{f'{zn}{b}': l for zn, ls in zl.items() if ls for b, l in ls})
        return zl

    rc = river_cells(kcls)
    ys, xs = np.nonzero(rc)
    by0, by1 = max(0, ys.min() * KF - 64), min(H, (ys.max() + 1) * KF + 64)
    lutf = W_ / 'cache' / 'lock_lut.npz'

    def get_luts(sl, y0, save):
        if save and lutf.exists():
            z = np.load(lutf)
            return [(int(b), z[f'l{b}']) for b in (5, 4, 3)]
        wm = water_mask(np.asarray(ids[sl]), np.asarray(v[sl]), up(rc, sl[0].start, sl[0].stop)[:, sl[1]], y0, cam, P)
        luts = color_lut(cond[sl], raw[sl], wm)
        if save:
            np.savez(lutf, **{f'l{b}': l for b, l in luts})
        log('lut bins filled', {b: int((~np.isnan(l[:, 0])).sum()) for b, l in luts})
        return luts

    if a.crop:
        x0, y0, x1, y1 = map(int, a.crop.split(','))
        sl = (slice(y0, y1), slice(x0, x1))
        kc = up(rc, y0, y1)[:, x0:x1]
        luts = get_luts(sl, y0, False) if a.local_lut else get_luts((slice(by0, by1), slice(0, W)), by0, True)
        r = np.asarray(raw[sl])
        ninj = 0
        if a.inject:
            r, ninj = inject(r, water_mask(np.asarray(ids[sl]), np.asarray(v[sl]), kc, y0, cam, P))
        out, fill, info, ds, water = lock_region(r, np.asarray(cond[sl]), np.asarray(ids[sl]), np.asarray(v[sl]), kc, y0, cam, P, luts)
        zinfo = {}
        if not a.no_zones:
            zl = zone_luts(raw, cond, ids, kcls, blut, (y0, y1), slice(x0, x1)) if a.local_lut else get_zluts()
            out_w = out
            out, zf, zb = zone_lock_region(out_w, np.asarray(cond[sl]), np.asarray(ids[sl]), np.asarray(v[sl]), up(kcls, y0, y1)[:, x0:x1], kc, y0, cam, P, zl, luts, blut, ZP)
            zinfo = {'zones': {zn: {'fill_px': int(m.sum()), 'fill_m2': round(float(m.sum()) * PX * PX, 1), 'blobs': sum(1 for b in zb if b[0] == zn)} for zn, m in zf.items()}}
            zf['ring'] = zf['ring'] | fill      # 표시용: 강물 잠금이 바꾼 곳도 청록으로
            fill_show = zf
        tag = f'crop_{x0}_{y0}' + ('_inject' if a.inject else '')
        sheet(S / f'{tag}.png', [cond[sl], r, out, overlay(r, fill) if a.no_zones else overlay_zones(r, fill_show)], scale=a.sheet_scale)
        info.update(zinfo)
        Image.fromarray(np.clip(ds, 0, 255).astype(np.uint8)).reduce(2).save(S / f'{tag}_dist.png')
        diff_out = int((np.abs(out.astype(np.int16) - np.asarray(cond[sl]).astype(np.int16)).max(-1) > 48)[water].sum()) if a.inject else None
        res = {'crop': [x0, y0, x1, y1], 'injected': ninj, **info, 'fill_m2': round(info['fill_px'] * PX * PX, 1),
               'changed_outside_water_px': int((out != r).any(-1)[~water].sum()), 'water_px_far_from_cond_after_lock(inject only)': diff_out}
        (S / f'{tag}.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
        log(tag, res)
        return
    sl = (slice(by0, by1), slice(0, W))
    log('river rows', by0, by1)
    luts = get_luts(sl, by0, True)
    out, fill, info, ds, water = lock_region(raw[sl], cond[sl], np.asarray(ids[sl]), np.asarray(v[sl]), up(rc, by0, by1), by0, cam, P, luts)
    locked = np.lib.format.open_memmap(W_ / 'cache' / 'locked.npy', mode='w+', dtype=np.uint8, shape=(H, W, 3))
    locked[:] = raw
    locked[sl] = out
    locked.flush()
    changed_out = int((out != np.asarray(raw[sl])).any(-1)[~water].sum())
    zst = {'skipped': True}
    if not a.no_zones:
        # 교량·호안/선착장 잠금: 캔버스 전체를 띠(2048행 + 위아래 96행 겹침)로 돈다. 입력은 강물 잠금 전 raw, 결과는 locked 에 덮어쓴다(두 잠금의 픽셀은 겹치지 않는다. ring 만 강물)
        zl = get_zluts()
        B, HALO = 2048, 96
        zpx = {'bridge': 0, 'bank': 0, 'ring': 0, 'ghost': 0}
        zblobs = []
        ov = np.zeros((H // 8, W // 8), np.uint8)
        bfill = np.zeros((H, W), bool) if SPAN['on'] and ZWHOLE is None else None      # [12차] 교량 덩어리 채움(경간 단위 되돌림의 씨앗)
        for s0 in range(0, H, B):
            s1 = min(H, s0 + B)
            a0, a1 = max(0, s0 - HALO), min(H, s1 + HALO)
            idb = np.asarray(ids[a0:a1])
            kf = up(kcls, a0, a1)
            if not (blut[idb[::4, ::4]].any() or ((kf[::4, ::4] == 13) | (kf[::4, ::4] == 16)).any()):
                continue
            src = np.asarray(locked[a0:a1])
            o2, zf, zb = zone_lock_region(np.asarray(raw[a0:a1]), cond[a0:a1], idb, np.asarray(v[a0:a1]), kf, up(rc, a0, a1), a0, cam, P, zl, luts, blut, ZP)
            core = slice(s0 - a0, s1 - a0)
            anyf = zf['bridge'] | zf['bank'] | zf['ring']
            if anyf[core].any():
                dst = np.array(src[core])
                dst[anyf[core]] = o2[core][anyf[core]]
                locked[s0:s1] = dst
            if bfill is not None:
                bfill[s0:s1] = zf['bridge'][core] & blut[idb[core]]
            for k_, zn in enumerate(('bridge', 'bank', 'ring', 'ghost')):
                m = zf[zn]
                zpx[zn] += int(m[core].sum())
                mm = m[core]
                o8 = mm.reshape(mm.shape[0] // 8, 8, W // 8, 8).any((1, 3))
                ov[s0 // 8:s0 // 8 + o8.shape[0]][o8] = k_ + 1
            zblobs += [(zn, px, cy_ + a0, cx_) for zn, px, cy_, cx_ in zb if s0 <= cy_ + a0 < s1]
            log('zone lock rows', s0, s1, {k: int(m[core].sum()) for k, m in zf.items()})
        spans = []
        if bfill is not None and bfill.any():      # [12차] 덩어리가 닿은 교량 경간 전체를 기대색(+ id 별 색 이동)으로
            cnt = np.bincount(np.asarray(ids[::2, ::2])[bfill[::2, ::2]], minlength=65536) * 4
            ks = set(int(k) for k in np.nonzero(cnt >= SPAN['min_px'])[0])
            log('bridge span ids', len(ks))
            for ys, xs, R, new_, sinfo in bridge_spans(raw, cond, ids, v, cam, blut, zl, lambda ys, xs: bfill[ys, xs], ks):
                blk = np.array(locked[ys, xs])
                blk[R] = new_
                locked[ys, xs] = blk
                spans.append(sinfo)
                o8m = np.zeros((H // 8, W // 8), bool)
                yy, xx = np.nonzero(R)
                o8m[np.minimum((yy + ys.start) // 8, H // 8 - 1), np.minimum((xx + xs.start) // 8, W // 8 - 1)] = True
                ov[o8m] = 5
            del bfill
        zpx['span'] = sum(i['px'] for i in spans)
        locked.flush()
        o8 = np.ascontiguousarray(locked[4::8, 4::8]).copy()
        for k_, zn in enumerate(('bridge', 'bank', 'ring', 'ghost', 'span')):
            o8 = overlay(o8, ov == k_ + 1, ZCOL[zn])
        Image.fromarray(o8).save(S / 'lock_zones_overview.png')
        zper = []
        for zn, px, cy_, cx_ in sorted(zblobs, key=lambda b: -b[1])[:12]:
            y0c, x0c = int(max(0, min(H - 800, cy_ - 400))), int(max(0, min(W - 1200, cx_ - 600)))
            s2 = (slice(y0c, y0c + 800), slice(x0c, x0c + 1200))
            name = f'lock_zone{len(zper)}_{zn}.png'
            ch = (np.asarray(locked[s2]) != np.asarray(raw[s2])).any(-1)
            sheet(S / name, [cond[s2], raw[s2], locked[s2], overlay(np.asarray(raw[s2]), ch)], scale=1)
            zper.append({'sheet': name, 'zone': zn, 'px': px, 'm2': round(px * PX * PX, 1), 'canvas_xy': [x0c, y0c]})
        zst = {'params': ZP, 'fill_px': zpx, 'fill_m2': {k: round(n_ * PX * PX, 1) for k, n_ in zpx.items()},
               'blobs': {zn: sum(1 for b in zblobs if b[0] == zn) for zn in ('bridge', 'bank')}, 'largest': zper, 'spans': spans, 'span_params': SPAN}
        log('zone lock:', zst['fill_m2'], 'blobs', zst['blobs'])
    # [10차] 지면·나무 잠금(밤섬 포함) → 강물 단색: 일꾼이 locked 파일에 직접 쓴다. 강물 단색이 위의 강물 잠금·ring 을 전부 덮는다
    gst = {}
    if not (a.no_ground and a.no_flat_water):
        locked.flush()
        del locked
        gst = ground_water_full(a, raw, cond, ids, v, kcls, rc, cam, meta, P, S, W_ / 'cache' / 'locked.npy')
        locked = np.load(W_ / 'cache' / 'locked.npy', mmap_mode='r+')
    # [8차] 지붕 잠금 · 랜드마크 벽 잠금: 입력은 raw, 결과는 locked 에 덮어쓴다(건물 id 화소라 강물·교량·호안 잠금과 겹치지 않는다)
    rst = {'skipped': True}
    if not a.no_roof:
        rst = roof_lock_full(a, raw, cond, ids, v, cam, meta, locked, S)
    # 시트: 전체 1/8(바꾼 곳 표시) + 큰 덩어리 6곳(cond | raw | 잠금 뒤 | 표시)
    r8 = np.asarray(Image.fromarray(np.ascontiguousarray(out)).reduce(8))
    f8 = fill.reshape(fill.shape[0] // 8, 8, W // 8, 8).any((1, 3)) if fill.shape[0] % 8 == 0 else fill[::8, ::8][:r8.shape[0], :r8.shape[1]]
    Image.fromarray(overlay(r8, f8[:r8.shape[0], :r8.shape[1]])).save(S / 'lock_overview.png')
    per = []
    if fill.any():
        lab, n = nd.label(fill)
        sz = np.bincount(lab.ravel(), minlength=n + 1)
        sz[0] = 0
        for i in np.argsort(sz)[::-1][:6]:
            if sz[i] == 0:
                break
            yy, xx = nd.find_objects((lab == i).astype(np.uint8))[0]
            cy, cx = (yy.start + yy.stop) // 2, (xx.start + xx.stop) // 2
            y0c, x0c = max(0, min(fill.shape[0] - 800, cy - 400)), max(0, min(W - 1200, cx - 600))
            s2 = (slice(y0c, y0c + 800), slice(x0c, x0c + 1200))
            name = f'lock_blob{len(per)}.png'
            sheet(S / name, [cond[sl][s2], raw[sl][s2], out[s2], overlay(np.asarray(raw[sl][s2]), fill[s2])], scale=1)
            per.append({'sheet': name, 'px': int(sz[i]), 'm2': round(float(sz[i]) * PX * PX, 1), 'canvas_xy': [int(x0c), int(y0c + by0)]})
    st = {'params': P, 'rows': [int(by0), int(by1)], 'water_px': info['water_px'], 'water_m2': round(info['water_px'] * PX * PX, 1),
          'fill_px': info['fill_px'], 'fill_m2': round(info['fill_px'] * PX * PX, 1), 'blobs': info['blobs'],
          'skipped_huge_components': info['skipped_huge_components'], 'changed_outside_water_px': changed_out, 'largest': per, 'zones': zst, 'roof': rst, **gst}
    (W_ / 'lock_stats.json').write_text(json.dumps(st, ensure_ascii=False, indent=1))
    log('lock: fill', st['fill_m2'], 'm² of water', st['water_m2'], 'm², blobs', st['blobs'], 'changed outside water', changed_out)


# ───────────────────────── quant(팔레트 + 피라미드) ─────────────────────────
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


QRESCUE = {'err': 30.0, 'k': 12, 'min_px': 1500, 'max_swap': 8}


def rescue_palette(small, pal, n, P=QRESCUE):
    """[12차] median-cut 이 버린 드문 색(r7: 연못 하늘색 — halfF3 랜드마크 16색 면들이 칸을 가져감)을 되살린다: 1/4 그림에서 팔레트 오차 > err 인 화소를
    k 색으로 묶고, min_px 넘는 묶음의 중심을 가장 적게 쓰인 팔레트 칸과 바꾼다(바꾼 칸을 쓰던 화소의 늘어난 오차가 묶음이 줄인 오차보다 작을 때만) → (팔레트, [(옛 색, 새 색, px)])"""
    px = small.reshape(-1, 3).astype(np.float32)[::3]
    Pf = np.array(pal, np.float32).reshape(-1, 3)[:n]
    out = []
    for _ in range(P['max_swap']):
        d = ((px[:, None, :] - Pf[None]) ** 2).sum(-1)
        ix = d.argmin(1)
        e = np.sqrt(d[np.arange(len(px)), ix])
        hi = e > P['err']
        if hi.sum() < P['min_px']:
            break
        q = Image.fromarray(px[hi].astype(np.uint8).reshape(1, -1, 3)).quantize(colors=P['k'], method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE, kmeans=2)
        qi = np.asarray(q).ravel()
        cen = np.array(q.getpalette()[:P['k'] * 3], np.float32).reshape(-1, 3)
        cnt = np.bincount(qi, minlength=P['k'])
        j = int(cnt.argmax())
        if cnt[j] < P['min_px']:
            break
        use = np.bincount(ix, minlength=n)
        gain = (e[hi][qi == j] - np.sqrt(((px[hi][qi == j] - cen[j]) ** 2).sum(-1))).sum()
        best = None
        for c_ in np.argsort(use)[:6]:
            m = ix == c_
            P2 = np.delete(Pf, c_, 0)
            loss = (np.sqrt(((px[m][:, None] - P2[None]) ** 2).sum(-1)).min(1) - e[m]).sum() if m.any() else 0.0
            if best is None or loss < best[1]:
                best = (int(c_), float(loss))
        if best[1] >= gain:
            break
        out.append((Pf[best[0]].astype(int).tolist(), cen[j].astype(int).tolist(), int(cnt[j]) * 3))
        Pf[best[0]] = cen[j]
    pal = np.clip(np.round(Pf), 0, 255).astype(int).ravel().tolist()
    return pal, out


def step_quant(a):
    W_ = Path(a.work)
    src = W_ / 'cache' / 'locked.npy'
    rgb = np.load(src if src.exists() else W_ / 'cache' / 'raw.npy', mmap_mode='r')
    small = Image.fromarray(np.ascontiguousarray(rgb[::4, ::4]))
    pimg = small.quantize(colors=a.colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE, kmeans=3)
    pal = pimg.getpalette()[:a.colors * 3]
    pal, resc = rescue_palette(np.asarray(small), pal, a.colors)
    pal = pal + pal[:3] * (256 - a.colors)
    log('palette', a.colors, 'rescued', resc)
    ix8 = quantize_big(rgb, pal, a.jobs)
    save_p(ix8, pal, W_ / 'p0625.png')        # 파일 이름은 경복궁과 같게 둔다(make_tiles 규약). 여의도에서는 z8 = 12.5 cm
    Pf = np.array(pal, np.float32).reshape(-1, 3)
    for name, f in (('p0125', 2), ('p025', 4), ('p05', 8)):
        rq = Pf[ix8].reshape(H // f, f, W // f, f, 3).mean((1, 3)).round().astype(np.uint8)
        ix = quantize_big(rq, pal, a.jobs)
        save_p(ix, pal, W_ / f'{name}.png')
        log(name, ix.shape)
    e = np.sqrt(((Pf[ix8[::7, ::7]] - rgb[::7, ::7].astype(np.float32)) ** 2).sum(-1))
    err = {'mean': float(e.mean()), 'p95': float(np.percentile(e, 95))}
    (W_ / 'palette.json').write_text(json.dumps({'colors': a.colors, 'palette': pal[:a.colors * 3], 'rgb_error_z8': err}))
    log('quant error', err)


# ───────────────────────── maps(depth_rg8 · classes · crown) ─────────────────────────
# 앱 클래스(경복궁과 같은 0–11): 0 없음 1 바탕 지면 2 도로 3 녹지 4 물 5 궁궐 마당 6 지붕 7 벽 8 궁궐 지붕 9 궁궐 벽 10 나무 11 보행 광장
# 여의도 분류(classes_05m 0–17, 지면 id 1 에만 씀) → 앱 클래스
KCLS_TO_APP = {0: 1, 1: 2, 2: 11, 3: 3, 4: 1, 5: 4, 6: 1, 7: 1, 8: 1, 9: 1, 10: 2, 11: 3, 12: 2, 13: 11, 14: 3, 15: 3, 16: 11, 17: 4}
KCLS_NAMES = {0: '바탕 지면', 1: '도로(차도)', 2: '광장·보도', 3: '잔디·숲 바닥', 5: '강물(한강)', 12: '철도 선로 바닥', 13: '호안', 14: '공원 잔디마당', 15: '습지', 16: '선착장·부잔교', 17: '작은 물(연못·샛강 수로·수영장)'}
APP_NAMES = {0: '없음', 1: '바탕 지면', 2: '도로', 3: '녹지', 4: '물', 5: '(궁궐 마당: 여의도 미사용)', 6: '지붕', 7: '벽', 8: '(궁궐 지붕: 미사용)', 9: '(궁궐 벽: 미사용)', 10: '나무', 11: '보행 광장·포장'}
FOOT_BRIDGE = ('샛강다리', '횡단보도', '한강남자전거길', '한강북자전거길', '한강 자전거길 출입로', '새남터다리')
# 물체 종류(meta) → 유형: 1 건물(지붕 6 / 벽 7), 2 차도 교량(윗면 2 / 옆면·교각 7), 3 보행 교량·승강장(윗면 11 / 옆면 7), 4 나무(10)
OBJ_RULES = [('건물: lowrise, lowrise_synthetic, apartment, tower, landmark:*, park_pavilion, station_building, station_entrance:*', '지붕 6 / 벽 7'),
             ('차도 교량: bridge:* (아래 보행 교량 제외)', '윗면(수평면) 2 도로 / 옆면·교각·난간 7 벽'),
             ('보행 교량: bridge:' + ', '.join(FOOT_BRIDGE) + ' · 승강장 station_platform', '윗면 11 보행 / 옆면 7 벽'),
             ('나무: tree(id 30000)', '10 나무')]


def obj_type(kind, scene_roads=None, idn=None):
    k = kind.split(':')[0]
    if k == 'ground':
        return 0
    if k == 'tree':
        return 4
    if k == 'bridge':
        nm = kind.split(':', 1)[1] if ':' in kind else ''
        if nm in FOOT_BRIDGE:
            return 3
        if nm == 'generic' and scene_roads is not None and idn is not None and 0 <= idn - 20000 < len(scene_roads):
            return 3 if scene_roads[idn - 20000].get('cls') in ('foot', 'cycle') else 2   # 이름 없는 교량은 장면 도로 등급으로 가른다
        return 2
    if k == 'station_platform':
        return 3
    return 1


def step_maps(a):
    W_ = Path(a.work)
    meta = load_meta(a)
    cam = Cam(meta)
    cond, ids, v, kcls = (cache(a, n) for n in ('cond', 'ids', 'v', 'kcls'))
    roads = json.load(open(a.scene))['roads'] if a.scene and Path(a.scene).exists() else None
    typ = np.ones(65536, np.uint8)
    for k, t in meta['ids'].items():
        typ[int(k)] = obj_type(t, roads, int(k))
    k2a = np.array([KCLS_TO_APP.get(i, 1) for i in range(256)], np.uint8)
    per = 2 * PX / cam.ey[2]
    depth_v = np.zeros((MH, MW), np.uint16)
    cls = np.zeros((MH, MW), np.uint8)
    R = np.ones((MH, MW), np.uint8)
    crown_frac = np.zeros((MH, MW), np.float32)
    lo = hi = 0
    dmin, dmax = 1e9, -1e9
    fix_w = fix_b = 0
    n_id = np.zeros(65536, np.int64)
    sx = np.zeros(65536, np.float64)
    sy = np.zeros(65536, np.float64)
    want = [int(k) for k, t in meta['ids'].items() if t.startswith('landmark') or t.startswith('bridge') or t.startswith('station_building')]
    top = {k: None for k in want}
    box = {k: [W, H, 0, 0] for k in want}
    BAND = 64 * F
    for y0 in range(0, H, BAND):
        y1 = min(H, y0 + BAND)
        my0, my1 = y0 // F, y1 // F
        vv = np.asarray(v[y0:y1])
        idb = np.asarray(ids[y0:y1])
        cb = np.asarray(cond[y0:y1])
        # 깊이: 칸(8×8)의 가장 가까운 면 = 최솟값. 지면을 평면으로 펴지 않는다(여의도 지면은 실제 형상: 수면 −1.8 m, 호안 경사, 0 m 지면)
        d = (cam.z0 + vv.astype(np.float64) * cam.step).reshape(my1 - my0, F, MW, F).min((1, 3))
        dmin, dmax = min(dmin, float(d.min())), max(dmax, float(d.max()))
        q = np.round((d - D0) / DSTEP)
        lo += int((q < 0).sum())
        hi += int((q > 65534).sum())
        depth_v[my0:my1] = np.clip(q, 0, 65534).astype(np.uint16)
        # 그림 px 클래스
        hgt = cam.height(vv, y0)
        slope = np.zeros_like(hgt)
        slope[1:-1] = (hgt[:-2] - hgt[2:]) / per
        if y0 > 0:
            slope[0] = slope[1]
        wall = (slope > 0.55) & (slope < 2.2)
        t = typ[idb]
        c = np.zeros(idb.shape, np.uint8)
        g = t == 0
        gc = k2a[up(kcls, y0, y1)]
        # 물가 다듬기(분류 맵은 0.5 m 칸이라 물가가 계단진다): 수면 높이인 지면은 물, 수면보다 0.6 m 넘게 높은데 강물 칸이면 포장(호안)
        w_low = g & (hgt < WL + 0.25) & (gc != 4)
        b_high = g & (hgt > WL + 0.6) & (gc == 4) & (np.asarray(up(kcls, y0, y1)) == 5)
        fix_w += int(w_low.sum())
        fix_b += int(b_high.sum())
        gc[w_low] = 4
        gc[b_high] = 11
        c[g] = gc[g]
        b = t == 1
        c[b] = np.where(wall[b], 7, 6)
        b = t == 2
        c[b] = np.where(wall[b], 7, 2)
        b = t == 3
        c[b] = np.where(wall[b], 7, 11)
        c[t == 4] = 10
        cnt = np.stack([(c == k).reshape(my1 - my0, F, MW, F).sum((1, 3)) for k in range(12)], -1)
        cls[my0:my1] = (cnt * 16 + np.arange(12)).argmax(-1).astype(np.uint8)   # 다수결, 동률은 큰 번호(가리는 쪽)
        # 수관: 나무 픽셀 중 줄기(조건 렌더가 붉은 갈색)를 뺀 비율
        tr = t == 4
        trunk = cb[..., 0].astype(np.int16) > cb[..., 1].astype(np.int16) + 6
        frac = (tr & ~trunk).reshape(my1 - my0, F, MW, F).mean((1, 3))
        crown_frac[my0:my1] = frac
        has = frac > 0.04
        rr = np.ones(frac.shape, np.uint8)
        rr[has] = 2 + np.round(frac[has] * 253).astype(np.uint8)
        R[my0:my1] = rr
        # id 통계(랜드마크·교량 앵커용)
        flat = idb.ravel()
        n_id += np.bincount(flat, minlength=65536)
        xs = np.tile(np.arange(W, dtype=np.float64), y1 - y0)
        sx += np.bincount(flat, xs, 65536)
        sy += np.bincount(flat, np.repeat(np.arange(y0, y1, dtype=np.float64), W), 65536)
        present = np.nonzero(np.bincount(flat, minlength=65536))[0]
        for k in set(want) & set(present.tolist()):
            yy, xx = np.nonzero(idb == k)
            bx = box[k]
            box[k] = [min(bx[0], int(xx.min())), min(bx[1], int(yy.min()) + y0), max(bx[2], int(xx.max())), max(bx[3], int(yy.max()) + y0)]
            if top[k] is None:
                r0 = yy.min()
                top[k] = [float(xx[yy == r0].mean()), int(r0 + y0)]
        log('maps rows', my0, my1)
    assert lo == 0 and hi == 0, f'깊이가 16비트 범위 밖: 아래 {lo}칸, 위 {hi}칸 (D0 {D0}, step {DSTEP}, 실제 {dmin:.1f}–{dmax:.1f} m)'
    rg = np.zeros((MH, MW, 3), np.uint8)
    rg[..., 0] = depth_v >> 8
    rg[..., 1] = depth_v & 255
    Image.fromarray(rg, 'RGB').save(W_ / 'depth_rg8.png', optimize=True)
    Image.fromarray(cls, 'L').save(W_ / 'classes.png', optimize=True)
    # 그루 번호(G): 나무가 id 하나(30000)라 id 해시를 쓸 수 없다 → 장면의 나무 점을 화면에 투영해 수관 칸마다 가장 가까운 나무의 번호 해시
    G = np.zeros((MH, MW), np.uint8)
    ntree = 0
    if a.scene and Path(a.scene).exists():
        from scipy.spatial import cKDTree
        tr = np.array(json.load(open(a.scene))['trees'], np.float64)
        p = cam.proj(np.c_[tr[:, :2], np.full(len(tr), 4.5)]) / F     # 수관 가운데 높이 약 4.5 m 로 가정
        ok = (p[:, 0] > -8) & (p[:, 0] < MW + 8) & (p[:, 1] > -8) & (p[:, 1] < MH + 8)
        idx = np.nonzero(ok)[0]
        ntree = len(idx)
        if ntree:
            yy, xx = np.nonzero(R > 1)
            _, nn = cKDTree(p[idx]).query(np.c_[xx + 0.5, yy + 0.5])
            G[yy, xx] = ((idx[nn].astype(np.uint64) * np.uint64(2654435761)) >> np.uint64(11)) % np.uint64(255) + np.uint64(1)
    Image.fromarray(np.dstack([R, G, np.zeros_like(R)]), 'RGB').save(W_ / 'crown.png', optimize=True)
    st = {'depth': {'D0_m': D0, 'step_m': DSTEP, 'cells_below_D0': lo, 'cells_above_16bit': hi, 'min_m': round(dmin, 2), 'max_m': round(dmax, 2),
                    'v_min': int(depth_v.min()), 'v_max': int(depth_v.max())},
          'classes': {int(k): int(n) for k, n in zip(*np.unique(cls, return_counts=True))},
          'shore_fix_px': {'low_ground_to_water': fix_w, 'river_class_above_water_to_paved': fix_b},
          'crown_cells': int((R > 1).sum()), 'crown_tree_numbers': int(len(np.unique(G[G > 0]))), 'scene_trees_in_canvas': ntree}
    (W_ / 'maps_stats.json').write_text(json.dumps(st, indent=1))
    ids_out = {}
    for k in want:
        if n_id[k]:
            ids_out[str(k)] = {'kind': meta['ids'][str(k)], 'px': int(n_id[k]), 'centroid': [round(sx[k] / n_id[k], 1), round(sy[k] / n_id[k], 1)], 'top': top[k], 'bbox': box[k]}
    (W_ / 'id_stats.json').write_text(json.dumps(ids_out, ensure_ascii=False, indent=1))
    col = np.array([(188, 196, 206), (205, 198, 182), (86, 90, 98), (126, 176, 92), (78, 138, 182), (214, 198, 160), (176, 176, 170), (222, 212, 196),
                    (52, 84, 104), (150, 62, 48), (62, 122, 58), (196, 184, 160)], np.uint8)
    Image.fromarray(col[cls]).save(W_ / 'classes_vis.png')
    log('maps', st)


# ───────────────────────── map.json ─────────────────────────
# 랜드마크: (id, 이름, 종류, meta kind 들). 앵커 px 는 ID 패스에서 그 건물의 보이는 픽셀(12.5 cm 캔버스)로 잡는다.
LM_OBJ = [('assembly', '국회의사당', 'landmark', ['landmark:assembly']), ('assembly_members', '국회의원회관', 'landmark', ['landmark:국회의원회관']),
          ('assembly_library', '국회도서관', 'landmark', ['landmark:국회도서관']), ('63', '63빌딩', 'tower', ['landmark:63']),
          ('parc1', '파크원 타워1', 'tower', ['landmark:parc1']), ('parc2', '파크원 타워2(NH금융타워)', 'tower', ['landmark:parc2']),
          ('ifc', 'IFC 서울', 'tower', ['landmark:ifc1', 'landmark:ifc2', 'landmark:ifc3']), ('conrad', '콘래드 서울', 'tower', ['landmark:conrad']),
          ('hyundai', '더현대 서울', 'landmark', ['landmark:hyundai']), ('lg', 'LG트윈타워', 'tower', ['landmark:lg']), ('fki', 'FKI타워(전경련회관)', 'tower', ['landmark:fki']),
          ('church', '여의도순복음교회', 'landmark', ['landmark:church']), ('krx', '한국거래소', 'landmark', ['landmark:KRX한국거래소서울사무소']),
          ('kbs', 'KBS 본관', 'landmark', ['landmark:kbs'])]
# 한강 교량: 장면 도로 번호(id − 20000)로 고른다. 근거는 NOTES 4차(도로 이름·끝점).
LM_BRIDGE = [('mapo_bridge', '마포대교', [23192, 23193]), ('wonhyo_bridge', '원효대교', [22148, 20281]), ('seogang_bridge', '서강대교', [21535, 23881, 25034, 25035]),
             ('saetgang_bridge', '샛강다리', [22862])]
# 넓은 곳: 장면 areas 의 이름으로 찾아 가운데(대표점)를 z=0 으로 투영
LM_AREA = [('yeouido_park', '여의도공원', [('grass', '여의도공원'), ('wood', '여의도공원 자연생태의숲'), ('wood', '여의도공원 한국전통의숲'), ('plaza', '여의도공원 문화의마당')]),
           ('hangang_park', '여의도한강공원', [('grass', '여의도한강공원')]), ('saetgang_park', '여의도샛강생태공원', [('grass', '여의도샛강생태공원')]),
           ('bamseom', '밤섬', [('grass', '밤섬')]), ('park_plaza', '여의도공원 문화의마당', [('plaza', '여의도공원 문화의마당')])]
# 한강공원 물빛광장: 장면에 이름이 없다 → 2차 대표 창 wmulbit(6.25 cm 21174,19238, 1408×1024)의 가운데
#   [5차] 값은 판 C 의 12.5 cm 캔버스 px 다. 다른 판에서는 판 C 카메라로 지면 점을 되살려 다시 투영한다(step_mapjson).
LM_PX = [('mulbit', '한강공원 물빛광장', 'place', [(21174 + 704) / 2, (19238 + 512) / 2])]


def step_mapjson(a):
    W_ = Path(a.work)
    meta = load_meta(a)
    cam = Cam(meta)
    S = json.load(open(a.scene))
    ist = json.loads((W_ / 'id_stats.json').read_text())
    kind_ids = {}
    for k, v in ist.items():
        kind_ids.setdefault(v['kind'], []).append(k)
    inc = lambda p: bool(0 <= p[0] < W and 0 <= p[1] < H)
    rnd = lambda p: [round(float(p[0]), 1), round(float(p[1]), 1)]
    lms = []

    def from_ids(idl):
        idl = [str(i) for i in idl if str(i) in ist]
        if not idl:
            return None
        n = sum(ist[i]['px'] for i in idl)
        c = [sum(ist[i]['centroid'][j] * ist[i]['px'] for i in idl) / n for j in (0, 1)]
        tp = min((ist[i]['top'] for i in idl), key=lambda t: t[1])
        bb = [min(ist[i]['bbox'][0] for i in idl), min(ist[i]['bbox'][1] for i in idl), max(ist[i]['bbox'][2] for i in idl), max(ist[i]['bbox'][3] for i in idl)]
        return {'px': rnd(c), 'top_px': rnd(tp), 'bbox_px': bb, 'visible_px': n}

    for lid, name, kind, kinds in LM_OBJ:
        r = from_ids([i for k in kinds for i in kind_ids.get(k, [])])
        e = {'id': lid, 'name': name, 'kind': kind, 'in_canvas': r is not None}
        key = kinds[0].split(':', 1)[1]
        sl = S['landmarks'].get(key)
        if sl:
            ring = np.array(sl['rings'][0][0][0] if isinstance(sl['rings'][0][0][0][0], list) else sl['rings'][0][0], np.float64)
            c = ring.mean(0)
            e['local_m'] = [round(float(c[0]), 1), round(float(c[1]), 1), 0.0]
            e['h_m'] = sl.get('h')
            e['base_px'] = rnd(cam.proj([c])[0])
        if r:
            e.update(r)
            if 'local_m' not in e:
                e['local_m'] = [round(t, 1) for t in cam.unproj(r['px'][0], r['bbox_px'][3], 0.0)]   # 보이는 픽셀의 아래 끝을 지면으로 본 근사
        else:
            e['note'] = f'판 {cam.board} 조건 렌더에 이 건물이 없다(ID 패스에 없음)'
        lms.append(e)
    for lid, name, idl in LM_BRIDGE:
        r = from_ids(idl)
        e = {'id': lid, 'name': name, 'kind': 'bridge', 'in_canvas': r is not None, 'ids': idl}
        if r:
            e.update(r)
        pts = np.array([p[:2] for i in idl for p in S['roads'][i - 20000]['pts']], np.float64)
        e['local_m'] = [round(float(pts[:, 0].mean()), 1), round(float(pts[:, 1].mean()), 1), 0.0]
        lms.append(e)
    from shapely.geometry import Polygon
    appcls = np.asarray(Image.open(W_ / 'classes.png'))
    wl_, _n = nd.label(appcls == 4)
    han = wl_ == np.bincount(wl_.ravel())[1:].argmax() + 1
    near_han = nd.distance_transform_edt(~han) < 200
    from shapely.ops import unary_union
    for lid, name, srcs in LM_AREA:
        polys = [Polygon(ar['rings'][0]).buffer(0) for cat, nm in srcs for ar in S['areas'].get(cat, []) if ar.get('name') == nm and len(ar['rings'][0]) >= 3]
        if not polys:
            lms.append({'id': lid, 'name': name, 'kind': 'area', 'in_canvas': False, 'note': '장면 areas 에 이름이 없다'})
            continue
        u = unary_union(polys)
        big = max(u.geoms, key=lambda g: g.area) if u.geom_type == 'MultiPolygon' else u
        # 판에 걸친 넓은 곳은 캔버스 안에 보이는 부분의 대표점을 쓴다
        cv = Polygon([cam.unproj(x, y)[:2] for x, y in ((0, 0), (W, 0), (W, H), (0, H))])
        vis = big.intersection(cv)
        tgt = vis if not vis.is_empty else big
        tgt = max(tgt.geoms, key=lambda g: g.area) if tgt.geom_type in ('MultiPolygon', 'GeometryCollection') else tgt
        c = tgt.representative_point()
        p = cam.proj([[c.x, c.y, 0.0]])[0]
        # 대표점이 건물·도로 위에 떨어질 수 있다(한강공원 다각형은 섬을 두른 띠) → 다각형 안의 녹지 칸(앱 클래스 3) 중 가장 큰 덩어리의 가운데로 옮긴다
        mk = Image.new('L', (MW, MH), 0)
        for g_ in (u.geoms if u.geom_type == 'MultiPolygon' else [u]):
            ImageDraw.Draw(mk).polygon([tuple(q / F) for q in cam.proj(np.array(g_.exterior.coords))], fill=1)
        gm = np.asarray(mk).astype(bool) & (appcls == 3)
        if lid == 'hangang_park':
            gm &= near_han      # 한강공원 다각형은 샛강 쪽까지 두른다 → 한강 본류에서 200 m 안의 녹지만
        lab_, n_ = nd.label(gm)
        if n_:
            sz_ = np.bincount(lab_.ravel()); sz_[0] = 0
            yy, xx = np.nonzero(lab_ == sz_.argmax())
            i_ = np.argmin((yy - yy.mean()) ** 2 + (xx - xx.mean()) ** 2)
            p = np.array([xx[i_] * F + F / 2, yy[i_] * F + F / 2], np.float64)
            w_ = cam.unproj(p[0], p[1], 0.0)
            c = type('P', (), {'x': w_[0], 'y': w_[1]})
        lms.append({'id': lid, 'name': name, 'kind': 'area', 'in_canvas': inc(p), 'px': rnd(p), 'local_m': [round(c.x, 1), round(c.y, 1), 0.0], 'area_m2': round(u.area),
                    'visible_fraction': round(vis.area / big.area, 2)})
    import cam as ydcam
    cC = ydcam.Cam('C')
    for lid, name, kind, p in LM_PX:
        p = cam.proj([cC.unproj(p[0] * 2, p[1] * 2, 0.0)])[0]
        lms.append({'id': lid, 'name': name, 'kind': kind, 'in_canvas': inc(p), 'px': rnd(p), 'local_m': [round(t, 1) for t in cam.unproj(p[0], p[1], 0.0)],
                    'note': '2차 대표 창 wmulbit 의 가운데(장면에 이름이 없어 창 위치로 잡음)'})
    for st_ in S['transit']['stations']:
        p = cam.proj([[st_['xy'][0], st_['xy'][1], 0.0]])[0]
        if inc(p):
            lms.append({'id': 'station_' + st_['name'], 'name': st_['name'] + ('' if '선착장' in st_['name'] else '역'), 'kind': 'station', 'in_canvas': True, 'px': rnd(p), 'local_m': [st_['xy'][0], st_['xy'][1], 0.0]})
    # 이동 경로: 지역 좌표(m) pts 는 그대로 두고(앱 mapscene.js 가 pts 를 쓴다), 12.5 cm 캔버스 px(z 포함 투영)를 px 로 더한다
    mv = json.load(open(a.movers or HERE / 'movers' / f'{cam.board}_movers.json'))

    def path(ln, keep=()):
        pts = np.array([(list(p) + [0.0])[:3] for p in ln['pts']], np.float64)
        px = cam.proj(pts)
        frac = float(((px[:, 0] >= 0) & (px[:, 0] < W) & (px[:, 1] >= 0) & (px[:, 1] < H)).mean())
        o = {k: ln[k] for k in keep if k in ln}
        o['pts'] = [[round(float(v_), 2) for v_ in p] for p in pts]
        o['px'] = [[round(float(x), 1), round(float(y), 1)] for x, y in px]
        o['in_canvas'] = round(frac, 2)
        return o

    paths, cnt = {}, {}
    for key, src, keep in (('lanes', 'bus_lanes', ('name', 'highway', 'dir', 'length')), ('rail_lanes', 'rail_lanes', ('line', 'kind', 'hidden', 'bridge', 'length')),
                           ('boat_routes', 'boat_routes', ('name', 'kind', 'loop', 'length'))):
        al = [path(ln, keep) for ln in mv.get(src, [])]
        paths[key] = [o for o in al if o['in_canvas'] > 0]          # 캔버스에 한 점도 안 걸치는 경로는 뺀다
        cnt[key] = [len(al), len(paths[key])]
    # 보행로: 장면 도로의 보행 등급(footway·path·pedestrian; 계단·교량·터널 제외), 모든 점이 캔버스 안, 길이 25 m 이상. z = 0.02
    wl = []
    for r in S['roads']:
        if r.get('cls') != 'foot' or r.get('hw') == 'steps' or r.get('bridge') or r.get('tunnel') or r.get('area') or len(r['pts']) < 2:
            continue
        o = path({'pts': [[p[0], p[1], 0.02] for p in r['pts']], 'name': r.get('name', '')}, ('name',))
        L_ = float(np.hypot(*np.diff(np.array(o['pts'])[:, :2], axis=0).T).sum())
        if o['in_canvas'] == 1.0 and L_ >= 25:
            o['length'] = round(L_, 1)
            wl.append(o)
    paths['walk_paths'] = wl
    cnt['walk_paths'] = [sum(1 for r in S['roads'] if r.get('cls') == 'foot'), len(wl)]
    inp = json.loads((W_ / 'cache' / 'inputs.json').read_text())
    ms = json.loads((W_ / 'maps_stats.json').read_text())
    # 랜드마크: 앱(mapscene.js)은 landmarks {key: {name, px:[지도 px]}} 를 읽는다. px = 지도 px(1 m 칸), canvas_px = 12.5 cm 캔버스 px.
    #   건물의 px 는 보이는 픽셀의 무게중심, top_px 는 꼭대기, ground_px 는 풋프린트 중심의 지면 점.
    ALIAS = {'yeouido_park': 'park', 'hangang_park': 'hangang', 'mapo_bridge': 'mapo', 'wonhyo_bridge': 'wonhyo', 'seogang_bridge': 'seogang'}   # 임시 세트·maps.js 의 key
    lmd = {}
    for l in lms:
        e = {'name': l['name'], 'kind': l['kind'], 'in_canvas': l['in_canvas']}
        if l.get('px'):
            e['px'] = [round(l['px'][0] / F, 1), round(l['px'][1] / F, 1)]
            e['canvas_px'] = l['px']
        if l.get('top_px'):
            e['top_px'] = [round(l['top_px'][0] / F, 1), round(l['top_px'][1] / F, 1)]
        if l.get('base_px'):
            e['ground_px'] = [round(l['base_px'][0] / F, 1), round(l['base_px'][1] / F, 1)]
        if l.get('bbox_px'):
            e['bbox_px'] = [round(t / F, 1) for t in l['bbox_px']]
        for k in ('h_m', 'local_m', 'area_m2', 'visible_fraction', 'visible_px', 'ids', 'note'):
            if l.get(k) is not None:
                e[k] = l[k]
        if e.get('h_m') is not None:
            e['h'] = e['h_m']
        if not e['in_canvas']:
            e.pop('px', None)          # 앱은 px 가 있으면 바로가기를 그 좌표로 덮는다 → 캔버스 밖이면 주지 않는다
        lmd[ALIAS.get(l['id'], l['id'])] = e
    cj = cam.app_json()
    cj.update(theta=cam.theta, elev=35.0, SX0=cam.SX0, SY1=cam.SY1, cam_ref=cam.cl.tolist())      # 임시 규격의 키(mapscene.js 가 읽는다)
    mj = {'schema': 'yeouido-map-1', 'id': 'yeouido', 'name': '여의도', 'name_en': 'Yeouido', 'board': {'C': 'C (국회의사당~63빌딩, θ=135)', 'F': 'F (θ=180: 북쪽에서 남쪽을 봄. 한강이 앞·왼쪽, 국회의사당 오른쪽 아래, 63빌딩 왼쪽 위)'}.get(cam.board, cam.board),
          'placeholder': bool(inp.get('placeholder')), 'raw': inp.get('raw'), 'built': time.strftime('%Y-%m-%d %H:%M:%S'),
          'canvas': [W, H], 'm_per_px': PX, 'map_px': [MW, MH], 'map_m_per_px': PX * F,
          'note': '임시 규격(_yd_interim)의 키를 그대로 둔 윗집합. canvas = 12.5 cm 그림 px, map_px = depth_rg8·classes·crown 의 칸(1 m; 경복궁은 0.5 m). '
                  '경로의 pts = 장면 지역 좌표 m [x, y, z], px = 12.5 cm 캔버스 px [X, Y](지도 px 는 ÷8).',
          'tiles': {'dir': 'tiles', 'm_per_px': {'1': PX * 8, '2': PX * 4, '4': PX * 2, '8': PX}, 'note': 'z = 지도 칸 하나당 그림 px. z8 이 원본(12.5 cm). 아래 단계는 양자화한 z8 의 BOX 축소'},
          'files': {'bg': 'bg.png (z2, 5504×3392)', 'bg_1x': 'bg_1x.png (z1, 2752×1696)', 'depth': 'depth_rg8.png', 'classes': 'classes.png', 'crown': 'crown.png'},
          'depth': {'D0': D0, 'step': DSTEP, 'D0_m': D0, 'step_m': DSTEP, 'formula': 'depth_m = D0 + (R*256+G)*step, 65535 = 없음(이 지도에는 없음). 칸(1 m) 안 최솟값',
                    'v_range': [ms['depth']['v_min'], ms['depth']['v_max']],
                    'ground_note': '지면은 평면으로 펴지 않았다: 0 m 지면, 한강 수면 −1.8 m, 호안 경사. 칸 최솟값이라 평지 칸도 z=0 평면 깊이보다 최대 0.57 m 가깝다'},
          'camera': cj, 'sun': {'euler_deg': [50, 0, cam.theta - 73], 'shadow_tint': [0.6, 0.64, 0.74]}, 'local_origin_epsg5186': S['org'],
          'classes': {'app': APP_NAMES, 'from_ground_classes_05m': {str(k): {'name': KCLS_NAMES[k], 'app': KCLS_TO_APP[k]} for k in KCLS_NAMES},
                      'objects': [{'what': w, 'app': r} for w, r in OBJ_RULES], 'cells': ms['classes']},
          'water_level_m': WL, 'landmarks': lmd, **paths, 'mover_specs': mv.get('specs'), 'movers_about': mv.get('about')}
    (W_ / 'map.json').write_text(json.dumps(mj, ensure_ascii=False, separators=(',', ':')))
    log('map.json', (W_ / 'map.json').stat().st_size, 'B; landmarks', len(lms), 'in canvas', sum(1 for l in lms if l['in_canvas']), '경로 [전체, 넣은 것]', cnt)
    for l in lms:
        print('  ', ALIAS.get(l['id'], l['id']), l['name'], lmd[ALIAS.get(l['id'], l['id'])].get('px'), 'in' if l['in_canvas'] else 'OUT')


# ───────────────────────── keys(셰이더 색 키 점검, 참고) ─────────────────────────
def step_keys(a):
    W_ = Path(a.work)
    im = np.asarray(Image.open(W_ / 'p0125.png').convert('RGB')).astype(np.float32) / 255
    cl = np.asarray(Image.open(W_ / 'classes.png'))
    f = im.shape[0] // cl.shape[0]
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    lum = im @ np.array([.3, .59, .11], np.float32)
    green = g - np.maximum(r, b) > 0.07
    blue = (b > r * 1.25) & (b > g)
    glass = (r * 1.12 <= b) & (lum >= 0.10) & (lum < 0.62)
    out = {}
    for k, nm in ((3, 'green'), (10, 'tree'), (4, 'water'), (6, 'roof'), (7, 'wall'), (1, 'ground'), (2, 'road'), (11, 'walk')):
        m = np.repeat(np.repeat(cl == k, f, 0), f, 1)
        if m.sum() == 0:
            continue
        out[nm] = {'px': int(m.sum()), 'isGreen': round(float(green[m].mean()), 3), 'lawnG(l>=.56)': round(float((green & (lum >= 0.56))[m].mean()), 3),
                   'isBlue': round(float(blue[m].mean()), 3), 'isGlass': round(float(glass[m].mean()), 3), 'lum_med': round(float(np.median(lum[m])), 3)}
        print(nm, out[nm])
    (W_ / 'keys.json').write_text(json.dumps(out, indent=1))


# ───────────────────────── tiles ─────────────────────────
def step_tiles(a):
    W_ = Path(a.work)
    r = subprocess.run([sys.executable, a.make_tiles, '--z1', str(W_ / 'p05.png'), '--z2', str(W_ / 'p025.png'), '--z4', str(W_ / 'p0125.png'), '--z8', str(W_ / 'p0625.png'),
                        '--out', str(W_ / 'tiles'), '--jobs', str(a.jobs)])
    if r.returncode:
        sys.exit(f'make_tiles 실패({r.returncode})')
    mf = W_ / 'tiles' / 'manifest.json'
    m = json.loads(mf.read_text())
    m['note'] = 'make_tiles.py 가 만든다. 여의도: 지도 칸 1 m 당 그림 px = z (z1 1 m, z2 0.5 m, z4 0.25 m, z8 0.125 m). 단색 타일은 파일 없이 solid 에 [x, y, 색 번호].'
    m['map_m_per_px'] = PX * F
    mf.write_text(json.dumps(m, ensure_ascii=False, separators=(',', ':')) + '\n')
    shutil.copy(W_ / 'p025.png', W_ / 'bg.png')
    shutil.copy(W_ / 'p05.png', W_ / 'bg_1x.png')
    log('tiles + bg.png + bg_1x.png')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('step', choices=['all', 'cache', 'lock', 'quant', 'maps', 'tiles', 'mapjson', 'keys', 'rooftest', 'gtest', 'ghost', 't11'])
    ap.add_argument('--src', default='raw', choices=['raw', 'locked'], help='ghost: 검출할 그림')
    ap.add_argument('--before', help='t11: 전 그림을 읽을 작업 폴더(그 cache/locked.npy)')
    ap.add_argument('--zp', help='t11: 교량 덩어리 매개변수 덮어쓰기(JSON)')
    ap.add_argument('--raw')
    ap.add_argument('--pass', dest='pass_dir', default=str(HERE / 'half'))
    ap.add_argument('--work', required=True)
    ap.add_argument('--scene', default=str(HERE / 'scene.json'))
    ap.add_argument('--movers', default=None, help='기본: movers/<판>_movers.json (판은 pass meta.json 의 board)')
    ap.add_argument('--placeholder', action='store_true', help='raw 가 양식 전 cond 임을 map.json 에 적는다')
    ap.add_argument('--crop')
    ap.add_argument('--inject', action='store_true', help='lock --crop 시험: 강물 위에 배·섬·다리 흉내를 그려 넣고 잠근다')
    ap.add_argument('--local-lut', action='store_true', help='lock --crop 시험: 대응표를 그 구역에서만 만든다')
    ap.add_argument('--thr', type=float, default=0)
    ap.add_argument('--zthr', type=float, default=0, help='교량·호안/선착장 잠금 임계값(기본 42)')
    ap.add_argument('--no-zones', action='store_true', help='교량·호안/선착장 잠금을 끈다(강물 잠금만)')
    ap.add_argument('--no-roof', action='store_true', help='지붕 잠금·랜드마크 벽 잠금을 끈다(8차)')
    ap.add_argument('--no-bridge-whole', action='store_true', help='(11차부터 기본값; 남겨 둔 스위치)')
    ap.add_argument('--bridge-whole', action='store_true', help='강 교량 전체를 기대색으로 되돌린다(10차 방식). 11차 기본은 덩어리 + 벽돌 씨앗')
    ap.add_argument('--mat-lm', default='auto', choices=['auto', 'on', 'off'], help='[12차] 재질 랜드마크 벽 전체 cond(auto = pass 가 halfF3 이후)')
    ap.add_argument('--mcolors', type=int, default=0, help='[12차] 재질 랜드마크 벽 포스터라이즈 색 수(기본 = wcolors 12)')
    ap.add_argument('--no-span', action='store_true', help='[12차] 교량 경간 단위 되돌림을 끈다')
    ap.add_argument('--apt-frac', type=float, default=0, help='[12차] 아파트 면 교체 벽돌 몫 문턱(기본 FACE rec_frac)')
    ap.add_argument('--no-ground', action='store_true', help='지면·나무 잠금(밤섬 포함)을 끈다(10차)')
    ap.add_argument('--no-flat-water', action='store_true', help='강물 단색 채움을 끈다(10차; 끄면 5차 강물 잠금 결과가 남는다)')
    ap.add_argument('--origin', help='rooftest: --raw 조각의 캔버스 원점 x,y')
    ap.add_argument('--out', help='rooftest: 그림을 쓸 폴더')
    ap.add_argument('--name', default='t', help='rooftest: 파일 이름 머리')
    ap.add_argument('--sheet-scale', type=int, default=2)
    ap.add_argument('--colors', type=int, default=128)
    ap.add_argument('--make-tiles', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'gyeongbokgung', 'make_tiles.py'))
    ap.add_argument('--jobs', type=int, default=16)
    a = ap.parse_args()
    assert a.jobs <= 16, '프로세스는 16 이하'
    if a.no_span:
        SPAN['on'] = False
    if a.apt_frac:
        FACE['rec_frac'] = a.apt_frac
    steps = ['cache', 'lock', 'quant', 'maps', 'tiles', 'mapjson', 'keys'] if a.step == 'all' else [a.step]
    for s in steps:
        t = time.time()
        globals()['step_' + s](a)
        log(f'step {s} done in {time.time() - t:.0f}s')


if __name__ == '__main__':
    main()
