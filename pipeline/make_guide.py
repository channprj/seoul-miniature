#!/usr/bin/env python3
"""공개 가능한 모델로 배경을 다시 그리기 위한 밑그림(블록아웃)을 만든다.

입력은 기존 그림을 쓰지 않는다:
  - pipeline/input/occlusion_depth16.png  (렌더 깊이; 카메라·기하만 담김)
  - pipeline/input/camera_nw45w.json
  - work/osm_raw.json  (pipeline/fetch_osm.py 로 받은 OSM: 건물 윤곽, 도로, 수면, 녹지, 경복궁 경계 — ODbL)
출력(같은 2752×1696 캔버스, 같은 카메라):
  - guide_color.png   의미색 + 간단한 음영의 블록아웃
  - guide_depth.png   ControlNet 용 정규화 깊이(가까울수록 밝음)
  - guide_classes.png 클래스 맵(0 없음,1 지면,2 도로,3 녹지,4 수면,5 궁궐마당,6 건물지붕,7 건물벽,8 궁궐지붕,9 궁궐벽,10 수목,11 보행로)

사용: python3 pipeline/make_guide.py <outdir> [osm_raw.json]
"""
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / 'work'
out.mkdir(parents=True, exist_ok=True)

cam = json.load(open(REPO / 'pipeline/input/camera_nw45w.json'))
W, H = cam['res']
m = cam['m_per_px_screen']
ex, ey, vd = (np.array(cam[k]) for k in ('screen_x_axis', 'screen_y_axis', 'view_dir'))
cl = np.array(cam['cam_location'])
camvd = float(cl @ vd)

d16 = np.array(Image.open(REPO / 'pipeline/input/occlusion_depth16.png')).astype(np.float64)
none = d16 >= 65535
depth = 2060.0 + d16 * 0.02

