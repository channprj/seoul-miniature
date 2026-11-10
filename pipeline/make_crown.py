#!/usr/bin/env python3
"""수관 마스크 assets/redraw/crown.png 을 굽는다(앱이 선택으로 읽는다: app/src/assets.js, render.js 의 uCrown).

  python3 pipeline/make_crown.py [crown.png] [crown_region.png] [out.png]

입력(기본 work/hd/full/v4/, 지금 타일과 맞는 판은 *_v4c): 지도 px(0.5 m) 칸마다
  crown_v4c.png         다시 그린 그림에서 새 나무가 그려진 픽셀의 비율(0~255). 나무 밑 그림자·줄기까지 들어 있다.
  crown_region_v4c.png  수관을 다시 그린 영역(0 이 아니면 안)
  assets/redraw/tiles/z8_*.png  실제 그림. 위 마스크 안에서 수관만 다시 가려낸다:
     그림자·잔디는 평평한 색, 수관은 얼룩과 외곽선이 있으므로 17 px 창의 밝기 경계 밀도로 가르고,
     가는 선(그림자 가장자리)은 열림 연산으로 지우고 구멍은 메운다. 붉은 갈색 줄기는 뺀다.
출력(2752×1696, 8 비트 RGB, 비인터레이스):
  R  0 = 영역 밖(렌더러가 클래스 맵대로 판정), 1 = 영역 안·나무 없음, 2~255 = 칸 안 수관 픽셀 비율
  G  나무 한 그루 단위 색 번호 1~255(0 = 없음). 계절 색(단풍·벚꽃)을 그루 단위로 고르는 데 쓴다.
     붙어 있는 나무 무리는 거리 변환의 봉우리로 나눈다(봉우리 하나 = 한 그루). 번호는 봉우리 자리로 정한 고정 난수.
  B  0
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as nd

REPO = Path(__file__).resolve().parents[1]
V = REPO / 'work/hd/full/v4'
a = sys.argv[1:]
crown = np.asarray(Image.open(a[0] if len(a) > 0 else V / 'crown_v4c.png').convert('L'))
region = np.asarray(Image.open(a[1] if len(a) > 1 else V / 'crown_region_v4c.png').convert('L')) > 0
out = Path(a[2]) if len(a) > 2 else REPO / 'assets/redraw/crown.png'
assert crown.shape == (1696, 2752) and region.shape == crown.shape, (crown.shape, region.shape)

TILES = REPO / 'assets/redraw/tiles'
Z, B, MG = 8, 256, 24          # 그림 배율, 블록 크기·여백(지도 px)
LUMA = np.array([.299, .587, .114], np.float32)


def disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r + 1


def picture(x0, y0, w, h):
    im = Image.new('RGB', (w * Z, h * Z))
    for ty in range(y0 * Z // 256, ((y0 + h) * Z - 1) // 256 + 1):
        for tx in range(x0 * Z // 256, ((x0 + w) * Z - 1) // 256 + 1):
            f = TILES / f'z{Z}_{tx}_{ty}.png'
            if f.exists():
                im.paste(Image.open(f).convert('RGB'), (tx * 256 - x0 * Z, ty * 256 - y0 * Z))
    return np.asarray(im).astype(np.float32)


def crown_pixels(x0, y0, w, h):
    """그림 px 단위 수관 여부(bool, h*Z × w*Z)"""
    a = picture(x0, y0, w, h)
    m = np.kron(crown[y0:y0 + h, x0:x0 + w] > 0, np.ones((Z, Z), bool))
    lum = a @ LUMA
    e = np.zeros(lum.shape, np.float32)
    e[:, :-1] += np.abs(lum[:, :-1] - lum[:, 1:]) > 12
    e[:-1] += np.abs(lum[:-1] - lum[1:]) > 12
    c = m & (nd.uniform_filter(e, 17) > 0.12)
    c = nd.binary_opening(c, disk(5))
    c = nd.binary_closing(c, disk(3))
    hole = nd.binary_fill_holes(c) & ~c
    lab, n = nd.label(hole)
    if n:
        c |= (nd.sum(hole, lab, range(n + 1)) < 2500)[lab] & hole   # 작은 구멍만 메운다(큰 구멍은 수관 사이에 갇힌 그림자)
    lab, n = nd.label(c)
    if n:
        c &= (nd.sum(c, lab, range(n + 1)) >= 900)[lab]      # 길가 경계에 맺힌 작은 방울 제거
    c = nd.binary_erosion(c, disk(4))                        # 창 너비만큼 바깥으로 번진 테두리를 되돌린다
    trunk = (a[..., 0] > a[..., 1] + 10) & (lum < 110)
    # 수관 사이 좁은 틈의 그림자: 경계가 하나도 없는 평평하고 짙은 면(20×20 px 이상)은 뺀다
    flat = nd.binary_dilation(nd.uniform_filter(e, 7) < 1e-6, np.ones((7, 7))) & (lum < 90) & (lum >= 45)
    lab, n = nd.label(flat)
    if n:
        flat &= (nd.sum(flat, lab, range(n + 1)) >= 400)[lab]
    c &= m & ~trunk & ~flat
    # 그루 봉우리: 검은 외곽선을 뺀 수관 안쪽의 거리 변환에서 반경 30 px(1.9 m) 안 최고점. 겹친 나무도 외곽선으로 갈린다.
    d = nd.gaussian_filter(nd.distance_transform_edt(c & (lum >= 45)), 3.0)
    peak = (d > 8) & (d == nd.maximum_filter(d, size=61))
    lab, n = nd.label(peak, structure=np.ones((3, 3)))
    pk = np.array(nd.center_of_mass(peak, lab, range(1, n + 1))).reshape(-1, 2) / Z
    return c, pk


H, W = crown.shape
frac = np.zeros(crown.shape, np.float32)
seeds = np.zeros(crown.shape, bool)
# 영역 마스크는 낱알처럼 구멍이 많다 → 3 칸 닫힘으로 메운다(7 칸 넘는 구멍 = 옛 나무를 되살린 자리는 남는다)
region = nd.binary_closing(region, disk(3)) | region
for by in range(0, H, B):
    for bx in range(0, W, B):
        if not crown[by:by + B, bx:bx + B].any():
            continue
        x0, y0 = max(0, bx - MG), max(0, by - MG)
        x1, y1 = min(W, bx + B + MG), min(H, by + B + MG)
        c, pk = crown_pixels(x0, y0, x1 - x0, y1 - y0)
        for py, px in pk + (y0, x0):
            if by <= py < by + B and bx <= px < bx + B:
                seeds[int(py), int(px)] = True
        f = c.reshape(y1 - y0, Z, x1 - x0, Z).mean((1, 3))
        frac[by:min(H, by + B), bx:min(W, bx + B)] = f[by - y0:by - y0 + B, bx - x0:bx - x0 + B][:min(H, by + B) - by, :min(W, bx + B) - bx]

has = region & (frac > 0.04)
R = np.zeros(crown.shape, np.uint8)
R[region] = 1
R[has] = 2 + (frac[has] * 253).round().astype(np.uint8)

# 수관 칸마다 가장 가까운 봉우리(같은 무리 안에서만 뜻이 있지만, 무리 사이는 수관이 아닌 칸으로 떨어져 있다)
_, (iy, ix) = nd.distance_transform_edt(~seeds, return_indices=True)
h = (iy.astype(np.uint32) * 73856093) ^ (ix.astype(np.uint32) * 19349663)
h ^= h >> 13; h *= np.uint32(0x5bd1e995); h ^= h >> 15
G = np.where(has, 1 + (h % 255), 0).astype(np.uint8)

Image.fromarray(np.dstack([R, G, np.zeros_like(R)]), 'RGB').save(out, optimize=True)
print(f'{out}: {out.stat().st_size} bytes, 영역 {int(region.sum())} 칸, 수관 {int(has.sum())} 칸, 나무 {int(seeds.sum())} 그루')
