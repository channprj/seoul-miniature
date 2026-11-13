#!/usr/bin/env python3
"""지면 종류 래스터 osm/ground_kinds.png 를 만든다(prep_extra.py 가 있으면 읽는다. 없으면 OSM 에 없는 땅은 민무늬 바탕 지면이다).
OSM 은 강남의 블록 안쪽을 거의 비워 둔다: 학교 운동장, 언덕 숲, 지상 주차장, 도로변 녹지가 「아무것도 없는 땅」으로 남는다(판의 약 25 %).
위에서 내려다본 정사 그림(공개판은 네이버 지도 위성 화면, 글자 없는 층, 확대 17, 56장 = roof_classes.py 와 같은 그림)에서 2 m 칸마다 색을 읽어 다섯 종류 가운데 하나로 적는다:
  1 나무(짙고 얼룩진 초록), 2 잔디·인조잔디(고른 초록), 3 모래 마당(밝은 황토: 학교 운동장·빈 터), 4 아스팔트(지상 주차장·마당), 5 밝은 포장(광장·보도·옥외 데크), 0 모름.
건물 안, 높은 건물 둘레(항공 사진에서 벽이 옆으로 누워 땅을 가린다), 그늘처럼 어두운 칸은 0 으로 둔다. 종류만 옮기고 색은 옮기지 않는다. 그림도 이 래스터도 저장소에 넣지 않는다.

  python ground_kinds.py <그림 폴더> [m/px=0.4738]      (작업 폴더에서. 그림 폴더의 idx.json = {"이름": [가운데 x, y(장면 m)]}, 그림은 g<이름>.png)
"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as nd

D = Path(sys.argv[1]); K = float(sys.argv[2]) if len(sys.argv) > 2 else 0.4738; G = 2.0
S = json.load(open('scene.json')); idx = json.load(open(D / 'idx.json'))
sys.path.insert(0, str(Path(__file__).resolve().parent)); from cam import Cam
c = Cam('T'); corners = np.array([c.unproj(X, Y, 0)[:2] for X, Y in ((0, 0), (c.W, 0), (c.W, c.H), (0, c.H))]); x0, y0 = corners.min(0) - 40; x1, y1 = corners.max(0) + 40
W, H = int((x1 - x0) / G) + 1, int((y1 - y0) / G) + 1; xs = x0 + (np.arange(W) + .5) * G; ys = y1 - (np.arange(H) + .5) * G
rgb = np.zeros((H, W, 3), np.float32); var = np.zeros((H, W), np.float32); best = np.full((H, W), 1e9, np.float32)
for name, c0 in idx.items():   # 칸마다 가장 가까운 그림에서(화면 가장자리의 단추·글자 띠는 빼고) 칸 평균색과 밝기 얼룩을 읽는다
    f = D / f'g{name}.png'
    if not f.exists(): continue
    a = np.asarray(Image.open(f).convert('RGB')).astype(np.float32); h, w = a.shape[:2]; C = (w / 2 + 32.0, h / 2)
    px = C[0] + (xs - c0[0]) / K; py = C[1] - (ys - c0[1]) / K; okx = (px > 112) & (px < w - 52); oky = (py > 72) & (py < h - 72)
    if not okx.any() or not oky.any(): continue
    ix, iy = np.nonzero(okx)[0], np.nonzero(oky)[0]; n = max(1, int(round(G / K))); sm = nd.uniform_filter(a, (n, n, 1)); g = a.mean(-1); sd = np.sqrt(np.maximum(nd.uniform_filter(g * g, 2 * n + 1) - nd.uniform_filter(g, 2 * n + 1) ** 2, 0))
    PX, PY = np.meshgrid(px[ix].astype(int), py[iy].astype(int)); d = np.hypot(xs[ix][None, :] - c0[0], ys[iy][:, None] - c0[1]).astype(np.float32); sl = np.ix_(iy, ix); take = d < best[sl]
    r_ = rgb[sl]; r_[take] = sm[PY, PX][take]; rgb[sl] = r_; v_ = var[sl]; v_[take] = sd[PY, PX][take]; var[sl] = v_; b_ = best[sl]; b_[take] = d[take]; best[sl] = b_
if '--dump' in sys.argv: np.savez('osm/_gk_dump.npz', rgb=rgb, var=var, best=best, x0=x0, y1=y1)
r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]; lum = .299 * r + .587 * g + .114 * b; gx = g - np.maximum(r, b); rb = r - b
# 문턱은 OSM 으로 종류를 아는 칸(간선 도로, 숲, 구장, 주차장)의 색 분포에 맞췄다. 이 그림은 전체가 초록 쪽으로 치우쳐 있어(도로도 g − max(r, b) 중앙값 9) 초록 판정을 밝기에 견준 비율로 한다.
kind = np.zeros((H, W), np.uint8); green = gx > np.maximum(8.0, .15 * lum)
kind[green & (lum < 88)] = 1; kind[green & (lum >= 88)] = 2
kind[~green & (rb > 22) & (lum > 125)] = 3
grey = ~green & (np.abs(rb) < 19) & (kind == 0); kind[grey & (lum >= 72) & (lum < 126) & (var < 46)] = 4; kind[grey & (lum >= 126)] = 5
kind[(best > 1e8) | ((lum < 58) & ~((gx > .2 * lum) & (lum > 30)))] = 0   # 그늘은 모름. 짙은 숲(어둡지만 초록 몫이 큰 칸)은 나무로 남긴다
# 건물 안과 높은 건물 둘레는 모름
m = Image.new('L', (W, H), 0); dm = ImageDraw.Draw(m); tp = lambda pts: [((x - x0) / G, (y1 - y) / G) for x, y in pts]
tall = Image.new('L', (W, H), 0); dt = ImageDraw.Draw(tall)
for bd in S['buildings']:
    dm.polygon(tp(bd['rings'][0]), fill=1)
    if bd['h'] > 30: dt.polygon(tp(bd['rings'][0]), fill=int(min(255, bd['h'])))
blk = nd.binary_dilation(np.asarray(m) > 0, iterations=1); th = np.asarray(tall).astype(np.float32)
for hh, rad in ((30, 8), (60, 16), (100, 26), (160, 40)): blk |= nd.binary_dilation(th > hh, iterations=int(rad / G))
kind[blk] = 0
# 다수결로 고르게 하고 작은 조각(80 m² 미만)은 버린다. 아스팔트·밝은 포장은 좁은 틈(골목 그늘)까지 칠하지 않게 400 m² 이상만
votes = np.stack([nd.uniform_filter((kind == k).astype(np.float32), 5) for k in range(6)]); maj = votes.argmax(0).astype(np.uint8); maj[kind == 0] = 0; kind = maj
for k, amin in ((1, 80), (2, 80), (3, 200), (4, 400), (5, 400)):
    lab, n = nd.label(kind == k); sz = nd.sum(kind == k, lab, np.arange(1, n + 1)) * G * G; small = np.isin(lab, np.nonzero(sz < amin)[0] + 1); kind[small] = 0
Image.fromarray(kind).save('osm/ground_kinds.png'); json.dump({'x0': float(x0), 'y1': float(y1), 'g': G, 'size': [W, H], 'kinds': {'1': 'tree', '2': 'grass', '3': 'sand', '4': 'asphalt', '5': 'pave'}}, open('osm/ground_kinds.json', 'w'))
tot = kind.size; print('cells', tot, {k: '%.1f%%' % (100 * (kind == i).sum() / tot) for i, k in enumerate(('unknown', 'tree', 'grass', 'sand', 'asphalt', 'pave'))})
