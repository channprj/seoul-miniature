# 지면 그림(화면 좌표, 6.25 cm): 평색 알베도에서 보이는 지면은 그대로, 건물·나무에 가려진 곳은
# OSM 도로를 그려 넣고 나머지는 가장 가까운 "도로 아닌" 지면색으로 메운다. 원래 자료에 없던 동네 골목도 OSM 으로 추가.
import json, sys, numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from shapely.geometry import LineString
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__))); import osm_blds
Image.MAX_IMAGE_PIXELS = None
RR = __import__('os').environ.get('P3D_ROOT', 'work/') + 'redraw/'; R = RR + 'hires/passes/'
cam = json.load(open(RR + 'hires/camera/nw45w_x8_0p0625_camera.json'))
EX, EY = np.array(cam['screen_x_axis']), np.array(cam['screen_y_axis']); CX, CY = cam['cx'], cam['cy']; PX, W, H = 0.0625, 22016, 13568
def proj(xy): xy = np.asarray(xy); return np.stack([(xy @ EX[:2] - CX) / PX + W / 2, H / 2 - (xy @ EY[:2] - CY) / PX], 1)
alb = np.array(Image.open(R + 'flat_albedo_unlit_rgb8.png').convert('RGB')); cls = np.array(Image.open(R + 'old_class_u8.png'))
ground = np.isin(cls, (3, 4, 5, 6, 7, 12, 14, 15)) & (alb.sum(-1) > 30)
WID = {'motorway': 18, 'trunk': 18, 'primary': 18, 'secondary': 12, 'tertiary': 9, 'residential': 5.5, 'unclassified': 5.5, 'living_street': 5, 'service': 3.6,
       'primary_link': 7, 'secondary_link': 7, 'tertiary_link': 6, 'pedestrian': 5, 'footway': 2.0, 'path': 1.8, 'steps': 2.0, 'cycleway': 2.0}
masks = {k: Image.new('L', (W, H), 0) for k in ('road', 'alley', 'walk')}; dr = {k: ImageDraw.Draw(v) for k, v in masks.items()}
n = 0
for e in json.load(open(RR + 'osm_raw.json'))['elements']:
    t = e.get('tags', {}); hw = t.get('highway')
    if e['type'] != 'way' or hw not in WID or not e.get('geometry') or t.get('tunnel') or t.get('indoor') or t.get('covered') == 'yes': continue
    pts = [osm_blds.tm5186(q['lon'], q['lat']) for q in e['geometry']]
    if len(pts) < 2: continue
    w = WID[hw]
    if t.get('lanes', '').isdigit() and hw not in ('footway', 'path', 'steps', 'pedestrian'): w = max(w, int(t['lanes']) * 3.3)
    if t.get('area') == 'yes' and len(pts) > 3:
        from shapely.geometry import Polygon
        poly = Polygon(pts).buffer(0)
    else: poly = LineString(pts).buffer(w / 2, cap_style=1, join_style=1)
    kind = 'walk' if hw in ('pedestrian', 'footway', 'path', 'steps', 'cycleway') else 'alley' if hw in ('residential', 'unclassified', 'living_street', 'service') else 'road'
    for g in (poly.geoms if poly.geom_type == 'MultiPolygon' else [poly]):
        if g.is_empty: continue
        dr[kind].polygon([tuple(p) for p in proj(np.array(g.exterior.coords))], fill=255); n += 1
print('osm ways drawn', n)
m = {k: np.array(v) > 0 for k, v in masks.items()}
ROAD = np.array([86, 90, 100], np.uint8); ALLEY = np.array([112, 114, 120], np.uint8); WALK = np.array([208, 200, 182], np.uint8)
# 가려진 곳 메우기: 도로·표시가 아닌 지면만 씨앗으로
seed = ground & ~np.isin(cls, (3, 12)); s8 = seed[4::8, 4::8]; a8 = alb[4::8, 4::8]; c8 = cls[4::8, 4::8]
idx = ndimage.distance_transform_edt(~s8, return_distances=False, return_indices=True)
up = lambda a: np.repeat(np.repeat(a, 8, 0), 8, 1)[:H, :W]
out = alb.copy(); gcls = cls.copy(); occ = ~ground
out[occ] = up(a8[idx[0], idx[1]])[occ]; gcls[occ] = up(c8[idx[0], idx[1]])[occ]
# 옛 앱 클래스 맵(0.5 m)의 녹지(3)·수목(10) 자리인데 바탕 지면으로 남은 곳은 잔디로(청와대 경내·북악산 자락 등 평색 알베도에 녹지가 없던 곳)
oc = np.array(Image.open(__import__('os').environ.get('P3D_OLD_CLASSES', 'work/old_classes.png'))); ocu = up(oc)
m05 = ndimage.binary_opening(np.isin(oc, (3, 10)), iterations=3); lab, nl = ndimage.label(m05); sz = ndimage.sum(m05, lab, range(1, nl + 1)); m05 = np.isin(lab, 1 + np.nonzero(sz >= 400)[0])  # 100 m² 미만 조각 제외
msm = np.asarray(Image.fromarray((ndimage.gaussian_filter(m05.astype(np.float32), 1.2) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)) > 127  # 계단 없는 경계
lawn = np.median(alb[::16, ::16][cls[::16, ::16] == 5], 0).astype(np.uint8); grn = (gcls == 7) & msm; out[grn] = lawn; gcls[grn] = 5; print('lawn added px', int(grn.sum()), lawn)
np.save('aoi_05m.npy', oc > 0)
base = (gcls == 7)  # 바탕 지면에만 OSM 길을 얹는다(궁 마당·잔디·광장·기존 도로는 그대로)
for k, col, code in (('walk', WALK, 4), ('alley', ALLEY, 3), ('road', ROAD, 3)):
    put = m[k] & (base | (occ & ~np.isin(gcls, (14,)))) if k != 'walk' else m[k] & base
    out[put] = col; gcls[put] = code
Image.fromarray(out).save('ground_clean.png'); Image.fromarray(gcls).save('ground_class.png'); Image.fromarray(out[::8, ::8]).save('ground_clean_05m.png'); print('ok')