# ── 월드 격자(0.5 m)에 OSM 클래스를 래스터화. 경위도 → EPSG:5186(TM, GRS80) → 로컬
osm = json.load(open(sys.argv[2] if len(sys.argv) > 2 else REPO / 'work/osm_raw.json'))
ORG = cam.get('local_origin_epsg5186', [197940.46660081236, 552912.2911692131])
def tm5186(lon, lat):
    a, f = 6378137.0, 1 / 298.257222101
    e2 = f * (2 - f); ep2 = e2 / (1 - e2)
    lat0, lon0 = np.radians(38.0), np.radians(127.0)
    def M(p):
        return a * ((1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * p - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * np.sin(2 * p)
                    + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * np.sin(4 * p) - (35 * e2**3 / 3072) * np.sin(6 * p))
    p, l = np.radians(lat), np.radians(lon)
    N_ = a / np.sqrt(1 - e2 * np.sin(p)**2); T = np.tan(p)**2; C = ep2 * np.cos(p)**2; A = (l - lon0) * np.cos(p)
    x = N_ * (A + (1 - T + C) * A**3 / 6 + (5 - 18 * T + T**2 + 72 * C - 58 * ep2) * A**5 / 120) + 200000.0
    y = (M(p) - M(lat0) + N_ * np.tan(p) * (A**2 / 2 + (5 - T + 9 * C + 4 * C**2) * A**4 / 24 + (61 - 58 * T + T**2 + 600 * C - 330 * ep2) * A**6 / 720)) + 600000.0
    return x - ORG[0], y - ORG[1]
X0, Y0, X1, Y1 = -800.0, -500.0, 900.0, 1350.0
G = 0.5
gw, gh = int((X1 - X0) / G), int((Y1 - Y0) / G)
def gp(geom):
    out_ = []
    for q in geom:
        x, y = tm5186(q['lon'], q['lat'])
        out_.append(((x - X0) / G, (y - Y0) / G))
    return out_
layers = {k: Image.new('L', (gw, gh), 0) for k in ('park', 'water', 'road', 'path', 'bld', 'palace', 'wood', 'lane', 'wline')}
blds = []
bmeta = []   # (격자 좌표 윤곽, 태그, 중심 경도, 중심 위도) — 건물별 성격(한옥·빌라·타워 등) 판정용
dr = {k: ImageDraw.Draw(v) for k, v in layers.items()}
ROADW = {'primary': 22, 'primary_link': 9, 'secondary': 16, 'secondary_link': 8, 'tertiary': 11, 'tertiary_link': 7, 'residential': 6,
         'unclassified': 6, 'living_street': 5, 'service': 4, 'busway': 4}
PATHW = {'footway': 2.5, 'pedestrian': 5, 'path': 2, 'steps': 2, 'cycleway': 2, 'track': 3}
def outer_rings(rel):
    # multipolygon 의 outer way 조각을 이어 붙여 닫힌 고리로 만든다
    segs = [m['geometry'] for m in rel['members'] if m['type'] == 'way' and m.get('role') in ('outer', '') and m.get('geometry')]
    rings = []
    while segs:
        ring = list(segs.pop(0))
        changed = True
        while changed and (ring[0] != ring[-1]):
            changed = False
            for i, sg in enumerate(segs):
                if sg[0] == ring[-1]: ring += sg[1:]
                elif sg[-1] == ring[-1]: ring += sg[-2::-1]
                elif sg[-1] == ring[0]: ring = sg[:-1] + ring
                elif sg[0] == ring[0]: ring = sg[:0:-1] + ring
                else: continue
                segs.pop(i); changed = True; break
        rings.append(ring)
    return rings
FORCE_H = {'국립민속박물관': 12, '국립고궁박물관': 13}
for e in osm['elements']:
    t = e.get('tags', {})
    if e['type'] == 'relation':
        key = 'palace' if e['id'] == 5501517 else 'bld' if 'building' in t else 'water' if t.get('natural') == 'water' else 'park'
        for ring in outer_rings(e):
            if len(ring) >= 3:
                dr[key].polygon(gp(ring), fill=255)
                # 관계(멀티폴리곤)로 올라온 건물도 이름·종류 판정에 쓰도록 건물 목록에 넣는다
                # 기존 3D 장면에 빠져 있는 큰 건물은 여기서 직접 세운다(높이는 사진을 보고 정한 어림값)
                if key == 'bld' and t.get('name') in FORCE_H:
                    blds.append(([tm5186(q['lon'], q['lat']) for q in ring], dict(t, height=str(FORCE_H[t['name']]), _force='1')))
                if key == 'bld': bmeta.append((gp(ring), t, sum(q['lon'] for q in ring) / len(ring), sum(q['lat'] for q in ring) / len(ring)))
        continue
    g = e.get('geometry')
    if not g: continue
    if 'building' in t:
        if len(g) >= 3:
            dr['bld'].polygon(gp(g), fill=255)
            blds.append(([tm5186(q['lon'], q['lat']) for q in g], t))
            bmeta.append((gp(g), t, sum(q['lon'] for q in g) / len(g), sum(q['lat'] for q in g) / len(g)))
    elif 'highway' in t:
        hw = t['highway']
        if hw in ROADW and t.get('tunnel') != 'yes':
            lanes = float(t.get('lanes', 0) or 0) if str(t.get('lanes', '')).replace('.', '').isdigit() else 0
            w = max(ROADW[hw], lanes * 3.3 + 1) if lanes else ROADW[hw]
            dr['road'].line(gp(g), fill=255, width=max(2, round(w / G)), joint='curve')
            if w >= 9:
                # 차선 점선(3 m 선, 4 m 간격). 넓은 도로가 강으로 읽히지 않게 하는 단서다.
                pts = gp(g); offs = [0.0] if w < 15 else [-w / 4 / G, w / 4 / G] if w < 24 else [-w / 3 / G, 0.0, w / 3 / G]
                acc = 0.0
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    L = math.hypot(bx - ax, by - ay)
                    if L < 1e-6: continue
                    ux, uy = (bx - ax) / L, (by - ay) / L
                    t0 = 0.0
                    while t0 < L:
                        ph = (acc + t0) % (7 / G)
                        if ph < 3 / G:
                            t1 = min(L, t0 + 3 / G - ph)
                            for o in offs:
                                dr['lane'].line([(ax + ux * t0 - uy * o, ay + uy * t0 + ux * o), (ax + ux * t1 - uy * o, ay + uy * t1 + ux * o)], fill=255, width=1)
                            t0 = t1 + 1e-3
                        else:
                            t0 += 7 / G - ph
                    acc += L
        elif hw in PATHW:
            if t.get('area') == 'yes' and len(g) >= 3: dr['path'].polygon(gp(g), fill=255)
            else: dr['path'].line(gp(g), fill=255, width=max(2, round(PATHW[hw] / G)), joint='curve')
    elif t.get('natural') == 'water' or t.get('water'):
        if len(g) >= 3: dr['water'].polygon(gp(g), fill=255)
    elif 'waterway' in t:
        if not t.get('tunnel') and t.get('layer') != '-1' and t['waterway'] not in ('drain', 'ditch'): dr['wline'].line(gp(g), fill=255, width=round(4 / G))
    elif len(g) >= 3:
        dr['park'].polygon(gp(g), fill=255)
        if t.get('natural') in ('wood', 'scrub') or t.get('landuse') == 'forest': dr['wood'].polygon(gp(g), fill=255)
def poly_area(pts):
    return abs(sum(pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1] for i in range(len(pts) - 1))) / 2 * G * G
