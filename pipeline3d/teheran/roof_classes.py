#!/usr/bin/env python3
"""건물별 지붕 종류표 osm/roof_classes.json 을 만든다(prep_extra.py 가 있으면 읽는다. 없으면 지붕은 고정 난수로 정해진다).
입력은 위에서 내려다본 정사 그림 여러 장과 그 가운데 좌표다. 공개판은 네이버 지도 위성 화면(글자 없는 층, 확대 17)을 판 전체에 56장 찍어 넣었다. 그림은 저장소에 없고, 이 표도 저장소에 넣지 않는다.
그림에서 읽는 것은 건물 윤곽 안쪽 화소의 색 중앙값 하나뿐이고, 그것을 일곱 종류(초록 방수 바닥, 회색, 밝은 색, 짙은 색, 붉은 기와, 파란 지붕, 황토색) 가운데 하나로 적는다. 색 자체는 옮기지 않는다.
20 m 가 넘는 건물은 항공 사진에서 지붕이 옆으로 밀려 찍히므로 건너뛴다. 나무·그림자에 덮여 어두운 초록·검정으로 읽힌 곳도 건너뛴다.

  python roof_classes.py <그림 폴더> [m/px=0.4738]      (작업 폴더에서. 그림 폴더의 idx.json = {"이름": [가운데 x, y(장면 m)]}, 그림은 g<이름>.png)
"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as nd

D = Path(sys.argv[1]); K = float(sys.argv[2]) if len(sys.argv) > 2 else 0.4738
S = json.load(open('scene.json')); idx = json.load(open(D / 'idx.json'))
B = [(b['osm'], np.array(b['rings'][0], float), b['h']) for b in S['buildings'] if b['h'] <= 20 and b['area'] >= 45]
cen = np.array([p.mean(0) for _, p, _ in B])


def classify(rgb):
    r, g, b = (float(v) for v in rgb); lum = .299 * r + .587 * g + .114 * b; mx, mn = max(r, g, b), min(r, g, b); sat = (mx - mn) / max(mx, 1)
    if lum < 52: return None                                        # 그림자·나무
    if g > r + 10 and g >= b - 4 and sat > .16: return 'green' if lum > 78 else None   # 어두운 초록은 나무
    if r > g + 11 and r > b + 17: return 'tile'                     # 붉은·고동색 기와, 붉은 방수 바닥
    if b > r + 18 and b > g + 6: return 'blue'
    if sat < .13: return 'light' if lum > 172 else 'grey' if lum > 104 else 'dark'
    if r > b + 14 and g > b + 6: return 'tan'
    return 'grey' if lum > 104 else 'dark'


out = {}
for name, c0 in idx.items():
    f = D / f'g{name}.png'
    if not f.exists(): continue
    a = np.asarray(Image.open(f).convert('RGB')).astype(np.float32); H, W = a.shape[:2]; C = np.array([W / 2 + 32.0, H / 2])   # 화면에서 좌표가 놓이는 자리(1529 × 1190 창에서 잰 값: 두 확대 단계의 고정점, 건물 윤곽을 겹쳐 확인)
    sel = np.nonzero((np.abs(cen[:, 0] - c0[0]) < W * K / 2 - 14) & (np.abs(cen[:, 1] - c0[1]) < H * K / 2 - 14))[0]
    if not len(sel): continue
    lab = Image.new('I', (W, H), 0); d = ImageDraw.Draw(lab)
    for n, i in enumerate(sel): d.polygon([(C[0] + (x - c0[0]) / K, C[1] - (y - c0[1]) / K) for x, y in B[i][1]], fill=n + 1)
    lab = np.asarray(lab); lab = np.where(nd.binary_erosion(lab > 0, iterations=2), lab, 0)   # 윤곽에서 약 1 m 안쪽만
    l2 = lab; ui = (l2 > 0) & (np.arange(W)[None, :] > 70) & (np.arange(H)[:, None] > 60)   # 화면 위·왼쪽의 단추 띠는 뺀다
    ids = l2[ui]; px = a[ui]; order = np.argsort(ids, kind='stable'); ids, px = ids[order], px[order]; cut = np.searchsorted(ids, np.arange(1, len(sel) + 2))
    for n, i in enumerate(sel):
        q = px[cut[n]:cut[n + 1]]
        if len(q) < 25: continue
        k = classify(np.median(q, 0))
        if k and B[i][0] not in out: out[B[i][0]] = k
json.dump(out, open('osm/roof_classes.json', 'w'), separators=(',', ':'))
cnt = {}
for v in out.values(): cnt[v] = cnt.get(v, 0) + 1
print('buildings', len(B), 'classified', len(out), cnt)