bmeta.sort(key=lambda b: -poly_area(b[0]))
idimg = Image.new('I', (gw, gh), 0)
did = ImageDraw.Draw(idimg)
for i, (pts, t, lon, lat) in enumerate(bmeta):
    did.polygon(pts, fill=i + 1)
    did.line(pts + pts[:1], fill=i + 1, width=5)      # 벽 픽셀도 같은 건물로 잡히게 2.5 m 부풀림
g_bid = np.array(idimg)
g_park, g_water, g_road, g_path, g_bld, g_pal, g_wood = (np.array(layers[k]) for k in ('park', 'water', 'road', 'path', 'bld', 'palace', 'wood'))
# 개울(선형 수로)은 궁궐·공원 안에서만 그린다. 시가지 구간은 대부분 복개돼 도로 밑에 있다.
g_water = np.maximum(g_water, np.where((g_pal > 0) | (g_park > 0), np.array(layers['wline']), 0))
# 궁궐 안의 차도는 보행로로 본다(관람 구역에 차가 다니지 않는다)
g_path = np.maximum(g_path, np.where(g_pal > 0, g_road, 0)); g_road = np.where(g_pal > 0, 0, g_road)

# ── 기존 렌더 범위(fit_rect) 밖의 건물을 OSM 윤곽으로 세운다: 깊이 맵에 z-buffer 로 그려 넣는다.
#    높이는 height / building:levels 태그, 없으면 면적 기반 추정(연출용).
FIT = cam['fit_rect_local']
def to_px(x, y, zz=0.0):
    return ((x * ex[0] + y * ex[1] + zz * ex[2] - cam['cx']) / m + W / 2, H / 2 - (x * ey[0] + y * ey[1] + zz * ey[2] - cam['cy']) / m)
def dg0_row(row):
    return -(((H / 2 - row - 0.5) * m + cam['cy']) * ey[2] / vd[2]) - camvd
def num(v):
    try: return float(str(v).split()[0].replace('m', ''))
    except Exception: return None
added = 0
for pts, t in blds:
    cxm = sum(q[0] for q in pts) / len(pts); cym = sum(q[1] for q in pts) / len(pts)
    if '_force' not in t and FIT[0] - 6 < cxm < FIT[2] + 6 and FIT[1] - 6 < cym < FIT[3] + 6: continue
    area = abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))) / 2
    if area < 12: continue
    hgt = num(t.get('height')) or (num(t.get('building:levels')) or 0) * 3.3
    if not hgt:
        rnd = (hash((round(cxm, 1), round(cym, 1))) % 1000) / 1000
        hgt = (4.5 + 5 * rnd) if area < 150 else (8 + 10 * rnd) if area < 600 else (14 + 16 * rnd)
    hgt = min(hgt, 90.0)
    base = [to_px(q[0], q[1]) for q in pts]
    dh = hgt * ey[2] / m
    xs = [b[0] for b in base]; ys = [b[1] for b in base]
    x0, x1 = int(np.floor(min(xs))) - 1, int(np.ceil(max(xs))) + 2
    y0, y1 = int(np.floor(min(ys) - dh)) - 1, int(np.ceil(max(ys))) + 2
    if x1 <= 0 or y1 <= 0 or x0 >= W or y0 >= H: continue
    x0c, y0c, x1c, y1c = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x1c <= x0c or y1c <= y0c: continue
    bw, bh = x1c - x0c, y1c - y0c
    yy, xx = np.mgrid[y0c:y1c, x0c:x1c]
    sub = depth[y0c:y1c, x0c:x1c]; subn = none[y0c:y1c, x0c:x1c]
    # 벽
    for i in range(len(base)):
        (ax, ay), (bx, by) = base[i - 1], base[i]
        if abs(bx - ax) < 0.5: continue
        im = Image.new('L', (bw, bh), 0)
        ImageDraw.Draw(im).polygon([(ax - x0c, ay - y0c), (bx - x0c, by - y0c), (bx - x0c, by - dh - y0c), (ax - x0c, ay - dh - y0c)], fill=1)
        mk = np.array(im) > 0
        if not mk.any(): continue
        yb = ay + (xx + 0.5 - ax) * (by - ay) / (bx - ax)
        hh = np.clip((yb - (yy + 0.5)) * m / ey[2], 0, hgt)
        dd = dg0_row(yb - 0.5) + hh * vd[2]
        w = mk & ~subn & (dd < sub)
        sub[w] = dd[w]
    # 지붕
    im = Image.new('L', (bw, bh), 0)
    ImageDraw.Draw(im).polygon([(bx_ - x0c, by_ - dh - y0c) for bx_, by_ in base], fill=1)
    mk = np.array(im) > 0
    dd = dg0_row(yy + dh) + hgt * vd[2]
    w = mk & ~subn & (dd < sub)
    sub[w] = dd[w]
    added += 1
print('extruded margin buildings:', added)

py, px = np.mgrid[0:H, 0:W]
u = (px + 0.5 - W / 2) * m + cam['cx']
v = (H / 2 - py - 0.5) * m + cam['cy']
dg0 = -v * ey[2] / vd[2] - camvd                 # z=0 평면의 깊이
z = vd[2] * (depth - dg0)                        # 지면 위 높이
wx = u * ex[0] + v * ey[0] + (depth + camvd) * vd[0]
wy = u * ex[1] + v * ey[1] + (depth + camvd) * vd[1]
z[none] = 0

gi = np.clip(((wx - X0) / G).astype(int), 0, gw - 1)
gj = np.clip(((wy - Y0) / G).astype(int), 0, gh - 1)
s_park, s_water, s_road, s_path, s_bld, in_pal, s_wood = (g[gj, gi] > 0 for g in (g_park, g_water, g_road, g_path, g_bld, g_pal, g_wood))
s_lane = np.array(layers['lane'])[gj, gi] > 0

# ── 벽/지붕: 화면 위로 1px 갈 때 높이 변화
zu = np.roll(z, 1, axis=0); zd = np.roll(z, -1, axis=0)
per = 2 * m / ey[2]
wall = ((zu - zd) / per > 0.55) & ((zu - zd) / per < 2.2)
tall = z > 1.3
# 건물 판정: 지붕은 윤곽 안, 벽은 윤곽 경계라 2 px 팽창한 윤곽으로 본다
g_bld_d = np.array(Image.fromarray(g_bld).filter(ImageFilter.MaxFilter(9))) > 0
s_bld_d = g_bld_d[gj, gi]

cls = np.zeros((H, W), np.uint8)
ground = ~none & ~tall
cls[ground] = 1
cls[ground & in_pal] = 5
cls[ground & s_park] = 3
cls[ground & s_path] = 11
cls[ground & s_road & ~in_pal] = 2
cls[ground & s_water] = 4
is_b = ~none & tall & s_bld_d
cls[is_b & ~wall] = 6
cls[is_b & wall] = 7
cls[is_b & in_pal & ~wall] = 8
cls[is_b & in_pal & wall] = 9
# 수목: 윤곽 밖의 솟은 픽셀. 윤곽 안이라도 지붕이 평평하지 않고 둥글면(가로 높이 변화가 큼) 수목으로 본다
# OSM 에 윤곽이 없는 건물도 있다. 지붕이 평평하면(가로 이웃과 높이 차가 거의 없음) 건물로 본다.
zl = np.roll(z, 1, axis=1)
flat = (np.abs(z - zl) < 0.12) & tall & ~none
flat_frac = np.array(Image.fromarray((flat * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(5))) / 255.0
tall_frac = np.array(Image.fromarray((tall * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(5))) / 255.0
# 경사 지붕 집(한옥 등)은 평평하지 않다. 공원·궁궐 밖에서 빽빽하게 모여 있으면 건물로 본다(외딴 덩어리 = 가로수).
dense = np.array(Image.fromarray((tall * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(14))) / 255.0
flatty = (flat_frac > 0.72 * np.maximum(tall_frac, 1e-3)) | ((dense > 0.5) & ~s_park & ~in_pal)
extra_b = ~none & tall & ~s_bld_d & flatty
# 광화문 월대·앞마당: 낮고 평평한 단(3 m 미만)이 '윤곽 없는 건물'로 잡혀 회색 삼각형이 되고, 생성 모델이 그 자리를 연못으로 칠했다.
# 이 구역에서만 낮은 평면을 지면으로 되돌린다(다른 곳의 판정은 건드리지 않는다).
yy, xx = np.mgrid[0:H, 0:W]
plaza = (xx > 640) & (xx < 840) & (yy > 1130) & (yy < 1300) & extra_b & (z < 3.0)
extra_b &= ~plaza
cls[plaza] = 11
cls[extra_b & ~wall] = 6
cls[extra_b & wall] = 7
cls[~none & tall & ~s_bld_d & ~flatty & ~plaza] = 10
# 숲(OSM wood/forest): 렌더에 나무가 없는 곳은 덩어리 무늬로 수목 클래스를 뿌린다(깊이는 지면 그대로)
rng = np.random.default_rng(11)
noise = np.array(Image.fromarray((rng.random((gh // 6 + 1, gw // 6 + 1)) * 255).astype(np.uint8)).resize((gw, gh), Image.BICUBIC))
lump = (noise > 105)[gj, gi]
cls[(cls == 3) & s_wood & lump] = 10
Image.fromarray(cls).save(out / 'guide_classes.png')
# 앱이 쓸 깊이(외곽 건물 포함): v = (depth-2060)/0.02, R=v>>8, G=v&255, 65535 = 없음
vq = np.clip(np.round((depth - 2060.0) / 0.02), 0, 65534).astype(np.uint16); vq[none] = 65535
rg = np.zeros((H, W, 3), np.uint8); rg[..., 0] = vq >> 8; rg[..., 1] = vq & 255
Image.fromarray(rg).save(out / 'depth_rg8.png')

# ── 색
col = {
    0: (188, 196, 206), 1: (205, 198, 182), 2: (86, 90, 98), 3: (126, 176, 92), 4: (78, 138, 182), 5: (214, 198, 160),
    6: (176, 176, 170), 7: (222, 212, 196), 8: (52, 84, 104), 9: (150, 62, 48), 10: (62, 122, 58), 11: (196, 184, 160),
}
rgb = np.zeros((H, W, 3), np.float64)
for k, c in col.items():
    rgb[cls == k] = c
rgb[(cls == 2) & s_lane] = (226, 226, 220)

# ── 건물별 성격: 주변 시가지가 전부 같은 회색 상자가 되지 않게, 가진 데이터(OSM 태그·렌더 높이·면적·동네)로 종류를 나눈다.
# 1 빌라(저층 다세대) 2 한옥 3 중층 상가·사무 4 고층 타워 5 아파트 6 공공·문화 7 청와대(청기와)
# 한옥은 OSM 태그가 있는 것 외에는 북촌·서촌 구역의 작고 낮은 건물을 한옥으로 '추정'한다(등록 자료가 아니다).
bid = g_bid[gj, gi]
isb = (cls == 6) | (cls == 7)
nb = len(bmeta) + 1
roofm = cls == 6
zsum = np.bincount(bid[roofm], weights=z[roofm], minlength=nb); zcnt = np.bincount(bid[roofm], minlength=nb)
zmean = zsum / np.maximum(zcnt, 1)
def h01(i, salt):
    v = (i * 2654435761 + salt * 40503) & 0xffffffff
    v ^= v >> 15; v = (v * 2246822519) & 0xffffffff; v ^= v >> 13
    return (v & 0xffff) / 65535.0
kind_of = np.zeros(nb, np.uint8); hsh = np.zeros(nb)
for i, (pts, t, lon, lat) in enumerate(bmeta):
    k = i + 1; hsh[k] = h01(k, 7)
    area, zm, b = poly_area(pts), zmean[k], t.get('building', 'yes')
    nm = t.get('name', '')
    tagged_hanok = t.get('roof:material') == 'roof_tiles' or 'building:architecture' in t or (t.get('roof:shape') in ('gabled', 'hipped-and-gabled') and 'roof:colour' in t)
    zone = (126.9815 < lon < 126.9885 and 37.5775 < lat < 37.5850) or (126.9660 < lon < 126.9735 and 37.5765 < lat < 37.5845)
    if abs(lon - 126.9748) < 0.0009 and abs(lat - 37.5866) < 0.0007: kd = 7      # 청와대 본관과 양쪽 별채(청기와). 이름 태그가 없어 좌표로 잡는다.
    elif tagged_hanok or (zone and area < 170 and 0 < zm < 6.5 and h01(k, 3) < 0.75): kd = 2
    elif zm >= 38: kd = 4
    elif b in ('apartments', 'residential') and zm >= 20: kd = 5
    elif b in ('school', 'public', 'university', 'church', 'civic', 'government') or t.get('tourism') in ('museum', 'gallery') or t.get('amenity') in ('place_of_worship', 'library', 'townhall', 'theatre', 'arts_centre'): kd = 6
    elif zm >= 14: kd = 3
    else: kd = 1
    kind_of[k] = kd
kind = kind_of[bid]
# 윤곽이 없는 건물(높이로만 판정한 것)은 높이로 나눈다
unk = isb & (bid == 0)
kind[unk & (z < 14)] = 1; kind[unk & (z >= 14)] = 3; kind[unk & (z >= 38)] = 4
kind[~isb] = 0
hpx = np.where(bid > 0, hsh[bid], ((np.floor(wx / 14) * 31 + np.floor(wy / 14) * 17) % 97) / 97.0)
ROOFS = {1: [(108, 150, 112), (112, 156, 118), (150, 150, 146), (168, 166, 158), (172, 104, 84), (92, 100, 110)],
         2: [(64, 66, 74)], 3: [(160, 160, 156), (140, 146, 150), (176, 170, 160)], 4: [(150, 154, 160)],
         5: [(170, 170, 166)], 6: [(120, 146, 130), (160, 150, 140), (150, 100, 84)], 7: [(58, 112, 176)]}
WALLS = {1: [(170, 104, 84), (186, 120, 96), (214, 200, 176), (228, 222, 210), (190, 186, 176), (150, 112, 96)],
         2: [(226, 216, 196)], 3: [(196, 188, 172), (170, 176, 182), (206, 196, 186), (150, 140, 130), (184, 170, 150)],
         4: [(96, 136, 170), (76, 110, 140), (120, 150, 160), (110, 96, 84), (140, 160, 180)],
         5: [(232, 228, 216), (222, 214, 196), (214, 222, 226)], 6: [(210, 200, 184), (196, 150, 120), (200, 200, 196)], 7: [(236, 232, 222)]}
for kd in range(1, 8):
    for tbl, c_ in ((ROOFS, 6), (WALLS, 7)):
        lst = tbl[kd]; hh = hpx if c_ == 6 else (hpx * 7.31) % 1.0
        for j, colr in enumerate(lst):
            mk = (cls == c_) & (kind == kd) & (np.floor(hh * len(lst)).astype(int) % len(lst) == j)
            rgb[mk] = colr
Image.fromarray(kind.astype(np.uint8)).save(out / 'guide_kinds.png')

# ── 랜드마크: 이름으로 건물을 찾아 화면 위치를 기록한다(전용 프롬프트로 따로 그려 합성하는 데 쓴다. landmarks.py).
Image.fromarray(bid.astype(np.uint16)).save(out / 'guide_bid.png')
LM = {'gwanghwamun': ['광화문'], 'geunjeongjeon': ['근정전'], 'gyeonghoeru': ['경회루'], 'hyangwonjeong': ['향원정'],
      'folkmuseum': ['국립민속박물관'], 'palacemuseum': ['국립고궁박물관'], 'sejongcenter': ['세종문화회관 대극장', '세종문화회관 체임버홀', '세종문화회관 미술관'],
      'govcomplex': ['정부서울청사'], 'mmca': ['국립현대미술관'], 'dongsipjagak': ['동십자각'], 'heungnyemun': ['흥례문'], 'geunjeongmun': ['근정문'],
      'jibokjae': ['집옥재'], 'yeongbingwan': ['영빈관'], 'chunchugwan': ['춘추관'], 'historymuseum': ['대한민국역사박물관'], 'usembassy': ['주한미국대사관'],
      'kyobo': ['교보생명빌딩'], 'twintree': ['트윈트리타워 A동', '트윈트리타워 B동'], 'gangnyeongjeon': ['강녕전'], 'gyotaejeon': ['교태전'], 'jagyeongjeon': ['자경전'],
      # 주변 도심
      'ktwest': ['KT광화문빌딩 West'], 'kteast': ['KT광화문빌딩East'], 'dtower': ['D타워'], 'fourseasons': ['포시즌스호텔 서울'], 'police': ['서울지방경찰청 본관'],
      'jeongdok': ['정독도서관'], 'skseorin': ['SK 서린빌딩'], 'jongnotower': ['종로타워'], 'granseoul': ['그랑서울'], 'heungkuk': ['흥국생명빌딩'],
      'centropolis': ['센트로폴리스빌딩 A', '센트로폴리스빌딩 B'], 'concourt': ['헌법재판소 본관'], 'seoulhistory': ['서울역사박물관'], 'saemunan': ['새문안교회'],
      'ilmin': ['일민미술관'], 'japanembassy': ['주한일본대사관'], 'sarangchae': ['청와대 사랑채'], 'yeongchumun': ['영추문'], 'artsonje': ['아트선재센터'],
      'tower8': ['타워8'], 'cheongjin': ['청계11빌딩'], 'lgkwanghwamun': ['LG광화문빌딩'], 'seoulmuseum': ['서울미술관']}
lm_out = {}
for key, names in LM.items():
    ids = [i + 1 for i, b in enumerate(bmeta) if b[1].get('name') in names]
    if key == 'folkmuseum' and not ids: ids = [i + 1 for i, b in enumerate(bmeta) if '민속박물관' in b[1].get('name', '')]
    if key == 'mmca' and not ids: ids = [i + 1 for i, b in enumerate(bmeta) if '현대미술관' in b[1].get('name', '')]
    if not ids: continue
    mk = np.isin(bid, ids) & (cls >= 6) & (cls <= 9)
    if mk.sum() < 60: continue
    ys, xs = np.where(mk)
    lm_out[key] = {'ids': ids, 'cx': float(xs.mean()), 'cy': float(ys.mean()), 'bbox': [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], 'px': int(mk.sum())}
# 이름 태그가 없는 랜드마크는 좌표 근처의 건물로 잡는다 (경도, 위도, 반경 m)
LMC = {'folkmuseum': (126.9790, 37.5817, 45), 'palacemuseum': (126.9750, 37.5764, 45), 'mmca': (126.9803, 37.5790, 60)}
for key, (lo, la, rad) in LMC.items():
    if key in lm_out: continue
    ids = [i + 1 for i, b in enumerate(bmeta) if math.hypot((b[2] - lo) * 88800, (b[3] - la) * 111000) < rad]
    mk = np.isin(bid, ids) & (cls >= 6) & (cls <= 9)
    if ids and mk.sum() >= 60:
        ys, xs = np.where(mk)
        lm_out[key] = {'ids': ids, 'cx': float(xs.mean()), 'cy': float(ys.mean()), 'bbox': [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], 'px': int(mk.sum())}
bh = [i + 1 for i in range(len(bmeta)) if kind_of[i + 1] == 7]
if bh:
    mk = np.isin(bid, bh) & (cls >= 6) & (cls <= 9)
    if mk.sum() >= 60:
        ys, xs = np.where(mk)
        lm_out['bluehouse'] = {'ids': bh, 'cx': float(xs.mean()), 'cy': float(ys.mean()), 'bbox': [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], 'px': int(mk.sum())}
json.dump(lm_out, open(out / 'landmarks.json', 'w'), ensure_ascii=False, indent=1)
print('landmarks:', {k: (round(v['cx']), round(v['cy']), v['px']) for k, v in lm_out.items()})

# 음영: 깊이 기울기로 좌/우 면 구분 + 높이에 따른 벽 그라데이션
dx = np.roll(depth, -1, axis=1) - np.roll(depth, 1, axis=1)
dx[none | np.roll(none, 1, axis=1) | np.roll(none, -1, axis=1)] = 0
side = np.clip(dx / 1.2, -1, 1)                 # +면 오른쪽으로 멀어짐(왼쪽을 향한 벽), −면 반대
shade = np.ones((H, W))
wmask = (cls == 7) | (cls == 9)
shade[wmask] = 0.86 + 0.20 * side[wmask]
tmask = cls == 10
shade[tmask] = 0.80 + 0.35 * np.clip((zu - zd)[tmask] / 3.0, -0.5, 0.6)
rgb *= shade[..., None]
# 궁궐 지붕: 기왓골 줄무늬(아스팔트와 헷갈리지 않게)
pr = cls == 8
rgb[pr & ((px + py) % 4 < 2)] *= 0.80
hr = (cls == 6) & ((kind == 2) | (kind == 7))
rgb[hr & ((px + py) % 4 < 2)] *= 0.82
# 층 구분선(건물 벽, 3.3 m 마다)과 윤곽선
floor_line = wmask & (np.floor(z / 3.3) != np.floor(zd / 3.3))
rgb[floor_line & (cls == 7)] *= 0.86
edge = np.abs(depth - np.roll(depth, 1, axis=0)) + np.abs(depth - np.roll(depth, 1, axis=1))
rgb[(edge > 2.5) & ~none] *= 0.62
Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).save(out / 'guide_color.png')

dn = depth.copy(); dn[none] = np.nan
lo, hi = np.nanpercentile(dn, 0.5), np.nanpercentile(dn, 99.5)
g = 1 - np.clip((dn - lo) / (hi - lo), 0, 1)
g[none] = 0
Image.fromarray((g * 255).astype(np.uint8)).save(out / 'guide_depth.png')
print('wrote', out, {int(k): int((cls == k).sum()) for k in np.unique(cls)})
if os.environ.get('LM_DEBUG'):
    for nm in os.environ['LM_DEBUG'].split(','):
        ids = [i + 1 for i, b in enumerate(bmeta) if nm in b[1].get('name', '')]
        m = np.isin(bid, ids); gm = np.isin(g_bid, ids)
        print(nm, ids, 'bid px', int(m.sum()), 'ground px', int(gm.sum()), 'cls', np.bincount(cls[m], minlength=12).tolist() if m.any() else '', [(round(bmeta[i - 1][0][0][0]), round(bmeta[i - 1][0][0][1])) for i in ids])
if os.environ.get('PAL_DEBUG'):
    # 궁궐 경계(화면 좌표)를 따로 저장한다. 밑그림 출력은 바꾸지 않는다.
    Image.fromarray((in_pal * 255).astype(np.uint8)).save(out / 'debug_in_pal.png')
    json.dump([{'id': i + 1, 'tags': b[1], 'lon': b[2], 'lat': b[3]} for i, b in enumerate(bmeta)], open(out / 'debug_bmeta.json', 'w'), ensure_ascii=False)
